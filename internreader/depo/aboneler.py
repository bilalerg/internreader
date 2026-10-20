"""Bülten aboneleri (iş kuralları internreader/abonelik.py'de; burada yalnızca veritabanı işlemleri)."""

from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from internreader.db import Abone


def abone_eposta_ile(oturum: Session, eposta: str) -> Abone | None:
    return oturum.scalar(select(Abone).where(Abone.eposta == eposta))


def abone_id_ile(oturum: Session, abone_id: int) -> Abone | None:
    return oturum.get(Abone, abone_id)


def abone_onay_ozeti_ile(oturum: Session, ozet: str) -> Abone | None:
    return oturum.scalar(select(Abone).where(Abone.onay_jetonu_ozeti == ozet))


def abone_ekle(oturum: Session, eposta: str) -> Abone:
    abone = Abone(eposta=eposta, tercihler={}, kvkk_surumu="")
    oturum.add(abone)
    return abone


def abone_sil(oturum: Session, abone: Abone) -> None:
    oturum.delete(abone)


def onaylanmamislari_sil(oturum: Session, once: datetime) -> int:
    """Belirli bir andan önce kaydolup onaylamayanların e-postası silinir (gereğinden uzun veri tutulmaz)."""
    sonuc = oturum.execute(delete(Abone).where(Abone.durum == "bekliyor", Abone.onay_jetonu_tarihi < once))
    return sonuc.rowcount or 0


def abone_sayilari(oturum: Session) -> dict[str, int]:
    return dict(oturum.execute(select(Abone.durum, func.count()).group_by(Abone.durum)).all())
