import os
from datetime import timedelta


class DefaultConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql://ecommerce:ecommerce123@localhost:5432/ecommerce_ai"
    )

    REDIS_URL = os.environ.get("REDIS_URL", "redis://:redispass@localhost:6379/0")
    CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://:redispass@localhost:6379/1")
    CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://:redispass@localhost:6379/2")

    JWT_SECRET = os.environ.get("JWT_SECRET", SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)

    MAX_CONTENT_LENGTH = 50 * 1024 * 1024
    UPLOAD_EXTENSIONS = [".csv", ".xlsx", ".xls", ".json"]

    NLP_MODEL_PATH = os.environ.get("NLP_MODEL_PATH", "nlp/data/models")
    NLP_DEFAULT_MODEL = os.environ.get("NLP_DEFAULT_MODEL", "bert-base-chinese")
    NLP_DEVICE = os.environ.get("NLP_DEVICE", "cpu")
    NLP_MAX_LENGTH = int(os.environ.get("NLP_MAX_LENGTH", "128"))
    NLP_CACHE_TTL = int(os.environ.get("NLP_CACHE_TTL", "86400"))

    RATELIMIT_ENABLED = os.environ.get("RATELIMIT_ENABLED", "true").lower() == "true"
    RATELIMIT_DEFAULT = "200 per day; 50 per hour"

    CELERY_TASK_ACKS_LATE = True
    CELERY_TASK_REJECT_ON_WORKER_LOST = True
    CELERY_TASK_SERIALIZER = "json"
    CELERY_RESULT_SERIALIZER = "json"
    CELERY_ACCEPT_CONTENT = ["json"]
    CELERY_TASK_MAX_RETRIES = 3
    CELERY_TASK_MAX_TASKS_PER_CHILD = 100
    CELERY_BROKER_TRANSPORT_OPTIONS = {
        "max_retries": 3,
        "interval_start": 0,
        "interval_step": 0.2,
        "interval_max": 0.5,
    }
    CELERY_BEAT_SCHEDULE = {
        "check-timeout-tasks": {
            "task": "app.tasks.analysis_tasks.check_timeout_tasks",
            "schedule": 300,
        },
        "check-crawl-timeouts": {
            "task": "app.tasks.crawl_tasks.check_crawl_timeouts",
            "schedule": 300,
        },
        "schedule-due-crawls": {
            "task": "app.tasks.crawl_tasks.schedule_due_crawls",
            "schedule": 60,
        },
    }

    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    LOG_FILE = os.environ.get("LOG_FILE", "logs/app.log")
