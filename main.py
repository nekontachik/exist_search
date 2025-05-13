import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
import openai
from flask import Flask

# Load environment variables
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GPTS_MODEL_ID = os.getenv("GPTS_MODEL_ID")
openai.api_key = OPENAI_API_KEY

# Create Flask app
app = Flask(__name__)

# Start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привіт! Я бот, що відповідає через налаштовану GPTS-модель. Напишіть будь-яке повідомлення."
    )

# Message handler - forwards all user messages to GPTS
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    response = openai.ChatCompletion.create(
        model=GPTS_MODEL_ID,
        messages=[{"role": "user", "content": user_text}]
    )
    reply = response.choices[0].message.content.strip()
    await update.message.reply_text(reply)

# Initialize bot
bot = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
bot.add_handler(CommandHandler("start", start))
bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# Flask route for health check
@app.route('/')
def health_check():
    return 'Bot is running!'

# Webhook mode startup
if __name__ == "__main__":
    bot.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
        webhook_url=f"https://exist-search.onrender.com/{TELEGRAM_TOKEN}"
    ) 