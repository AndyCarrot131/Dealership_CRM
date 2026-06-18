"""add channel column to email_drafts

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-11
"""
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "email_drafts",
        sa.Column("channel", sa.String(10), nullable=False, server_default="email"),
    )


def downgrade() -> None:
    op.drop_column("email_drafts", "channel")
