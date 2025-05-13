#!/usr/bin/env python
# OpenAI client module for the Telegram bot

import logging
import os
from typing import Optional, Dict, Any, List
import time

from openai import OpenAI
from dotenv import load_dotenv

from utils import with_retry, format_error_message, metrics

# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GPTS_MODEL_ID = os.getenv("GPTS_MODEL_ID")

# Validate required environment variables
if not OPENAI_API_KEY:
    logger.error("OPENAI_API_KEY environment variable is not set!")
    raise ValueError("OPENAI_API_KEY environment variable is required")
    
if not GPTS_MODEL_ID:
    logger.error("GPTS_MODEL_ID environment variable is not set!")
    raise ValueError("GPTS_MODEL_ID environment variable is required")

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY, default_headers={"OpenAI-Beta": "assistants=v2"})

# Better error handling for different OpenAI versions
# Create fallback error classes that we'll use if imports fail
class BaseAPIError(Exception): pass
class BaseRateLimitError(Exception): pass
class BaseAPIConnectionError(Exception): pass

# Try to import from different potential locations based on OpenAI version
try:
    # Newer versions of OpenAI SDK (>=1.0.0)
    from openai.types.error import APIError, RateLimitError, APIConnectionError
    logging.info("Successfully imported OpenAI error types from openai.types.error")
except ImportError:
    try:
        # Older versions of OpenAI SDK
        from openai.error import APIError, RateLimitError, APIConnectionError
        logging.info("Successfully imported OpenAI error types from openai.error")
    except ImportError:
        # Fallback to our predefined classes if neither import works
        logging.warning("Could not import specific OpenAI error types, using fallback error classes")
        # Assign our base classes to the expected names
        APIError = BaseAPIError
        RateLimitError = BaseRateLimitError
        APIConnectionError = BaseAPIConnectionError

@with_retry(max_retries=3, base_delay=1)
async def generate_response(text: str) -> str:
    """
    Generate a response from the OpenAI Assistant (Assistants API).
    """
    import asyncio
    start_time = time.time()
    had_error = False

    try:
        # 1. Створити thread
        thread = client.beta.threads.create()

        # 2. Додати повідомлення
        client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=text
        )

        # 3. Запустити асистента
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=GPTS_MODEL_ID
        )

        # 4. Дочекатися завершення run (polling)
        while run.status not in ["completed", "failed"]:
            await asyncio.sleep(1)
            run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)

        if run.status == "failed":
            raise Exception("Assistant run failed")

        # 5. Отримати відповідь
        messages = client.beta.threads.messages.list(thread_id=thread.id)
        # Беремо останнє повідомлення від асистента
        reply = None
        for msg in reversed(messages.data):
            if msg.role == "assistant":
                reply = msg.content[0].text.value
                break
        if not reply:
            reply = "Вибачте, не вдалося отримати відповідь від асистента."

        processing_time = time.time() - start_time
        logger.info(f"Assistant response (length: {len(reply)} chars, time: {processing_time:.2f}s)")
        metrics.record_request(processing_time)
        return reply

    except Exception as e:
        had_error = True
        logger.error(f"Unexpected error in generate_response: {str(e)}", exc_info=True)
        processing_time = time.time() - start_time
        metrics.record_request(processing_time, had_error=True)
        raise APIError(f"Unexpected error: {str(e)}") 