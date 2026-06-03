"""Add last_active_at to users

Revision ID: 20260513_add_last_active_at
Revises: c7d9e4f1a2b3
Create Date: 2026-05-13 12:00:00.000000

"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260513_add_last_active_at"
down_revision: Union[str, None] = "c7d9e4f1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("users", "last_active_at")
