"""add content_hash to comments

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-06-10 15:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("comments", sa.Column("content_hash", sa.String(64), nullable=True))
    op.create_index(
        "idx_comments_hash_product", "comments", ["content_hash", "product_id"],
    )


def downgrade():
    op.drop_index("idx_comments_hash_product", table_name="comments")
    op.drop_column("comments", "content_hash")
