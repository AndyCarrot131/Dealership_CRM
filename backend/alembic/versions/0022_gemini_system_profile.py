"""add a selectable Gemini system profile

Revision ID: 0022
Revises: 0021
"""

from alembic import op
import sqlalchemy as sa

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
GEMINI_MODEL = "gemini-3.5-flash"
GEMINI_API_KEY_REF = "env:GEMINI_API_KEY"


def upgrade() -> None:
    op.add_column(
        "llm_profiles",
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute("UPDATE llm_profiles SET is_active = false")
    op.execute(
        sa.text(
            """
            INSERT INTO llm_profiles
                (user_id, name, base_url, api_key, model, is_active, is_system)
            SELECT id, 'Gemini', :base_url, :api_key, :model, true, true
            FROM users
            """
        ).bindparams(
            base_url=GEMINI_BASE_URL,
            api_key=GEMINI_API_KEY_REF,
            model=GEMINI_MODEL,
        )
    )


def downgrade() -> None:
    op.execute("DELETE FROM llm_profiles WHERE is_system = true")
    op.drop_column("llm_profiles", "is_system")
