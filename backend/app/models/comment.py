import datetime
from app.extensions import db


def utcnow():
    """Column-default-friendly wrapper for timezone-aware UTC now."""
    return datetime.datetime.now(datetime.timezone.utc)


class Comment(db.Model):
    __tablename__ = "comments"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    content = db.Column(db.Text, nullable=False)
    content_hash = db.Column(db.String(64), index=True)  # SHA-256 for dedup
    rating = db.Column(db.SmallInteger)  # 1-5
    author_name = db.Column(db.String(100), default="")
    platform = db.Column(db.String(50), default="")
    source = db.Column(db.String(50), default="import")
    purchase_time = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    analysis = db.relationship("CommentAnalysis", backref="comment", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        db.Index("idx_comments_product_created", "product_id", "created_at"),
        db.Index("idx_comments_rating", "rating"),
        db.Index("idx_comments_hash_product", "content_hash", "product_id"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "product_id": self.product_id,
            "content": self.content[:200] if self.content else "",
            "rating": self.rating,
            "author_name": self.author_name,
            "platform": self.platform,
            "source": self.source,
            "purchase_time": self.purchase_time.isoformat() if self.purchase_time else None,
            "created_at": self.created_at.isoformat(),
        }


class CommentAnalysis(db.Model):
    __tablename__ = "comment_analyses"

    id = db.Column(db.Integer, primary_key=True)
    comment_id = db.Column(db.Integer, db.ForeignKey("comments.id", ondelete="CASCADE"), nullable=False, unique=True)
    task_id = db.Column(db.Integer, db.ForeignKey("analysis_tasks.id", ondelete="SET NULL"), index=True)
    sentiment = db.Column(db.String(16))  # positive | negative | neutral
    sentiment_score = db.Column(db.Float)  # 0.0 - 1.0
    aspects = db.Column(db.JSON)  # {"quality": 0.8, "logistics": 0.3, ...}
    keywords = db.Column(db.JSON)
    summary = db.Column(db.Text)
    fake_score = db.Column(db.Float)  # 0.0 - 1.0, higher = more likely fake
    model_version = db.Column(db.String(64))
    analyzed_at = db.Column(db.DateTime, default=utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "comment_id": self.comment_id,
            "sentiment": self.sentiment,
            "sentiment_score": self.sentiment_score,
            "aspects": self.aspects,
            "keywords": self.keywords,
            "summary": self.summary,
            "fake_score": self.fake_score,
            "model_version": self.model_version,
            "analyzed_at": self.analyzed_at.isoformat() if self.analyzed_at else None,
        }
