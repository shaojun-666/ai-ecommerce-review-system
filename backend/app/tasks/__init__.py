"""Celery app initialization."""
from celery import Celery
from app.config import get_config

from celery.schedules import crontab

config = get_config()

celery_app = Celery(
    "ecommerce_tasks",
    broker=config.CELERY_BROKER_URL,
    backend=config.CELERY_RESULT_BACKEND,
    task_acks_late=config.CELERY_TASK_ACKS_LATE,
    task_reject_on_worker_lost=config.CELERY_TASK_REJECT_ON_WORKER_LOST,
    task_track_started=config.CELERY_TASK_TRACK_STARTED,
    task_serializer=config.CELERY_TASK_SERIALIZER,
    result_serializer=config.CELERY_RESULT_SERIALIZER,
    accept_content=config.CELERY_ACCEPT_CONTENT,
)

celery_app.conf.beat_schedule = {
    "snapshot-prices-every-6-hours": {
        "task": "app.tasks.crawl_tasks.snapshot_prices",
        "schedule": crontab(hour="*/6", minute="13"),
    },
    "check-crawl-timeouts": {
        "task": "app.tasks.crawl_tasks.check_crawl_timeouts",
        "schedule": crontab(minute="*/15"),
    },
    "schedule-due-crawls": {
        "task": "app.tasks.crawl_tasks.schedule_due_crawls",
        "schedule": crontab(minute="*/5"),
    },
}

from app.tasks import analysis_tasks  # noqa: E402, F401
from app.tasks import crawl_tasks  # noqa: E402, F401
