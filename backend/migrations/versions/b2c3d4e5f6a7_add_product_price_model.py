"""add product_price model for price history tracking

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-11 15:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "product_prices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("platform", sa.String(50), default=""),
        sa.Column("recorded_at", sa.DateTime(), index=True),
        sa.Column("source", sa.String(20), default="crawl"),
    )
    op.create_index("idx_product_prices_product", "product_prices", ["product_id"])
    op.create_index("idx_product_prices_recorded", "product_prices", ["recorded_at"])


def downgrade():
    op.drop_index("idx_product_prices_recorded", table_name="product_prices")
    op.drop_index("idx_product_prices_product", table_name="product_prices")
    op.drop_table("product_prices")
