"""Product tag model for grouping and filtering products."""
import datetime
from app.extensions import db


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc)


product_tag_map = db.Table(
    "product_tag_map",
    db.Column("product_id", db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("product_tags.id", ondelete="CASCADE"), primary_key=True),
)


class ProductTag(db.Model):
    __tablename__ = "product_tags"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    color = db.Column(db.String(20), default="#409eff")
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "color": self.color,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
