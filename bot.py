import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
    CallbackQueryHandler  # <-- ЭТОТ ИМПОРТ БЫЛ ПРОПУЩЕН!
)
from orchestrator import process_message
# Настройка логов
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_TOKEN", "REPLACED")

async def start(update: Update, context: CallbackContext):
    """Кнопки выбора агента"""
    keyboard = [
        [InlineKeyboardButton("🧠 Стратег", callback_data="strategist")],
        [InlineKeyboardButton("🔍 Исследователь", callback_data="researcher")],
        [InlineKeyboardButton("✍️ Копирайтер", callback_data="writer")],
        [InlineKeyboardButton("🎨 Дизайнер", callback_data="designer")],
        [InlineKeyboardButton("💻 Разработчик", callback_data="developer")],
        [InlineKeyboardButton("📊 Менеджер", callback_data="pm")]
    ]
    await update.message.reply_text(
        "👋 Привет! Я твой AI-штаб.\nВыбери агента или просто напиши вопрос.\n\n/team — показать команду",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
async def send_long_message(update: Update, text: str):
    """Отправляет длинное сообщение, разбивая на части при необходимости"""
    MAX_LENGTH = 4000  # Чуть меньше лимита Telegram (4096)
    
    # Если текст короткий — отправляем как есть
    if len(text) <= MAX_LENGTH:
        await update.message.reply_text(text)
        return
    
    # Если длинный — разбиваем по предложениям
    parts = []
    current_part = ""
    
    for sentence in text.split('. '):
        if len(current_part) + len(sentence) + 2 <= MAX_LENGTH:
            current_part += sentence + '. '
        else:
            parts.append(current_part.strip())
            current_part = sentence + '. '
    
    if current_part:
        parts.append(current_part.strip())
    
    # Отправляем все части по очереди
    for part in parts:
        await update.message.reply_text(part)

async def handle_message(update: Update, context: CallbackContext):
    user_message = update.message.text
    response = process_message(user_message)
    
    # Используем новую функцию для отправки
    await send_long_message(update, response)

async def button_callback(update: Update, context: CallbackContext):
    """Кнопка выбрана — просим написать запрос"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"🤖 Агент {query.data} выбран.\nНапиши свой запрос прямо сюда."
    )

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("team", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))  # <-- Теперь работает!
    
    print("🤖 Бот запущен и слушает сообщения...")
    app.run_polling()

if __name__ == "__main__":
    main()
