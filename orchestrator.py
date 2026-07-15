import json
import os
import uuid
import base64
import re
import asyncio
import aiohttp
import urllib3
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

# ============================================
# 1. КОНФИГУРАЦИЯ
# ============================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
GIGACHAT_CLIENT_ID = os.getenv("GIGACHAT_CLIENT_ID")
GIGACHAT_CLIENT_SECRET = os.getenv("GIGACHAT_CLIENT_SECRET")

# ============================================
# 2. ЗАГРУЗКА АГЕНТОВ
# ============================================
with open("agents_config.json", "r", encoding="utf-8") as f:
    config = json.load(f)
    agents = {agent["id"]: agent for agent in config["agents"]}

# ============================================
# 3. GIGACHAT: ПОЛУЧЕНИЕ ТОКЕНА (АСИНХРОННО)
# ============================================
async def get_gigachat_token():
    if not GIGACHAT_CLIENT_ID or not GIGACHAT_CLIENT_SECRET:
        return "⚠️ Нет Client ID или Secret в .env"

    auth_string = base64.b64encode(
        f"{GIGACHAT_CLIENT_ID}:{GIGACHAT_CLIENT_SECRET}".encode()
    ).decode()

    url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "RqUID": str(uuid.uuid4()),
        "Authorization": f"Basic {auth_string}"
    }
    data = {"scope": "GIGACHAT_API_PERS"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, data=data, ssl=False, timeout=30) as response:
                token_data = await response.json()
                return token_data.get("access_token")
    except Exception as e:
        return f"⚠️ Ошибка получения токена: {str(e)}"

# ============================================
# 4. GIGACHAT: ГЕНЕРАЦИЯ КАРТИНКИ (АСИНХРОННО)
# ============================================
async def generate_image(prompt):
    access_token = await get_gigachat_token()
    if isinstance(access_token, str) and access_token.startswith("⚠️"):
        return access_token

    url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
    payload = {
        "model": "GigaChat-2-Max",
        "messages": [
            {"role": "system", "content": "Ты — художник, который генерирует изображения по запросам пользователя с помощью встроенной функции text2image."},
            {"role": "user", "content": prompt}
        ],
        "function_call": "auto",
        "profanity_check": False
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {access_token}"
    }

    try:
        async with aiohttp.ClientSession() as session:
            # 1. Запрос на генерацию картинки
            async with session.post(url, headers=headers, json=payload, ssl=False, timeout=120) as response:
                data = await response.json()
                content = data["choices"][0]["message"]["content"]
                match = re.search(r'<img src="([^"]+)"', content)
                if not match:
                    return f"⚠️ Не найден ID картинки: {content[:200]}"

                file_id = match.group(1)
                download_url = f"https://gigachat.devices.sberbank.ru/api/v1/files/{file_id}/content"
                download_headers = {
                    "Accept": "application/octet-stream",
                    "Authorization": f"Bearer {access_token}"
                }

                # 2. Скачивание картинки
                async with session.get(download_url, headers=download_headers, ssl=False, timeout=30) as img_response:
                    if img_response.status != 200:
                        return f"⚠️ Ошибка скачивания: {img_response.status}"

                    file_path = "generated_image.jpg"
                    with open(file_path, "wb") as f:
                        f.write(await img_response.read())

                # 3. Отправка картинки в Telegram (правильный способ)
                send_photo_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
                
                # Открываем файл и отправляем через multipart/form-data
                with open(file_path, 'rb') as photo_file:
                    # Формируем данные для отправки
                    form_data = aiohttp.FormData()
                    form_data.add_field('chat_id', CHAT_ID)
                    form_data.add_field('caption', f"🎨 {prompt}")
                    form_data.add_field('photo', photo_file, filename='image.jpg', content_type='image/jpeg')
                    
                    async with session.post(send_photo_url, data=form_data, ssl=False, timeout=30) as send_resp:
                        if send_resp.status == 200:
                            return "✅ Картинка отправлена в чат!"
                        else:
                            text = await send_resp.text()
                            return f"⚠️ Ошибка отправки в Telegram: {send_resp.status} - {text}"

    except Exception as e:
        return f"⚠️ Ошибка генерации: {str(e)}"

