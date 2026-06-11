import datetime
from app.extensions import db


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc)


class ProductPrice(db.Model):
    __tablename__ = "product_prices"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    price = db.Column(db.Float, nullable=False)
    platform = db.Column(db.String(50), default="")
    recorded_at = db.Column(db.DateTime, default=utcnow, index=True)
    source = db.Column(db.String(20), default="crawl")  # crawl / manual

    product = db.relationship("Product", backref=db.backref("prices", lazy="dynamic", order_by="ProductPrice.recorded_at.desc()"))

    def to_dict(self):
        return {
            "id": self.id,
            "product_id": self.product_id,
            "price": self.price,
            "platform": self.platform,
            "recorded_at": self.recorded_at.isoformat() if self.recorded_at else None,
            "source": self.source,
        }
