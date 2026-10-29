"""ayrıntılara ilan tarihi, dönem yılı ve çıkarıcı sürümü

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-29 19:27:09.994578

Var olan ayrıntı kayıtları sürüm 1 olur; tarihsiz olanlar bir kez yeniden çıkarılır (depo/ayrintilar.py).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("ilan_ayrintilari", schema=None) as batch_op:
        batch_op.add_column(sa.Column("ilan_tarihi", sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column("donem_yili", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("surum", sa.Integer(), server_default="1", nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("ilan_ayrintilari", schema=None) as batch_op:
        batch_op.drop_column("surum")
        batch_op.drop_column("donem_yili")
        batch_op.drop_column("ilan_tarihi")
