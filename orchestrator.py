import json
import requests
import random
import os
from datetime import datetime

# === НАСТРОЙКИ ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "REPLACED")
CHAT_ID = os.getenv("CHAT_ID", "REPLACED")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-9ecf872eceb74eab94c342dcce9016fe")  # Бесплатно на platform.deepseek.com

# Загружаем конфиг
with open("agents_config.json", "r", encoding="utf-8") as f:
    config = json.load(f)
    agents = {agent["id"]: agent for agent in config["agents"]}

def call_agent(agent_id, user_message):
    agent = agents.get(agent_id)
    if not agent:
        return f"❌ Агент {agent_id} не найден"
    
    prompt = f"{agent['prompt']}\n\nПользователь: {user_message}\n\nОтвет:"
    
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
            return f"⚠️ Ошибка API (код {response.status_code}): {response.text[:200]}"
        
        # Парсим JSON
        result = response.json()
        
        # Проверяем наличие 'choices'
        if "choices" not in result or not result["choices"]:
            return f"⚠️ API вернул неожиданный ответ: {json.dumps(result, ensure_ascii=False)[:200]}"
        
        # Возвращаем текст ответа
        return result["choices"][0]["message"]["content"]
        
    except requests.exceptions.Timeout:
        return "⚠️ Превышено время ожидания ответа от API. Попробуй позже."
    except requests.exceptions.RequestException as e:
        return f"⚠️ Ошибка сети: {str(e)[:100]}"
    except Exception as e:
        return f"⚠️ Неизвестная ошибка: {str(e)[:100]}"
def send_telegram_message(text, chat_id=CHAT_ID):
    """Отправляет сообщение в Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    requests.post(url, json=payload)

def get_agent_by_command(text):
    """Определяет агента по команде или ключевым словам"""
    command_map = {
        "/strategy": "strategist",
        "/research": "researcher",
        "/write": "writer",
        "/design": "designer",
        "/code": "developer",
        "/pm": "pm",
        "/idea": "strategist",
        "/help": "pm"
    }
    
    for cmd, agent_id in command_map.items():
        if text.startswith(cmd):
            return agent_id, text[len(cmd):].strip()
    
    text_lower = text.lower()
    if any(word in text_lower for word in ["нарисуй", "дизайн", "логотип", "цвет", "стиль"]):
        return "designer", text
    if any(word in text_lower for word in ["стратеги", "план", "развитие"]):
        return "strategist", text
    if any(word in text_lower for word in ["напиши", "текст", "пост", "статья", "стих"]):
        return "writer", text
    if any(word in text_lower for word in ["код", "программа", "скрипт", "функция"]):
        return "developer", text
    if any(word in text_lower for word in ["исследуй", "найди", "данные"]):
        return "researcher", text
    
    return "pm", text

def process_message(message_text):
    if message_text.lower() in ["/start", "привет", "здарова", "хай"]:
        team_list = "\n".join([f"{a['name']} — {a['role']}" for a in config["agents"]])
        return f"👋 Привет! Я твой штаб AI-агентов.\n\nВот моя команда:\n{team_list}\n\nПросто напиши вопрос или выбери агента:\n/strategy — стратегия\n/research — исследование\n/write — написать текст\n/design — дизайн\n/code — код\n/pm — задачи"

    if message_text.lower() in ["/team", "/agents", "/команда"]:
        team_list = "\n".join([f"{a['name']} — {a['role']}" for a in config["agents"]])
        return f"🤖 Моя команда:\n\n{team_list}\n\nНапиши вопрос, и я вызову подходящего агента!"

    agent_id, query = get_agent_by_command(message_text)

    if not query:
        return f"🤔 Агент {agents[agent_id]['name']} ждёт твоего вопроса."

    send_telegram_message(f"🤖 {agents[agent_id]['name']} обрабатывает запрос...")
    result = call_agent(agent_id, query)

    return f"🧠 {agents[agent_id]['name']}:\n\n{result}"


