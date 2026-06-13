"""add llm_profiles table; migrate existing user_settings llm keys into default profiles

Revision ID: 0013
Revises: 0012
Create Date: 2026-06-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "llm_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("api_key", sa.Text(), nullable=False),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # For each user that already has llm settings in user_settings, create a
    # "Default" profile (is_active=true) so they keep a working configuration.
    op.execute(
        sa.text(
            """
            INSERT INTO llm_profiles (user_id, name, base_url, api_key, model, is_active)
            SELECT
                u.id,
                'Default',
                COALESCE(MAX(CASE WHEN s.key = 'llm_base_url' THEN s.value END), ''),
                COALESCE(MAX(CASE WHEN s.key = 'llm_api_key'  THEN s.value END), ''),
                COALESCE(MAX(CASE WHEN s.key = 'llm_model'    THEN s.value END), ''),
                TRUE
            FROM users u
            JOIN user_settings s ON s.user_id = u.id
            WHERE s.key IN ('llm_base_url', 'llm_api_key', 'llm_model')
            GROUP BY u.id
            """
        )
    )


def downgrade() -> None:
    op.drop_table("llm_profiles")
