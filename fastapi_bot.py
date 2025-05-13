#!/usr/bin/env python
# This is an implementation based on the article about FastAPI and python-telegram-bot v20+

from contextlib import asynccontextmanager
from http import HTTPStatus
import os
from dotenv import load_dotenv
import logging
from openai import OpenAI

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from fastapi import FastAPI, Request, Response

# Configure logging
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

# Initialize python telegram bot application
ptb = (
    Application.builder()
    .updater(None)  # No updater needed for webhook
    .token(TELEGRAM_TOKEN)
    .read_timeout(7)
    .get_updates_read_timeout(42)
    .build()
)

@asynccontextmanager
async def lifespan(_: FastAPI):
    """
    Context manager for FastAPI app.
    This function will run when the app starts and stops.
    """
    # Set webhook when app starts
    webhook_url = f"https://exist-search.onrender.com/{TELEGRAM_TOKEN}"
    await ptb.bot.setWebhook(webhook_url)
    logger.info(f"Webhook set to {webhook_url}")
    
    # Start the bot
    async with ptb:
        await ptb.start()
        logger.info("Bot started!")
        yield
        await ptb.stop()
        logger.info("Bot stopped!")

# Initialize FastAPI app
app = FastAPI(lifespan=lifespan)

# Define endpoints
@app.get("/")
async def health_check():
    """Health check endpoint"""
    return {"status": "Bot is running!"}

@app.post(f"/{TELEGRAM_TOKEN}")
async def process_update(request: Request):
    """Process updates from Telegram"""
    req = await request.json()
    update = Update.de_json(req, ptb.bot)
    await ptb.process_update(update)
    return Response(status_code=HTTPStatus.OK)

# Command handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    logger.info(f"Start command from user {update.effective_user.id}")
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

# Register handlers
ptb.add_handler(CommandHandler("start", start_command))
ptb.add_handler(CommandHandler("help", help_command))
ptb.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)) 