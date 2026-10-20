"""Yapay zekâ kullanım kayıtları ve harcama."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from internreader.db import YzKullanim, simdi


def kullanim_yaz(oturum: Session, kayitlar: list[dict]) -> None:
    for k in kayitlar:
        oturum.add(YzKullanim(**k))


def bu_ay_harcanan(oturum: Session) -> float:
    an = simdi()
    ay_basi = an.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return float(
        oturum.scalar(select(func.coalesce(func.sum(YzKullanim.maliyet_usd), 0.0)).where(YzKullanim.tarih >= ay_basi))
        or 0.0
    )
