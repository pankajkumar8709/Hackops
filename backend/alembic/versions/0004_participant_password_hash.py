"""add password_hash to participants

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-04

Adds a bcrypt password_hash column to participants for email+password auth.
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("participants", sa.Column("password_hash", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("participants", "password_hash")
