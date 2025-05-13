#!/usr/bin/env python
# This is an implementation based on production-ready examples of FastAPI with python-telegram-bot

import logging
import os
from contextlib import asynccontextmanager
from http import HTTPStatus
from typing import Dict, Any

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response, Depends
from openai import OpenAI
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Configure logging - important for production debugging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
# Set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GPTS_MODEL_ID = os.getenv("GPTS_MODEL_ID")

# Validate required environment variables
if not TELEGRAM_TOKEN:
    logger.error("TELEGRAM_TOKEN environment variable is not set!")
    raise ValueError("TELEGRAM_TOKEN environment variable is required")
    
if not OPENAI_API_KEY:
    logger.error("OPENAI_API_KEY environment variable is not set!")
    raise ValueError("OPENAI_API_KEY environment variable is required")
    
if not GPTS_MODEL_ID:
    logger.error("GPTS_MODEL_ID environment variable is not set!")
    raise ValueError("GPTS_MODEL_ID environment variable is required")

# Initialize OpenAI client
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Create bot application
def create_application() -> Application:
    """Create and configure the telegram bot application"""
    application = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .updater(None)  # No updater needed for webhook
        .build()
    )
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    return application

# Context manager for application lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Context manager for FastAPI app.
    This function will run when the app starts and stops.
    """
    # Create bot application when app starts
    app.state.bot_app = create_application()
    
    # Set webhook
    webhook_url = f"https://exist-search.onrender.com/{TELEGRAM_TOKEN}"
    
    # Start the bot
    async with app.state.bot_app:
        await app.state.bot_app.bot.set_webhook(webhook_url)
        logger.info(f"Webhook set to {webhook_url}")
        await app.state.bot_app.start()
        logger.info("Bot started successfully!")
        yield
        await app.state.bot_app.stop()
        logger.info("Bot stopped")

# Initialize FastAPI app
app = FastAPI(
    title="Telegram Bot with GPTS Integration",
    description="Integrates Telegram with GPTS OpenAI models",
    version="1.0.0",
    lifespan=lifespan
)

# Dependency to get application
async def get_application(request: Request) -> Application:
    return request.app.state.bot_app

# Define endpoints
@app.get("/")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "Bot is running!",
        "telegram_token": f"{TELEGRAM_TOKEN[:5]}...{TELEGRAM_TOKEN[-5:]}",
        "gpts_model": GPTS_MODEL_ID
    }

@app.post(f"/{TELEGRAM_TOKEN}")
async def process_update(request: Request, application: Application = Depends(get_application)):
    """Process updates from Telegram"""
    try:
        req_json = await request.json()
        logger.debug(f"Received update: {req_json}")
        
        update = Update.de_json(req_json, application.bot)
        await application.process_update(update)
        
        return Response(status_code=HTTPStatus.OK)
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        # Still return 200 to prevent Telegram from retrying
        return Response(status_code=HTTPStatus.OK)

# Command handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    logger.info(f"Start command from user {user.id} (@{user.username})")
    
    await update.message.reply_text(
        f"Привіт, {user.first_name}! Я бот, що відповідає через налаштовану GPTS-модель. Напишіть будь-яке повідомлення."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        "Просто надішліть мені повідомлення, і я відповім!\n\n"
        "Доступні команди:\n"
        "/start - Почати роботу з ботом\n"
        "/help - Показати цю довідку"
    )

# Message handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user message and send to GPTS."""
    user = update.effective_user
    user_text = update.message.text
    
    logger.info(f"Message from user {user.id} (@{user.username}): {user_text[:30]}...")
    
    # Send "typing" action to show the bot is processing
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    try:
        # Send user text to OpenAI
        response = openai_client.chat.completions.create(
            model=GPTS_MODEL_ID,
            messages=[{"role": "user", "content": user_text}]
        )
        reply = response.choices[0].message.content.strip()
        logger.info(f"GPTS response for user {user.id} (length: {len(reply)} chars)")
        
        # Reply to user
        await update.message.reply_text(reply)
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        await update.message.reply_text("Вибачте, виникла помилка. Спробуйте ще раз пізніше.") 