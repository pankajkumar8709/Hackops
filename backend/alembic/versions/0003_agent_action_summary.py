"""agent action plain-language summary

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-04

Adds a human-readable one-line summary to each AgentAction so the
dashboard explainability feed and the Discord bot can show what the
agent did without rendering raw JSON.
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_actions", sa.Column("summary", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("agent_actions", "summary")