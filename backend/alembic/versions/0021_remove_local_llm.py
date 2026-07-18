"""remove local LLM configuration

Revision ID: 0021
Revises: 0020
"""

from alembic import op
import sqlalchemy as sa

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Local profiles are obsolete now that Gemini is the environment default.
    # Delete them before dropping the discriminator so both upgrades and fresh
    # migration chains finish without resurrecting a local endpoint.
    op.execute("DELETE FROM llm_profiles WHERE is_local = true")
    op.execute(
        "DELETE FROM user_settings "
        "WHERE key IN ('llm_base_url', 'llm_api_key', 'llm_model')"
    )
    op.drop_column("llm_profiles", "is_local")


def downgrade() -> None:
    op.add_column(
        "llm_profiles",
        sa.Column("is_local", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
