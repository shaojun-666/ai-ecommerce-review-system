"""Category model — hierarchical tree structure for product classification.

Schema:
    categories (id, name, slug, icon, parent_id, lft, rgt, level, created_at)

Uses adjacency list (parent_id) for simplicity. The lft/rgt columns support
efficient subtree queries (nested set compatible but not enforced — set to 0
when not in use).
"""
import datetime
from app.extensions import db


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc)


# Many-to-many: product <-> category
product_category_map = db.Table(
    "product_category_map",
    db.Column("product_id", db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
    db.Column("category_id", db.Integer, db.ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
)


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), nullable=False, unique=True, index=True)
    icon = db.Column(db.String(50), default="")  # emoji or icon class name
    parent_id = db.Column(db.Integer, db.ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True)
    lft = db.Column(db.Integer, default=0)
    rgt = db.Column(db.Integer, default=0)
    level = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=utcnow)

    # Self-referential relationship
    children = db.relationship(
        "Category", backref=db.backref("parent", remote_side="Category.id"),
        lazy="selectin", order_by="Category.name",
    )

    def to_dict(self, include_children=False):
        d = {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "icon": self.icon,
            "parent_id": self.parent_id,
            "level": self.level,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_children and self.children:
            d["children"] = [c.to_dict() for c in self.children]
        return d

    def __repr__(self):
        return f"<Category {self.slug!r} (level={self.level})>"
