"""mark local llm profiles and align default model settings

Revision ID: 0018
Revises: 0017
Create Date: 2026-07-03

"""
import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

LOCAL_BASE_URL = os.getenv("LLM_BASE_URL", "http://local_llm:8080/v1")
LOCAL_API_KEY = os.getenv("LLM_API_KEY", "no-key-needed")
LOCAL_MODEL = os.getenv("LLM_MODEL", "Qwen3VL-4B-Instruct-Q4_K_M.gguf")


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE llm_profiles SET is_local = true
            WHERE base_url LIKE '%8080%'
               OR base_url LIKE '%local_llm%'
               OR base_url LIKE '%127.0.0.1%'
               OR base_url LIKE '%host.docker.internal%'
            """
        )
    )

    op.execute(
        sa.text(
            """
            UPDATE user_settings SET value = :url
            WHERE key = 'llm_base_url'
              AND value IN ('https://api.openai.com/v1', '')
            """
        ).bindparams(url=LOCAL_BASE_URL)
    )
    op.execute(
        sa.text(
            """
            UPDATE user_settings SET value = :key
            WHERE key = 'llm_api_key'
              AND value IN ('', 'sk-...')
            """
        ).bindparams(key=LOCAL_API_KEY)
    )
    op.execute(
        sa.text(
            """
            UPDATE user_settings SET value = :model
            WHERE key = 'llm_model'
              AND value IN ('gpt-4o', '')
            """
        ).bindparams(model=LOCAL_MODEL)
    )

    op.execute(
        sa.text(
            """
            UPDATE llm_profiles
            SET base_url = :url, api_key = :key, model = :model, is_local = true
            WHERE name = 'Default'
              AND is_active = true
              AND base_url IN ('https://api.openai.com/v1', '')
            """
        ).bindparams(url=LOCAL_BASE_URL, key=LOCAL_API_KEY, model=LOCAL_MODEL)
    )


def downgrade() -> None:
    pass
