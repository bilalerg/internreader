"""ayrıntılara ilan türü ve savunma kanıtı

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-30 10:00:00

Var olan kayıtlar "is" ve kanıtsız başlar; AYRINTI_SURUMU arttığı için aktif öğrenci ilanları bir kez yeniden çıkarılır.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("ilan_ayrintilari", schema=None) as batch_op:
        batch_op.add_column(sa.Column("ilan_turu", sa.String(length=14), server_default="is", nullable=False))
        batch_op.add_column(sa.Column("savunma_kaniti", sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("ilan_ayrintilari", schema=None) as batch_op:
        batch_op.drop_column("savunma_kaniti")
        batch_op.drop_column("ilan_turu")
