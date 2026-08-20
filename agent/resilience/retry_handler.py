"""Vertex AI Rate Limit (429) & Resilience Retry Handler.

Implements exponential backoff with full jitter to protect against quota bursts
and transient Vertex AI 429 / ResourceExhausted rate limit exceptions.
"""

import asyncio
import functools
import logging
import random
import time
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)
T = TypeVar("T")


def with_exponential_backoff(
    max_retries: int = 4,
    base_delay_seconds: float = 1.0,
    max_delay_seconds: float = 16.0,
    retryable_exceptions: tuple = (Exception,),
):
    """Decorator applying exponential backoff with full jitter to async and sync functions."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> T:
                attempt = 0
                while True:
                    try:
                        return await func(*args, **kwargs)
                    except retryable_exceptions as e:
                        err_str = str(e).lower()
                        is_rate_limit = "429" in err_str or "resource_exhausted" in err_str or "quota" in err_str
                        if attempt >= max_retries or not is_rate_limit:
                            raise e
                        attempt += 1
                        delay = min(max_delay_seconds, base_delay_seconds * (2 ** attempt))
                        jittered_delay = delay * random.uniform(0.8, 1.2)
                        logger.warning(f"Vertex AI 429 rate limit encountered. Retrying in {jittered_delay:.2f}s (Attempt {attempt}/{max_retries})...")
                        await asyncio.sleep(jittered_delay)
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> T:
                attempt = 0
                while True:
                    try:
                        return func(*args, **kwargs)
                    except retryable_exceptions as e:
                        err_str = str(e).lower()
                        is_rate_limit = "429" in err_str or "resource_exhausted" in err_str or "quota" in err_str
                        if attempt >= max_retries or not is_rate_limit:
                            raise e
                        attempt += 1
                        delay = min(max_delay_seconds, base_delay_seconds * (2 ** attempt))
                        jittered_delay = delay * random.uniform(0.8, 1.2)
                        logger.warning(f"Vertex AI 429 rate limit encountered. Retrying in {jittered_delay:.2f}s (Attempt {attempt}/{max_retries})...")
                        time.sleep(jittered_delay)
            return sync_wrapper

    return decorator
