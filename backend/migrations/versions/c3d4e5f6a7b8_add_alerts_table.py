"""Add alerts table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-11 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=True),
        sa.Column("alert_type", sa.String(length=32), nullable=False, index=True),
        sa.Column("severity", sa.String(length=16), nullable=False, server_default="info"),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("detail", JSONB(), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_alerts_product", "alerts", ["product_id"])
    op.create_index("idx_alerts_type", "alerts", ["alert_type"])
    op.create_index("idx_alerts_created", "alerts", ["created_at"])
    op.create_index("idx_alerts_unread", "alerts", ["is_read"], postgresql_where=sa.text("is_read = FALSE"))


def downgrade():
    op.drop_index("idx_alerts_unread", table_name="alerts")
    op.drop_index("idx_alerts_created", table_name="alerts")
    op.drop_index("idx_alerts_type", table_name="alerts")
    op.drop_index("idx_alerts_product", table_name="alerts")
    op.drop_table("alerts")
