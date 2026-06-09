import datetime
from app.extensions import db


def utcnow():
    """Column-default-friendly wrapper for timezone-aware UTC now."""
    return datetime.datetime.now(datetime.UTC)


class AnalysisTask(db.Model):
    __tablename__ = "analysis_tasks"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    name = db.Column(db.String(256), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")
    # pending | processing | completed | failed | completed_with_errors
    total_count = db.Column(db.Integer, default=0)
    processed_count = db.Column(db.Integer, default=0)
    failed_count = db.Column(db.Integer, default=0)
    error_count = db.Column(db.Integer, default=0)
    timeout_at = db.Column(db.DateTime)
    result_summary = db.Column(db.JSON)
    celery_task_id = db.Column(db.String(128))
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)
    completed_at = db.Column(db.DateTime)

    # Relationships
    analyses = db.relationship("CommentAnalysis", backref="task", lazy="dynamic")

    __table_args__ = (
        db.Index("idx_tasks_user_status", "user_id", "status"),
        db.Index("idx_results_task", "id"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "status": self.status,
            "total_count": self.total_count,
            "processed_count": self.processed_count,
            "failed_count": self.failed_count,
            "result_summary": self.result_summary,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
