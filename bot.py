import os
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

TOKEN = os.getenv("TELEGRAM_TOKEN", "7836254185:AAE-qjm_NYrsq6lNyIRH1laKdyWZEcnFZ8g")

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

async def handle_message(update: Update, context: CallbackContext):
    """Обрабатывает текстовые сообщения"""
    user_message = update.message.text
    response = process_message(user_message)
    await update.message.reply_text(response, parse_mode="Markdown")

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
