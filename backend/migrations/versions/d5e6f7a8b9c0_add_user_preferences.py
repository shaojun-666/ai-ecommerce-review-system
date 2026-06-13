"""Add preferences JSON column to users table

Revision ID: d5e6f7a8b9c0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-13

"""
from alembic import op
import sqlalchemy as sa

revision = "d5e6f7a8b9c0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("preferences", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("users", "preferences")
