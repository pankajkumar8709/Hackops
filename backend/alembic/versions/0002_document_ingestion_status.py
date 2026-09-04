"""document ingestion status

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-04

Adds ingestion pipeline state to documents so the frontend can show
"processing / ready / failed" per uploaded file.
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("ingestion_status", sa.String(length=20), nullable=False, server_default="processing"),
    )
    op.add_column(
        "documents",
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("documents", sa.Column("error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "error")
    op.drop_column("documents", "chunk_count")
    op.drop_column("documents", "ingestion_status")