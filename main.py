#!/usr/bin/env python
# This is an implementation based on production-ready examples of FastAPI with python-telegram-bot

import logging
import os
from contextlib import asynccontextmanager
from http import HTTPStatus
from typing import Dict, Any, Optional
import time
import asyncio
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response, Depends
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from utils import (
    make_http_request, 
    validate_input, 
    format_error_message, 
    metrics,
    DEFAULT_TIMEOUT
)
from openai_client import (
    generate_response, 
    APIError, 
    RateLimitError, 
    APIConnectionError
)

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
WEBHOOK_BASE_URL = os.getenv("WEBHOOK_URL", "https://exist-search.onrender.com")

# Validate required environment variables
if not TELEGRAM_TOKEN:
    logger.error("TELEGRAM_TOKEN environment variable is not set!")
    raise ValueError("TELEGRAM_TOKEN environment variable is required")

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
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Add periodic job to keep service alive
    # Check if job_queue is available (might not be in some environments)
    try:
        if hasattr(application, 'job_queue') and application.job_queue:
            application.job_queue.run_repeating(keep_alive_ping, interval=840, first=10)
            logger.info("Scheduled keep-alive ping job")
        else:
            logger.warning("Job queue is not available, skipping keep-alive ping setup")
    except Exception as e:
        logger.error(f"Error setting up job queue: {str(e)}")
    
    return application

# Periodic job to keep the service alive
async def keep_alive_ping(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ping self to keep the service alive on free tier."""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"Sending keep-alive ping at {current_time}")
    try:
        # Self ping the health check endpoint
        response = await make_http_request(f"{WEBHOOK_BASE_URL}/", timeout=DEFAULT_TIMEOUT)
        logger.info(f"Keep-alive ping response: {response.status_code}")
    except Exception as e:
        logger.error(f"Error in keep-alive ping: {str(e)}")

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
    webhook_url = f"{WEBHOOK_BASE_URL}/{TELEGRAM_TOKEN}"
    
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
        "metrics": metrics.get_metrics()
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
        "/help - Показати цю довідку\n"
        "/status - Показати статус бота"
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message with bot status metrics."""
    user = update.effective_user
    logger.info(f"Status command from user {user.id} (@{user.username})")
    
    # Get metrics
    bot_metrics = metrics.get_metrics()
    
    # Format uptime
    uptime_seconds = bot_metrics["uptime_seconds"]
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{int(hours)}г {int(minutes)}хв {int(seconds)}с"
    
    # Format message
    status_message = (
        f"📊 Статус бота:\n\n"
        f"⏱ Час роботи: {uptime_str}\n"
        f"📨 Всього запитів: {bot_metrics['total_requests']}\n"
        f"⚠️ Помилок: {int(bot_metrics['error_rate'] * 100)}%\n"
        f"⚡️ Середній час відповіді: {bot_metrics['avg_processing_time']:.2f}с\n"
        f"📈 Запитів за хвилину: {bot_metrics['requests_per_minute']:.1f}"
    )
    
    await update.message.reply_text(status_message)

# Message handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user message and send to GPTS."""
    user = update.effective_user
    user_text = update.message.text
    
    logger.info(f"Message from user {user.id} (@{user.username}): {user_text[:30]}...")
    
    # Validate input
    if not validate_input(user_text):
        await update.message.reply_text(format_error_message("ValidationError"))
        return
    
    # Send "typing" action to show the bot is processing
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    try:
        # Generate response from OpenAI
        reply = await generate_response(user_text)
        
        # Reply to user
        await update.message.reply_text(reply)
        
    except (APIError, RateLimitError, APIConnectionError) as e:
        # Handle known OpenAI API errors
        error_type = type(e).__name__
        await update.message.reply_text(format_error_message(error_type))
        
    except Exception as e:
        # Handle unexpected errors
        logger.error(f"Unexpected error processing message: {str(e)}", exc_info=True)
        await update.message.reply_text(format_error_message("UnknownError")) 