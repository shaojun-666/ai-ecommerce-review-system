import datetime
from app.extensions import db


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc)


class Alert(db.Model):
    __tablename__ = "alerts"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=True, index=True)
    alert_type = db.Column(db.String(32), nullable=False, index=True)
    # negative_surge | price_drop | price_spike | new_competitor | crawl_failure
    severity = db.Column(db.String(16), nullable=False, default="info")
    # critical | warning | info
    title = db.Column(db.String(256), nullable=False)
    message = db.Column(db.Text, nullable=False)
    detail = db.Column(db.JSON)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "product_id": self.product_id,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "title": self.title,
            "message": self.message,
            "detail": self.detail or {},
            "is_read": self.is_read,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
