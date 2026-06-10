"""add app_settings table

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-10

"""
from typing import Sequence, Union
import os

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(50), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    llm_base_url = os.getenv("llm_base_url", os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"))
    llm_api_key = os.getenv("llm_api_key", os.getenv("LLM_API_KEY", ""))
    llm_model = os.getenv("llm_model", os.getenv("LLM_MODEL", "gpt-4o"))

    op.execute(
        sa.text(
            "INSERT INTO app_settings (key, value) VALUES "
            "(:k1, :v1), (:k2, :v2), (:k3, :v3)"
        ).bindparams(
            k1="llm_base_url", v1=llm_base_url,
            k2="llm_api_key", v2=llm_api_key,
            k3="llm_model", v3=llm_model,
        )
    )


def downgrade() -> None:
    op.drop_table("app_settings")
