"""firma sanılan ilan sitelerini kapat

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-01 09:00:00

01.11.2026 arama keşfi, ilan toplayan bazı siteleri firma diye ekledi. Bunlar taranmaz; kurallar (arama.SIRKET_DEGIL)
yeniden eklenmelerini önler. Kayıt silinmez, firma kapatılır.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "UPDATE firmalar SET aktif = false "
        "WHERE anahtar IN ('isinolsun.com', 'jobsinistanbul.com', 'iagora.com', 'cvyolla.com')"
    )


def downgrade() -> None:
    """Downgrade schema: kapatılan firmalar elle açılır; bir önceki durum bilinmiyor."""
