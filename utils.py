#!/usr/bin/env python
# Utility functions for the Telegram bot

import logging
import time
import random
import httpx
from typing import Optional, Dict, Any, Callable, TypeVar, Awaitable
from functools import wraps

# Configure logging
logger = logging.getLogger(__name__)

# Type variables for generic functions
T = TypeVar('T')
F = TypeVar('F', bound=Callable[..., Awaitable[Any]])

# Constants
DEFAULT_TIMEOUT = (3.05, 30)  # (connect timeout, read timeout) in seconds
MAX_RETRIES = 3
BASE_RETRY_DELAY = 1  # Base delay in seconds

def with_retry(max_retries: int = MAX_RETRIES, base_delay: float = BASE_RETRY_DELAY) -> Callable[[F], F]:
    """
    Decorator that adds exponential backoff with jitter to async functions.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds before exponential backoff
        
    Returns:
        Decorated function with retry logic
    """
    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            retry_count = 0
            while retry_count <= max_retries:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    retry_count += 1
                    if retry_count > max_retries:
                        logger.error(f"Max retries ({max_retries}) exceeded for {func.__name__}: {str(e)}")
                        raise
                    
                    # Calculate delay with exponential backoff and jitter
                    delay = base_delay * (2 ** (retry_count - 1))
                    jitter = random.uniform(0, 0.1 * delay)  # Add 10% jitter
                    total_delay = delay + jitter
                    
                    logger.warning(f"Retry {retry_count}/{max_retries} for {func.__name__} after {total_delay:.2f}s: {str(e)}")
                    await asyncio.sleep(total_delay)
            
            # This should never be reached due to the raise in the loop
            raise RuntimeError("Unexpected retry loop exit")
        return wrapper
    return decorator

async def make_http_request(
    url: str, 
    method: str = "GET", 
    timeout: tuple[float, float] = DEFAULT_TIMEOUT,
    **kwargs: Any
) -> httpx.Response:
    """
    Make an HTTP request with proper timeout handling.
    
    Args:
        url: URL to request
        method: HTTP method (GET, POST, etc.)
        timeout: Tuple of (connect timeout, read timeout) in seconds
        **kwargs: Additional arguments to pass to httpx
        
    Returns:
        httpx.Response object
        
    Raises:
        httpx.HTTPError: If the request fails
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=url,
                timeout=timeout,
                **kwargs
            )
            response.raise_for_status()
            return response
    except httpx.HTTPError as e:
        logger.error(f"HTTP request failed: {str(e)}")
        raise

def validate_input(text: str, max_length: int = 4000) -> bool:
    """
    Validate user input text.
    
    Args:
        text: Text to validate
        max_length: Maximum allowed length
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not text or not isinstance(text, str):
        return False
    
    if len(text) > max_length:
        return False
    
    # Add more validation as needed
    return True

def format_error_message(error_type: str) -> str:
    """
    Format error messages in Ukrainian.
    
    Args:
        error_type: Type of error
        
    Returns:
        Formatted error message
    """
    error_messages = {
        "RateLimitError": "Вибачте, зараз занадто багато запитів до серверів OpenAI. Будь ласка, спробуйте пізніше.",
        "APIConnectionError": "Вибачте, виникли проблеми зі з'єднанням до серверів OpenAI. Будь ласка, спробуйте пізніше.",
        "APIError": "Вибачте, виникла помилка при обробці вашого запиту. Будь ласка, спробуйте пізніше.",
        "ValidationError": "Вибачте, ваше повідомлення занадто довге або містить неприпустимі символи.",
        "TimeoutError": "Вибачте, запит зайняв занадто багато часу. Будь ласка, спробуйте ще раз.",
        "UnknownError": "Вибачте, виникла невідома помилка. Спробуйте ще раз пізніше."
    }
    
    return error_messages.get(error_type, error_messages["UnknownError"])

# Metrics tracking
class MetricsTracker:
    """Simple metrics tracker for monitoring bot performance."""
    
    def __init__(self):
        self.request_count = 0
        self.error_count = 0
        self.total_processing_time = 0
        self.start_time = time.time()
    
    def record_request(self, processing_time: float, had_error: bool = False) -> None:
        """Record a request and its processing time."""
        self.request_count += 1
        self.total_processing_time += processing_time
        if had_error:
            self.error_count += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics."""
        uptime = time.time() - self.start_time
        return {
            "uptime_seconds": uptime,
            "total_requests": self.request_count,
            "error_rate": self.error_count / max(1, self.request_count),
            "avg_processing_time": self.total_processing_time / max(1, self.request_count),
            "requests_per_minute": (self.request_count / uptime) * 60 if uptime > 0 else 0
        }

# Global metrics tracker
metrics = MetricsTracker() 