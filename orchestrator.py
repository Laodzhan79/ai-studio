import json
import requests
import random
import os
from datetime import datetime

# === НАСТРОЙКИ ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "REPLACED")
CHAT_ID = os.getenv("CHAT_ID", "REPLACED")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "твой_ключ_здесь")  # Бесплатно на platform.deepseek.com

# === ЗАГРУЗКА КОНФИГА ===
with open("agents_config.json", "r", encoding="utf-8") as f:
    config = json.load(f)
    agents = {agent["id"]: agent for agent in config["agents"]}

def call_agent(agent_id, user_message):
    """Вызывает AI агента через DeepSeek API с обработкой ошибок"""
    agent = agents.get(agent_id)
    if not agent:
        return f"❌ Агент {agent_id} не найден"
    
    # Формируем промпт
    prompt = f"{agent['prompt']}\n\nПользователь: {user_message}\n\nОтвет:"
    
    # Вызов DeepSeek API
    try:
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 2000
            },
            timeout=30
        )
        
        # Проверяем статус ответа
        if response.status_code != 200:
            error_detail = response.text
            return f"⚠️ Ошибка API (код {response.status_code}): {error_detail[:200]}"
        
        # Парсим ответ
        result = response.json()
        
        # Проверяем наличие ключа 'choices'
        if "choices" not in result or not result["choices"]:
            return f"⚠️ API вернул пустой ответ: {result}"
        
        # Возвращаем текст ответа
        return result["choices"][0]["message"]["content"]
        
    except requests.exceptions.Timeout:
        return "⚠️ Превышено время ожидания ответа от API. Попробуй позже."
    except requests.exceptions.RequestException as e:
        return f"⚠️ Ошибка сети: {str(e)[:100]}"
    except KeyError as e:
        return f"⚠️ Неожиданный формат ответа API: {str(e)}"
    except Exception as e:
        return f"⚠️ Неизвестная ошибка: {str(e)[:100]}"

def send_telegram_message(text, chat_id=CHAT_ID):
    """Отправляет сообщение в Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def get_agent_by_command(text):
    """Определяет, какого агента вызвать по команде"""
    command_map = {
        "/strategy": "strategist",
        "/research": "researcher",
        "/write": "writer",
        "/design": "designer",
        "/code": "developer",
        "/pm": "pm",
        "/idea": "strategist",  # Синоним
        "/help": "pm"           # Синоним
    }
    
    # Проверяем команду в начале сообщения
    for cmd, agent_id in command_map.items():
        if text.startswith(cmd):
            return agent_id, text[len(cmd):].strip()
    
    # Если нет команды, выбираем случайного агента
    random_agent = random.choice(list(agents.keys()))
    return random_agent, text

def process_message(message_text):
    """Главная логика обработки сообщений"""
    # Приветствие
    if message_text.lower() in ["/start", "привет", "здарова", "хай"]:
        return "👋 Привет! Я твой штаб AI-агентов.\n\nВот моя команда:\n" + \
               "\n".join([f"{a['name']} — {a['role']}" for a in config["agents"]]) + \
               "\n\nПросто напиши вопрос или выбери агента:\n" + \
               "/strategy — стратегия\n/research — исследование\n/write — написать текст\n/design — дизайн\n/code — код\n/pm — задачи"
    
    # Показываем команду
    if message_text.lower() in ["/team", "/agents", "/команда"]:
        team_list = "\n".join([f"{a['name']} — {a['role']}" for a in config["agents"]])
        return f"🤖 Моя команда:\n\n{team_list}\n\nНапиши вопрос, и я вызову подходящего агента!"
    
    # Обработка команд и вызов агентов
    agent_id, query = get_agent_by_command(message_text)
    
    if not query:
        return f"🤔 Агент {agents[agent_id]['name']} ждёт твоего вопроса. Напиши, что нужно сделать."
    
    # Вызываем агента
    send_telegram_message(f"🤖 {agents[agent_id]['name']} обрабатывает запрос...")
    result = call_agent(agent_id, query)
    
    return f"🧠 {agents[agent_id]['name']}:\n\n{result}"

# === ТЕСТОВЫЙ ЗАПУСК ===
if __name__ == "__main__":
    # Тест без Telegram
    test_message = "/idea Как монетизировать AI-агентов?"
    print("Тестовый запрос:", test_message)
    print(process_message(test_message))
