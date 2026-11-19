"""Replace six career URLs checked on 2026-11-19.

Only replace the exact stale URL, so a newer discovered URL is preserved.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CORRECTIONS = (
    ("Avikon", "https://www.avikon.com.tr/tr/kariyer", "https://avikon.com.tr/kariyer"),
    ("Idenfit", "https://idenfit.com/insan-kaynaklari-yonetimi-modulu/", None),
    (
        "Lostar",
        "https://lostar.com.tr/hizmetler/surekli-siber-guvenlik/",
        "https://careers.smartrecruiters.com/Lostar/",
    ),
    ("Roketsan", "https://www.roketsan.com.tr/tr/insan-kaynaklari", "https://kariyer.roketsan.com.tr/jobs"),
    ("Techsign", "https://www.techsign.com.tr/en/career", "https://techsign.ai/en/career/"),
    ("VESTEL", "https://www.vestel.com.tr/kariyer", "https://www.vestelkariyer.com/is-ilanlari"),
)


def upgrade() -> None:
    connection = op.get_bind()
    statement = sa.text("UPDATE firmalar SET kariyer = :new WHERE ad = :name AND kariyer = :old")
    for name, old, new in CORRECTIONS:
        changed = connection.execute(statement, {"name": name, "old": old, "new": new})
        if name == "Idenfit" and changed.rowcount:
            # The old URL is a product page. Let discovery retry after removing it.
            connection.execute(
                sa.text("UPDATE firmalar SET kesif_tarihi = NULL WHERE ad = :name AND kariyer IS NULL"),
                {"name": name},
            )


def downgrade() -> None:
    """Do not restore verified-bad addresses on rollback."""
