"""add per-user user_settings table and move llm_* config off app_settings

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_LLM_KEYS = ("llm_base_url", "llm_api_key", "llm_model")


def upgrade() -> None:
    op.create_table(
        "user_settings",
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("key", sa.String(50), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Seed every existing user with the previous global LLM config so nobody
    # loses a working setup, then retire the global rows.
    op.execute(
        sa.text(
            "INSERT INTO user_settings (user_id, key, value) "
            "SELECT u.id, s.key, s.value "
            "FROM users u CROSS JOIN app_settings s "
            "WHERE s.key IN ('llm_base_url', 'llm_api_key', 'llm_model')"
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM app_settings "
            "WHERE key IN ('llm_base_url', 'llm_api_key', 'llm_model')"
        )
    )


def downgrade() -> None:
    op.drop_table("user_settings")
