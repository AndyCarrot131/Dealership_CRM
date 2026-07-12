"""use openresearchtools Qwen3.5-4B-Instruct Q4_K_M by default

Revision ID: 0020
Revises: 0019
Create Date: 2026-07-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_LOCAL_MODEL = "qwen3.5-4b-instruct-Q4_K_M.gguf"
PREVIOUS_LOCAL_MODELS = (
    "Qwen3VL-4B-Instruct-Q4_K_M.gguf",
    "Qwen3.5-4B-Q4_K_M.gguf",
)


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE user_settings
            SET value = :new_model
            WHERE key = 'llm_model' AND value IN :old_models
            """
        ).bindparams(
            sa.bindparam("old_models", expanding=True, value=PREVIOUS_LOCAL_MODELS),
            new_model=NEW_LOCAL_MODEL,
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE llm_profiles
            SET base_url = 'http://local_llm:8080/v1',
                api_key = 'no-key-needed',
                model = :new_model,
                is_local = true
            WHERE is_local = true AND model IN :old_models
            """
        ).bindparams(
            sa.bindparam("old_models", expanding=True, value=PREVIOUS_LOCAL_MODELS),
            new_model=NEW_LOCAL_MODEL,
        )
    )


def downgrade() -> None:
    pass
