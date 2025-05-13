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
client = OpenAI(api_key=OPENAI_API_KEY)

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
    Generate a response from the OpenAI GPTS model.
    
    Args:
        text: User input text
        
    Returns:
        Generated response text
        
    Raises:
        APIError: If the API request fails
        RateLimitError: If rate limit is exceeded
        APIConnectionError: If connection to API fails
    """
    start_time = time.time()
    had_error = False
    
    try:
        # Try the newer version with timeout parameter
        try:
            response = client.chat.completions.create(
                model=GPTS_MODEL_ID,
                messages=[{"role": "user", "content": text}],
                timeout=60  # 60 second timeout
            )
        except TypeError:
            # Fallback for older versions that don't support timeout parameter
            logger.warning("OpenAI client doesn't support timeout parameter, using without timeout")
            response = client.chat.completions.create(
                model=GPTS_MODEL_ID,
                messages=[{"role": "user", "content": text}]
            )
            
        reply = response.choices[0].message.content.strip()
        processing_time = time.time() - start_time
        logger.info(f"GPTS response (length: {len(reply)} chars, time: {processing_time:.2f}s)")
        
        # Record successful request
        metrics.record_request(processing_time)
        
        return reply
    
    except (APIError, RateLimitError, APIConnectionError) as e:
        had_error = True
        error_type = type(e).__name__
        logger.error(f"OpenAI {error_type}: {str(e)}")
        
        # Record failed request
        processing_time = time.time() - start_time
        metrics.record_request(processing_time, had_error=True)
        
        # Re-raise the exception for the retry decorator to handle
        raise
    
    except Exception as e:
        had_error = True
        logger.error(f"Unexpected error in generate_response: {str(e)}", exc_info=True)
        
        # Record failed request
        processing_time = time.time() - start_time
        metrics.record_request(processing_time, had_error=True)
        
        # Convert to APIError for consistent handling
        raise APIError(f"Unexpected error: {str(e)}") 