# ============================================
# 5. GIGACHAT: ТЕКСТОВЫЙ ОТВЕТ (АСИНХРОННО)
# ============================================
async def call_gigachat_text(agent, user_message):
    access_token = await get_gigachat_token()
    if isinstance(access_token, str) and access_token.startswith("⚠️"):
        return access_token

    url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
    prompt = f"{agent['prompt']}\n\nПользователь: {user_message}\n\nОтвет:"

    payload = {
        "model": "GigaChat-2-Max",
        "messages": [
            {"role": "system", "content": "Ты — полезный AI-ассистент. Отвечай на вопросы пользователя."},
            {"role": "user", "content": prompt}
        ],
        "profanity_check": False,
        "temperature": 0.7,
        "max_tokens": 2000
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {access_token}"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload, ssl=False, timeout=60) as response:
                data = await response.json()
                return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"⚠️ Ошибка GigaChat: {str(e)}"

# ============================================
# 6. ВЫЗОВ АГЕНТА (АСИНХРОННО)
# ============================================
async def call_agent(agent_id, user_message):
    agent = agents.get(agent_id)
    if not agent:
        return f"❌ Агент {agent_id} не найден"

    if agent_id == "designer":
        return await generate_image(user_message)
    return await call_gigachat_text(agent, user_message)

# ============================================
# 7. ОПРЕДЕЛЕНИЕ АГЕНТА ПО ЗАПРОСУ
# ============================================
def detect_agent(text):
    text_lower = text.lower().strip()
    commands = {
        "/strategy": "strategist",
        "/research": "researcher",
        "/write": "writer",
        "/design": "designer",
        "/code": "developer",
        "/pm": "pm",
        "/idea": "strategist",
        "/seo": "devops"
    }
    for cmd, agent_id in commands.items():
        if text_lower.startswith(cmd):
            query = text[len(cmd):].strip()
            return agent_id, query if query else ""

    keywords = {
        "designer": ["нарисуй", "дизайн", "логотип", "картинк", "изображени", "цвет", "стиль"],
        "researcher": ["исследуй", "найди", "данные", "информаци", "поиск", "анализ"],
        "writer": ["напиши", "текст", "пост", "статья", "стих", "рассказ", "сочини"],
        "developer": ["код", "программа", "скрипт", "функци", "баг", "ошибка"],
        "strategist": ["стратеги", "план", "развитие", "перспектив", "цель"],
        "devops": ["seo", "аудит", "проверь сайт"]
    }

    for agent_id, words in keywords.items():
        if any(w in text_lower for w in words):
            return agent_id, text
    return "pm", text

# ============================================
# 8. ОТПРАВКА СООБЩЕНИЙ (АСИНХРОННО)
# ============================================
async def send_telegram_message(text, chat_id=CHAT_ID):
    if not TELEGRAM_TOKEN or not chat_id:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(url, json={"chat_id": chat_id, "text": text}, timeout=15)
    except Exception:
        pass

# ============================================
# 9. РАСПРЕДЕЛЕНИЕ СЛОЖНЫХ ЗАДАЧ
# ============================================
def distribute_task(query):
    task_map = {
        "анализ": ["researcher", "strategist"],
        "исследование": ["researcher", "writer"],
        "прогноз": ["researcher", "strategist"],
        "план": ["strategist", "writer"],
        "код": ["developer"],
        "дизайн": ["designer"],
        "текст": ["writer"],
        "стих": ["writer"],
        "стратегия": ["strategist"],
        "seo": ["devops"],
        "аудит": ["devops"],
        "презентаци": ["writer", "researcher"],
        "концепци": ["designer", "strategist"],
        "рынок": ["researcher", "strategist"]
    }
    query_lower = query.lower()
    used_agents = []
    for keyword, agents_list in task_map.items():
        if keyword in query_lower:
            used_agents.extend(agents_list)
    if not used_agents:
        return {"pm": query}
    used_agents = list(set(used_agents))
    tasks = {}
    for agent_id in used_agents:
        agent = agents.get(agent_id)
        if agent:
            tasks[agent_id] = f"{query}\n\nТвоя роль: {agent['role']}. Ответь на запрос с этой позиции."
    return tasks

async def collect_results(tasks):
    results = {}
    for agent_id, sub_task in tasks.items():
        agent = agents.get(agent_id)
        if agent:
            results[agent['name']] = await call_agent(agent_id, sub_task)
    return results

def format_report(results):
    if not results:
        return "⚠️ Не удалось собрать ответы от агентов."
    report = "📊 **Командный отчёт**\n\n"
    for agent_name, response in results.items():
        report += f"### {agent_name}\n{response}\n\n---\n\n"
    return report

# ============================================
# 10. ГЛАВНАЯ ЛОГИКА (АСИНХРОННАЯ)
# ============================================
async def process_message(message_text):
    # === ДИАГНОСТИКА ===
    if message_text.lower() == "/debug":
        return "🔧 Бот работает (асинхронная версия). Команды: /design, /write, /research, /strategy, /code, /seo"

    # === ПРИВЕТСТВИЯ ===
    if message_text.lower() in ["/start", "привет", "хай", "здарова"]:
        team_list = "\n".join([f"{a['name']} — {a['role']}" for a in config["agents"]])
        return f"👋 Привет! Я твой AI-штаб.\n\nКоманда:\n{team_list}\n\nНапиши запрос или используй команды:\n/design — картинка\n/write — текст\n/research — исследование\n/strategy — стратегия\n/code — код\n/seo — аудит"

    if message_text.lower() in ["/team", "/команда"]:
        team_list = "\n".join([f"{a['name']} — {a['role']}" for a in config["agents"]])
        return f"🤖 Моя команда:\n\n{team_list}"

    # === ОБРАБОТКА КОМАНД ===
    if message_text.startswith("/"):
        agent_id, query = detect_agent(message_text)
        await send_telegram_message(f"🤖 {agents[agent_id]['name']} обрабатывает запрос...")
        result = await call_agent(agent_id, query)
        return f"🧠 {agents[agent_id]['name']}:\n\n{result}"

    # === СЛОЖНЫЕ ЗАДАЧИ ===
    tasks = distribute_task(message_text)
    if len(tasks) > 1:
        await send_telegram_message("🧠 Анализирую запрос... Распределяю задачи между агентами.")
        results = await collect_results(tasks)
        return format_report(results)

    if tasks:
        agent_id = list(tasks.keys())[0]
        sub_task = tasks[agent_id]
        await send_telegram_message(f"🤖 {agents[agent_id]['name']} обрабатывает запрос...")
        result = await call_agent(agent_id, sub_task)
        return f"🧠 {agents[agent_id]['name']}:\n\n{result}"

    # === ЕСЛИ НИЧЕГО НЕ ПОДОШЛО ===
    await send_telegram_message("🤖 Менеджер обрабатывает запрос...")
    result = await call_agent("pm", message_text)
    return f"🧠 Менеджер:\n\n{result}"
