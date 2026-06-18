"""rename deals.term_months -> term

Revision ID: 0016
Revises: 0015
Create Date: 2026-06-12

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("deals", "term_months", new_column_name="term")


def downgrade() -> None:
    op.alter_column("deals", "term", new_column_name="term_months")
