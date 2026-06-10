import datetime
from app.extensions import db


def utcnow():
    """Column-default-friendly wrapper for timezone-aware UTC now."""
    return datetime.datetime.now(datetime.UTC)


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    platform = db.Column(db.String(50), default="")
    platform_product_id = db.Column(db.String(128), default="", index=True)
    url = db.Column(db.String(1024), default="")
    image_url = db.Column(db.String(1024), default="")
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "platform": self.platform,
            "platform_product_id": self.platform_product_id,
            "url": self.url,
            "image_url": self.image_url,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
