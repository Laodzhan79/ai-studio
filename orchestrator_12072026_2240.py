import json
import requests
import os
import uuid
import base64
import re
import google.generativeai as genai
from dotenv import load_dotenv
import urllib3

# Отключаем SSL-предупреждения для GigaChat
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

# ============================================
# 1. КОНФИГУРАЦИЯ
# ============================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

GIGACHAT_CLIENT_ID = os.getenv("GIGACHAT_CLIENT_ID")
GIGACHAT_CLIENT_SECRET = os.getenv("GIGACHAT_CLIENT_SECRET")

# ============================================
# 2. ИНИЦИАЛИЗАЦИЯ GEMINI
# ============================================
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-flash-latest')
else:
    gemini_model = None

# ============================================
# 3. ЗАГРУЗКА АГЕНТОВ
# ============================================
with open("agents_config.json", "r", encoding="utf-8") as f:
    config = json.load(f)
    agents = {agent["id"]: agent for agent in config["agents"]}

# ============================================
# 4. GIGACHAT: ПОЛУЧЕНИЕ ТОКЕНА И ГЕНЕРАЦИЯ
# ============================================
def get_gigachat_token():
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
        response = requests.post(url, headers=headers, data=data, timeout=30, verify=False)
        response.raise_for_status()
        token_data = response.json()
        return token_data.get("access_token")
    except Exception as e:
        return f"⚠️ Ошибка получения токена: {str(e)}"

def generate_image(prompt):
    access_token = get_gigachat_token()
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
        response = requests.post(url, headers=headers, json=payload, timeout=120, verify=False)
        response.raise_for_status()
        data = response.json()

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
        image_response = requests.get(download_url, headers=download_headers, timeout=30, verify=False)

        if image_response.status_code == 200:
            file_path = "generated_image.jpg"
            with open(file_path, "wb") as f:
                f.write(image_response.content)

            send_photo_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
            files = {'photo': open(file_path, 'rb')}
            data_payload = {'chat_id': CHAT_ID, 'caption': f"🎨 {prompt}"}
            requests.post(send_photo_url, files=files, data=data_payload)
            return "✅ Картинка отправлена в чат!"
        else:
            return f"⚠️ Ошибка скачивания: {image_response.status_code}, ссылка: {download_url}"

    except Exception as e:
        return f"⚠️ Ошибка генерации: {str(e)}"

# ============================================
# 5. ВЫЗОВ АГЕНТА
# ============================================
def call_agent(agent_id, user_message):
    agent = agents.get(agent_id)
    if not agent:
        return f"❌ Агент {agent_id} не найден"

    # Дизайнер → картинка
    if agent_id == "designer":
        return generate_image(user_message)

    # Все остальные → GigaChat (вместо Gemini)
    return call_gigachat_text(prompt)

def call_gigachat_text(prompt):
    """Отправляет текстовый запрос в GigaChat (без картинок)"""
    access_token = get_gigachat_token()
    if isinstance(access_token, str) and access_token.startswith("⚠️"):
        return access_token

    url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
    payload = {
        "model": "GigaChat-2-Max",
        "messages": [
            {"role": "system", "content": "Ты — полезный AI-ассистент. Отвечай на вопросы пользователя."},
            {"role": "user", "content": prompt}
        ],
        "profanity_check": False
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {access_token}"
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60, verify=False)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"⚠️ Ошибка GigaChat: {str(e)}"
# ============================================
# 6. ОПРЕДЕЛЕНИЕ АГЕНТА ПО ЗАПРОСУ
# ============================================
def detect_agent(text):
    text_lower = text.lower().strip()

    # Явные команды
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

    # Ключевые слова
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
# 7. ОТПРАВКА СООБЩЕНИЙ
# ============================================
def send_telegram_message(text, chat_id=CHAT_ID):
    if not TELEGRAM_TOKEN:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text})

# ============================================
# 8. РАСПРЕДЕЛЕНИЕ СЛОЖНЫХ ЗАДАЧ
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
        "презентаци": ["writer", "researcher"],  # <-- добавил
        "концепци": ["designer", "strategist"],   # <-- добавил
        "рынок": ["researcher", "strategist"]     # <-- добавил
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
            sub_task = f"{query}\n\nТвоя роль: {agent['role']}. Ответь на запрос с этой позиции."
            tasks[agent_id] = sub_task

    return tasks

def collect_results(tasks):
    results = {}
    for agent_id, sub_task in tasks.items():
        agent = agents.get(agent_id)
        if agent:
            results[agent['name']] = call_agent(agent_id, sub_task)
    return results

def format_report(results):
    if not results:
        return "⚠️ Не удалось собрать ответы от агентов."

    report = "📊 **Командный отчёт**\n\n"
    for agent_name, response in results.items():
        report += f"### {agent_name}\n{response}\n\n---\n\n"

    return report

# ============================================
# 9. ГЛАВНАЯ ЛОГИКА
# ============================================
def process_message(message_text):
    # Приветствия и команды
    if message_text.lower() in ["/start", "привет", "хай", "здарова"]:
        team_list = "\n".join([f"{a['name']} — {a['role']}" for a in config["agents"]])
        return f"👋 Привет! Я твой AI-штаб.\n\nКоманда:\n{team_list}\n\nНапиши запрос или используй команды:\n/design — картинка\n/write — текст\n/research — исследование\n/strategy — стратегия\n/code — код\n/seo — аудит"

    if message_text.lower() in ["/team", "/команда"]:
        team_list = "\n".join([f"{a['name']} — {a['role']}" for a in config["agents"]])
        return f"🤖 Моя команда:\n\n{team_list}"

    # Проверяем, есть ли команда (/design, /write и т.д.)
    if message_text.startswith("/"):
        agent_id, query = detect_agent(message_text)
        if query:
            send_telegram_message(f"🤖 {agents[agent_id]['name']} обрабатывает запрос...")
            result = call_agent(agent_id, query)
            return f"🧠 {agents[agent_id]['name']}:\n\n{result}"
        else:
            return f"🤔 Агент {agents[agent_id]['name']} ждёт твой запрос."

    # Если нет команды — пробуем сложную задачу
    tasks = distribute_task(message_text)

    if len(tasks) > 1:
        send_telegram_message("🧠 Анализирую запрос... Распределяю задачи между агентами.")
        results = collect_results(tasks)
        return format_report(results)

    if tasks:
        agent_id = list(tasks.keys())[0]
        sub_task = tasks[agent_id]
        send_telegram_message(f"🤖 {agents[agent_id]['name']} обрабатывает запрос...")
        result = call_agent(agent_id, sub_task)
        return f"🧠 {agents[agent_id]['name']}:\n\n{result}"

    # Если ничего не подошло — Менеджер
    send_telegram_message("🤖 Менеджер обрабатывает запрос...")
    result = call_agent("pm", message_text)
    return f"🧠 Менеджер:\n\n{result}"
