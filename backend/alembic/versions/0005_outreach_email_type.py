"""add email_type and custom_template to outreach_rules

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-08

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "outreach_rules",
        sa.Column(
            "email_type",
            sa.String(30),
            nullable=False,
            server_default="lease_finance_ending",
        ),
    )
    op.add_column(
        "outreach_rules",
        sa.Column("custom_template", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("outreach_rules", "custom_template")
    op.drop_column("outreach_rules", "email_type")
