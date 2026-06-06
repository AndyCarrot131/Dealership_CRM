"""seed initial manager account

Revision ID: 0002
Revises: 0001
Create Date: 2024-01-01 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
from argon2 import PasswordHasher

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SEED_EMAIL = "admin@dealer.local"
_SEED_NAME = "Admin"
_SEED_INITIAL_PASSWORD = "changeme"


def upgrade() -> None:
    ph = PasswordHasher()
    hashed = ph.hash(_SEED_INITIAL_PASSWORD)
    op.execute(
        f"""
        INSERT INTO users (email, password_hash, name, role, must_change_password)
        VALUES ('{_SEED_EMAIL}', '{hashed}', '{_SEED_NAME}', 'manager', true)
        ON CONFLICT (email) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(f"DELETE FROM users WHERE email = '{_SEED_EMAIL}'")
