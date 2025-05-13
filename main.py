import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
import openai
from flask import Flask, request, jsonify

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GPTS_MODEL_ID = os.getenv("GPTS_MODEL_ID")
openai.api_key = OPENAI_API_KEY

# Log environment variables (without sensitive data)
logger.info(f"Bot initialized with GPTS model: {GPTS_MODEL_ID}")
if TELEGRAM_TOKEN:
    logger.info(f"Telegram token: {TELEGRAM_TOKEN[:5]}...{TELEGRAM_TOKEN[-5:]}")
else:
    logger.error("TELEGRAM_TOKEN is not set!")

# Create Flask app
app = Flask(__name__)

# Start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Start command received from user {update.effective_user.id}")
    await update.message.reply_text(
        "Привіт! Я бот, що відповідає через налаштовану GPTS-модель. Напишіть будь-яке повідомлення."
    )

# Message handler - forwards all user messages to GPTS
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    logger.info(f"Message received: '{user_text}' from user {update.effective_user.id}")
    
    try:
        logger.info(f"Sending request to OpenAI with model {GPTS_MODEL_ID}")
        response = openai.ChatCompletion.create(
            model=GPTS_MODEL_ID,
            messages=[{"role": "user", "content": user_text}]
        )
        reply = response.choices[0].message.content.strip()
        logger.info(f"OpenAI response received (length: {len(reply)})")
        await update.message.reply_text(reply)
    except Exception as e:
        logger.error(f"Error in OpenAI request: {str(e)}")
        await update.message.reply_text("Вибачте, сталася помилка. Спробуйте ще раз пізніше.")

# Initialize bot
bot = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
bot.add_handler(CommandHandler("start", start))
bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# Flask route for health check
@app.route('/')
def health_check():
    logger.info("Health check endpoint called")
    return 'Bot is running!'

# Webhook endpoint for Telegram
@app.route(f'/{TELEGRAM_TOKEN}', methods=['POST'])
def webhook():
    logger.info("Webhook called by Telegram")
    try:
        update = Update.de_json(request.get_json(force=True), bot.bot)
        logger.info(f"Update received: {update}")
        bot.dispatcher.process_update(update)
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return jsonify({"status": "error", "message": str(e)})

# Run Flask app
if __name__ == "__main__":
    # Set webhook
    webhook_url = f"https://exist-search.onrender.com/{TELEGRAM_TOKEN}"
    logger.info(f"Setting webhook to: {webhook_url}")
    try:
        bot.bot.set_webhook(url=webhook_url)
        logger.info("Webhook set successfully")
    except Exception as e:
        logger.error(f"Failed to set webhook: {str(e)}")
    
    # Run Flask app
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Starting Flask app on port {port}")
    app.run(host="0.0.0.0", port=port) 