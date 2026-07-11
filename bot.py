from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
import os
from orchestrator import process_message

TOKEN = os.getenv("TELEGRAM_TOKEN", "7836254185:AAE-qjm_NYrsq6lNyIRH1laKdyWZEcnFZ8g")

async def start(update: Update, context: CallbackContext):
    """Обработчик команды /start"""
    keyboard = [
        [InlineKeyboardButton("🧠 Стратег", callback_data="strategist")],
        [InlineKeyboardButton("🔍 Исследователь", callback_data="researcher")],
        [InlineKeyboardButton("✍️ Копирайтер", callback_data="writer")],
        [InlineKeyboardButton("🎨 Дизайнер", callback_data="designer")],
        [InlineKeyboardButton("💻 Разработчик", callback_data="developer")],
        [InlineKeyboardButton("📊 Менеджер", callback_data="pm")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👋 Привет! Я твой AI-штаб. Выбери агента или просто напиши вопрос.\n\n"
        "Команды: /team, /help",
        reply_markup=reply_markup
    )

async def handle_message(update: Update, context: CallbackContext):
    """Обработка всех текстовых сообщений"""
    user_message = update.message.text
    response = process_message(user_message)
    await update.message.reply_text(response, parse_mode="Markdown")

async def button_callback(update: Update, context: CallbackContext):
    """Обработка нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    agent_id = query.data
    await query.edit_message_text(
        f"🤖 Агент {agent_id} выбран.\n\nНапиши свой запрос прямо в чат."
    )

# === ЗАПУСК БОТА ===
def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("team", start))  # team вызывает то же самое
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("🤖 Бот запущен!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()