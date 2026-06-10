"""Crawl task model — separate from AnalysisTask.

Lifecycle: pending → crawling → filtering → completed
                                    → failed
States: pending | crawling | filtering | completed | failed
"""
import datetime
from app.extensions import db


def utcnow():
    return datetime.datetime.now(datetime.UTC)


class CrawlTask(db.Model):
    __tablename__ = "crawl_tasks"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True)

    # Task identity
    name = db.Column(db.String(256), nullable=False)
    platform = db.Column(db.String(32), nullable=False, default="jd")
    url = db.Column(db.String(1024), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")

    # Pagination control
    page_limit = db.Column(db.Integer, default=5)
    total_pages = db.Column(db.Integer, default=0)
    current_page = db.Column(db.Integer, default=0)

    # Scheduling
    schedule_interval = db.Column(db.Integer, default=0)  # minutes (0 = manual)
    last_run_at = db.Column(db.DateTime)
    next_run_at = db.Column(db.DateTime)

    # Results
    items_found = db.Column(db.Integer, default=0)
    items_new = db.Column(db.Integer, default=0)
    items_failed = db.Column(db.Integer, default=0)
    error_message = db.Column(db.Text)
    result_summary = db.Column(db.JSON)

    # Celery tracking
    celery_task_id = db.Column(db.String(128))

    # Timestamps
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)

    __table_args__ = (
        db.Index("idx_crawl_user_status", "user_id", "status"),
        db.Index("idx_crawl_platform_status", "platform", "status"),
        db.Index("idx_crawl_next_run", "next_run_at"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "product_id": self.product_id,
            "name": self.name,
            "platform": self.platform,
            "url": self.url,
            "status": self.status,
            "page_limit": self.page_limit,
            "total_pages": self.total_pages,
            "current_page": self.current_page,
            "schedule_interval": self.schedule_interval,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
            "items_found": self.items_found,
            "items_new": self.items_new,
            "items_failed": self.items_failed,
            "error_message": self.error_message,
            "result_summary": self.result_summary,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    def can_start(self) -> bool:
        return self.status in ("pending", "failed")

    def is_running(self) -> bool:
        return self.status in ("crawling", "filtering")

    def is_terminal(self) -> bool:
        return self.status in ("completed", "failed")
