import json
import requests
import os
import random
import google.generativeai as genai

# === НАСТРОЙКИ ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "REPLACED")
CHAT_ID = os.getenv("CHAT_ID", "REPLACED")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "REPLACED")

# Настройка Gemini (старая библиотека, но она работает с v1beta)
genai.configure(api_key=GEMINI_API_KEY)

# ПРАВИЛЬНАЯ МОДЕЛЬ — она точно есть в v1beta
model = genai.GenerativeModel('gemini-flash-latest')

# Загружаем конфиг агентов
with open("agents_config.json", "r", encoding="utf-8") as f:
    config = json.load(f)
    agents = {agent["id"]: agent for agent in config["agents"]}

def call_agent(agent_id, user_message):
    agent = agents.get(agent_id)
    if not agent:
        return f"❌ Агент {agent_id} не найден"
    
    prompt = f"{agent['prompt']}\n\nПользователь: {user_message}\n\nОтвет:"
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"⚠️ Ошибка Gemini: {str(e)}"

# === ОСТАЛЬНЫЕ ФУНКЦИИ (без изменений) ===
def send_telegram_message(text, chat_id=CHAT_ID):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    requests.post(url, json=payload)

def get_agent_by_command(text):
    """Определяет агента по команде или ключевым словам"""
    # Сначала проверяем явные команды
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
    
    # Если нет команды — проверяем ключевые слова (регистр не важен)
    text_lower = text.lower()
    
    # Дизайнер
    if any(word in text_lower for word in ["нарисуй", "дизайн", "логотип", "цвет", "стиль", "картинк", "изображени"]):
        return "designer", text
    
    # Стратег
    if any(word in text_lower for word in ["стратеги", "план", "развитие", "перспективы", "будущее", "цель"]):
        return "strategist", text
    
    # Копирайтер
    if any(word in text_lower for word in ["напиши", "текст", "пост", "статья", "стих", "рассказ", "сочини"]):
        return "writer", text
    
    # Разработчик
    if any(word in text_lower for word in ["код", "программа", "скрипт", "функция", "баг", "ошибка", "алгоритм"]):
        return "developer", text
    
    # Исследователь
    if any(word in text_lower for word in ["исследуй", "найди", "данные", "информация", "поиск", "факт"]):
        return "researcher", text
    
    # По умолчанию — Менеджер (он самый универсальный)
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
