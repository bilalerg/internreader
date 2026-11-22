"""Keep company operating evidence separate from the scanning switch."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "firmalar", sa.Column("faaliyet_durumu", sa.String(length=20), server_default="belirsiz", nullable=False)
    )
    op.add_column("firmalar", sa.Column("faaliyet_kontrol_zamani", sa.DateTime(timezone=True)))
    op.add_column("firmalar", sa.Column("faaliyet_kanit_tarihi", sa.DateTime(timezone=True)))
    op.add_column("firmalar", sa.Column("faaliyet_kanit_url", sa.Text()))
    op.add_column("firmalar", sa.Column("faaliyet_neden", sa.String(length=80)))


def downgrade() -> None:
    for alan in (
        "faaliyet_neden",
        "faaliyet_kanit_url",
        "faaliyet_kanit_tarihi",
        "faaliyet_kontrol_zamani",
        "faaliyet_durumu",
    ):
        op.drop_column("firmalar", alan)
