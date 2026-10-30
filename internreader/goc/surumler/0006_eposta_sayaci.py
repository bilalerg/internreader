"""günlük e-posta sayacı

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-30 23:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "eposta_sayaci",
        sa.Column("gun", sa.String(length=10), nullable=False),
        sa.Column("adet", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("gun"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("eposta_sayaci")
