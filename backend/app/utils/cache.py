"""Redis cache utilities with graceful degradation."""
import json
import logging
from functools import wraps
from typing import Any, Callable, Optional

from app.extensions import get_redis

logger = logging.getLogger(__name__)


def _serialize(data: Any) -> str:
    """Serialize data to JSON string."""
    return json.dumps(data, ensure_ascii=False, default=str)


def cache_get(key: str) -> Optional[Any]:
    """Get cached value by key. Returns deserialized data or None."""
    redis = get_redis()
    if not redis:
        return None
    try:
        val = redis.get(key)
        return json.loads(val) if val else None
    except Exception as e:
        logger.debug("Cache GET failed for %s: %s", key, e)
        return None


def cache_set(key: str, data: Any, ttl: int = 300) -> bool:
    """Set cached value with TTL (seconds). Returns True on success."""
    redis = get_redis()
    if not redis:
        return False
    try:
        redis.setex(key, ttl, _serialize(data))
        return True
    except Exception as e:
        logger.debug("Cache SET failed for %s: %s", key, e)
        return False


def cache_delete(key: str) -> bool:
    """Delete a single cache key."""
    redis = get_redis()
    if not redis:
        return False
    try:
        redis.delete(key)
        return True
    except Exception as e:
        logger.debug("Cache DELETE failed for %s: %s", key, e)
        return False


def cache_delete_pattern(pattern: str) -> bool:
    """Delete all keys matching a glob pattern (e.g. 'dashboard:*')."""
    redis = get_redis()
    if not redis:
        return False
    try:
        keys = redis.keys(pattern)
        if keys:
            redis.delete(*keys)
        return True
    except Exception as e:
        logger.debug("Cache DELETE pattern failed for %s: %s", pattern, e)
        return False


def cache_push_list(key: str, value: Any, max_len: int = 200) -> bool:
    """Push value to a Redis list (LPUSH), trim to max_len."""
    redis = get_redis()
    if not redis:
        return False
    try:
        redis.lpush(key, _serialize(value))
        redis.ltrim(key, 0, max_len - 1)
        return True
    except Exception as e:
        logger.debug("Cache LPUSH failed for %s: %s", key, e)
        return False


def cache_get_list(key: str, start: int = 0, end: int = -1) -> list:
    """Get range of items from a Redis list."""
    redis = get_redis()
    if not redis:
        return []
    try:
        items = redis.lrange(key, start, end)
        return [json.loads(item) for item in items]
    except Exception as e:
        logger.debug("Cache LRANGE failed for %s: %s", key, e)
        return []


def cached(ttl: int = 300):
    """Decorator: cache function return value in Redis.

    The cache key is derived from the function name and positional args.
    Usage:
        @cached(ttl=300)
        def get_overview():
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            redis = get_redis()
            if not redis:
                return func(*args, **kwargs)

            # Build cache key: func_name:arg1:arg2:...
            key_parts = [func.__name__]
            key_parts.extend(str(a) for a in args)
            key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
            key = ":".join(key_parts)

            try:
                cached_val = redis.get(key)
                if cached_val is not None:
                    return json.loads(cached_val)
            except Exception as e:
                logger.debug("Cache miss for %s: %s", key, e)

            result = func(*args, **kwargs)
            try:
                redis.setex(key, ttl, _serialize(result))
            except Exception as e:
                logger.debug("Cache SET failed in decorator: %s", e)
            return result
        return wrapper
    return decorator
