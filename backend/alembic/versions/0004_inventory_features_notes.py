"""add features and notes to inventory

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-08

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("inventory", sa.Column("features", sa.Text(), nullable=True))
    op.add_column("inventory", sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("inventory", "notes")
    op.drop_column("inventory", "features")
