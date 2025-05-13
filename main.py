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
from openai import OpenAI
# Безпечний імпорт помилок OpenAI, сумісний з різними версіями
try:
    from openai.types.error import APIError, RateLimitError, APIConnectionError
except ImportError:
    # Створюємо фіктивні класи для старіших версій або якщо модулі недоступні
    class APIError(Exception): pass
    class RateLimitError(Exception): pass
    class APIConnectionError(Exception): pass
    logging.warning("Could not import specific OpenAI error types, using fallback error classes")

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
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get("https://exist-search.onrender.com/")
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
    
    start_time = time.time()
    max_retries = 2
    retry_count = 0
    
    while retry_count <= max_retries:
        try:
            # Send user text to OpenAI with error handling for different versions
            try:
                # Try the newer version with timeout parameter
                response = openai_client.chat.completions.create(
                    model=GPTS_MODEL_ID,
                    messages=[{"role": "user", "content": user_text}],
                    timeout=60  # 60 second timeout
                )
            except TypeError:
                # Fallback for older versions that don't support timeout parameter
                logger.warning("OpenAI client doesn't support timeout parameter, using without timeout")
                response = openai_client.chat.completions.create(
                    model=GPTS_MODEL_ID,
                    messages=[{"role": "user", "content": user_text}]
                )
                
            reply = response.choices[0].message.content.strip()
            processing_time = time.time() - start_time
            logger.info(f"GPTS response for user {user.id} (length: {len(reply)} chars, time: {processing_time:.2f}s)")
            
            # Reply to user
            await update.message.reply_text(reply)
            return
        
        except (APIError, RateLimitError, APIConnectionError) as specific_error:
            # Обробка відомих помилок OpenAI API
            error_type = type(specific_error).__name__
            logger.error(f"OpenAI {error_type}: {str(specific_error)}")
            
            if isinstance(specific_error, RateLimitError) or isinstance(specific_error, APIConnectionError):
                if retry_count < max_retries:
                    retry_count += 1
                    wait_time = 2 * (retry_count) # Збільшуємо час очікування з кожною спробою
                    logger.info(f"Retrying after {wait_time}s (attempt {retry_count} of {max_retries})")
                    time.sleep(wait_time)
                    continue
            
            # Якщо це остання спроба або помилка не підлягає повторним спробам
            error_messages = {
                "RateLimitError": "Вибачте, зараз занадто багато запитів до серверів OpenAI. Будь ласка, спробуйте пізніше.",
                "APIConnectionError": "Вибачте, виникли проблеми зі з'єднанням до серверів OpenAI. Будь ласка, спробуйте пізніше.",
                "APIError": "Вибачте, виникла помилка при обробці вашого запиту. Будь ласка, спробуйте пізніше."
            }
            await update.message.reply_text(error_messages.get(error_type, "Вибачте, виникла помилка. Спробуйте ще раз пізніше."))
            return
            
        except Exception as e:
            logger.error(f"Unexpected error processing message: {str(e)}", exc_info=True)
            await update.message.reply_text(
                "Вибачте, виникла помилка. Спробуйте ще раз пізніше або змініть ваш запит."
            )
            return 