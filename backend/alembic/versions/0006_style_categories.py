"""add style_categories table

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "style_categories",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("sales_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("channel", sa.String(10), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("sales_id", "channel", "name", name="uq_style_category"),
    )


def downgrade() -> None:
    op.drop_table("style_categories")
