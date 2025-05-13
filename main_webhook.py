#!/usr/bin/env python
# This example is based on the customwebhookbot.py example from python-telegram-bot

import logging
import os
from dotenv import load_dotenv
from openai import OpenAI

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# Set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GPTS_MODEL_ID = os.getenv("GPTS_MODEL_ID")

# Initialize OpenAI client
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Command handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        "Привіт! Я бот, що відповідає через налаштовану GPTS-модель. Напишіть будь-яке повідомлення."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text("Просто надішліть мені повідомлення, і я відповім!")

# Message handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user message and send to GPTS."""
    user_text = update.message.text
    
    try:
        # Send user text to OpenAI
        logger.info(f"Sending message to OpenAI: {user_text[:30]}...")
        response = openai_client.chat.completions.create(
            model=GPTS_MODEL_ID,
            messages=[{"role": "user", "content": user_text}]
        )
        reply = response.choices[0].message.content.strip()
        logger.info(f"Received response from OpenAI ({len(reply)} chars)")
        
        # Reply to user
        await update.message.reply_text(reply)
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        await update.message.reply_text("Вибачте, виникла помилка. Спробуйте ще раз пізніше.")

def main() -> None:
    """Set up the application and a custom webhook."""
    
    # Define your Render.com URL
    webhook_url = f"https://exist-search.onrender.com/{TELEGRAM_TOKEN}"
    
    # Create the Application
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Register handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Set the webhook
    application.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
        webhook_url=webhook_url,
        secret_token=None,  # Optional: set a token to authenticate the webhook
    )

if __name__ == "__main__":
    main() 