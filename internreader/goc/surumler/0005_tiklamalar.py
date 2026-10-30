"""tıklama ölçümü tablosu

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-30 21:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "tiklamalar",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tarih", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ilan_kimlik", sa.String(length=16), nullable=False),
        sa.Column("eposta_no", sa.String(length=16), nullable=False),
        sa.Column("kisi", sa.String(length=16), nullable=False),
        sa.Column("hafta", sa.String(length=8), nullable=False),
        sa.Column("tur", sa.String(length=12), nullable=False),
        sa.Column("supheli", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("eposta_no", "ilan_kimlik", "supheli", name="uq_tiklama_eposta_ilan"),
    )
    with op.batch_alter_table("tiklamalar", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_tiklamalar_tarih"), ["tarih"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("tiklamalar", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_tiklamalar_tarih"))
    op.drop_table("tiklamalar")
