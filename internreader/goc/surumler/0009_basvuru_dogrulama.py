"""basvuru_dogrulama

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-15 14:31:47.512943

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "ilan_dogrulamalari",
        sa.Column("kimlik", sa.String(length=16), nullable=False),
        sa.Column("durum", sa.String(length=12), nullable=False),
        sa.Column("neden", sa.String(length=100), nullable=False),
        sa.Column("ilk_kontrol", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kontrol_zamani", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acik_dogrulama_zamani", sa.DateTime(timezone=True), nullable=True),
        sa.Column("gorulmeme_sayisi", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["kimlik"], ["ilanlar.kimlik"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("kimlik"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("ilan_dogrulamalari")
