"""Flask extensions initialization."""
import logging
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from redis import Redis

logger = logging.getLogger(__name__)

db = SQLAlchemy()
migrate = Migrate()

_redis: Redis | None = None


def init_redis(app) -> Redis | None:
    """Lazily initialize Redis client from app config.

    Returns None if Redis URL is not configured or connection fails,
    allowing graceful degradation.
    """
    global _redis
    try:
        url = app.config.get("REDIS_URL", "redis://localhost:6379/0")
        _redis = Redis.from_url(url, decode_responses=True, socket_connect_timeout=2)
        _redis.ping()
        logger.info("Redis connected: %s", url)
    except Exception as e:
        logger.warning("Redis unavailable, caching disabled: %s", e)
        _redis = None
    return _redis


def get_redis() -> Redis | None:
    """Get the global Redis client. Returns None if Redis is unavailable."""
    return _redis
