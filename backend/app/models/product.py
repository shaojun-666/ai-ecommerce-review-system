import datetime
from app.extensions import db


def utcnow():
    """Column-default-friendly wrapper for timezone-aware UTC now."""
    return datetime.datetime.now(datetime.timezone.utc)


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    platform = db.Column(db.String(50), default="")
    platform_product_id = db.Column(db.String(128), default="", index=True)
    url = db.Column(db.String(1024), default="")
    image_url = db.Column(db.String(1024), default="")
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    last_crawled_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    tags = db.relationship("ProductTag", secondary="product_tag_map", lazy="selectin",
                           backref=db.backref("tagged_products", lazy="selectin"))

    def to_dict(self, include_prices=False):
        d = {
            "id": self.id,
            "name": self.name,
            "platform": self.platform,
            "platform_product_id": self.platform_product_id,
            "url": self.url,
            "image_url": self.image_url,
            "user_id": self.user_id,
            "tags": [t.to_dict() for t in self.tags] if self.tags else [],
            "last_crawled_at": self.last_crawled_at.isoformat() if self.last_crawled_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_prices:
            prices = self.prices.limit(50).all()
            d["prices"] = [p.to_dict() for p in prices]
        # Attach latest price
        latest = self.prices.first()
        d["latest_price"] = latest.price if latest else None
        d["latest_price_at"] = latest.recorded_at.isoformat() if latest else None
        return d
