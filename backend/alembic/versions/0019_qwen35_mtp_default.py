"""use Qwen3.5 MTP Q4_K_M as the local default model

Revision ID: 0019
Revises: 0018
Create Date: 2026-07-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_LOCAL_MODEL = "Qwen3VL-4B-Instruct-Q4_K_M.gguf"
NEW_LOCAL_MODEL = "Qwen3.5-4B-Q4_K_M.gguf"


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE user_settings
            SET value = :new_model
            WHERE key = 'llm_model' AND value = :old_model
            """
        ).bindparams(new_model=NEW_LOCAL_MODEL, old_model=OLD_LOCAL_MODEL)
    )
    op.execute(
        sa.text(
            """
            UPDATE llm_profiles
            SET model = :new_model
            WHERE is_local = true AND model = :old_model
            """
        ).bindparams(new_model=NEW_LOCAL_MODEL, old_model=OLD_LOCAL_MODEL)
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE user_settings
            SET value = :old_model
            WHERE key = 'llm_model' AND value = :new_model
            """
        ).bindparams(old_model=OLD_LOCAL_MODEL, new_model=NEW_LOCAL_MODEL)
    )
    op.execute(
        sa.text(
            """
            UPDATE llm_profiles
            SET model = :old_model
            WHERE is_local = true AND model = :new_model
            """
        ).bindparams(old_model=OLD_LOCAL_MODEL, new_model=NEW_LOCAL_MODEL)
    )
