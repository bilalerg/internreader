"""Bülten gönderimi: kime ne zaman gönderilecek, kime hangi ilan gitti, gönderim kayıtları."""

from collections.abc import Iterable
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from internreader.db import Abone, Bulten, Gonderim
from internreader.depo._ortak import utc

HAFTALIK_ARALIK = timedelta(days=6, hours=12)  # haftalık abone: son bültenden en az ~1 hafta sonra


def gonderime_hazir_aboneler(oturum: Session, an: datetime) -> list[Abone]:
    """Onaylı aboneler: günlükler her çalıştırmada, haftalıklar son bültenlerinden bir hafta sonra."""
    hazir = []
    for abone in oturum.scalars(select(Abone).where(Abone.durum == "onayli").order_by(Abone.id)):
        son = utc(abone.son_bulten)
        if abone.siklik == "gunluk" or son is None or son <= an - HAFTALIK_ARALIK:
            hazir.append(abone)
    return hazir


def gonderilen_kimlikler(oturum: Session, abone_id: int) -> set[str]:
    return set(oturum.scalars(select(Gonderim.ilan_kimlik).where(Gonderim.abone_id == abone_id)))


def gonderim_kaydet(oturum: Session, abone: Abone, kimlikler: Iterable[str], an: datetime) -> None:
    for kimlik in kimlikler:
        oturum.add(Gonderim(abone_id=abone.id, ilan_kimlik=kimlik, tarih=an))
    abone.son_bulten = an


def bulten_kaydet(oturum: Session, abone_id: int, ilan_sayisi: int, durum: str, an: datetime) -> None:
    oturum.add(Bulten(abone_id=abone_id, ilan_sayisi=ilan_sayisi, durum=durum, tarih=an))


def bulten_istatistigi(oturum: Session, an: datetime, gun: int = 7) -> dict:
    """Son `gun` günde gönderilen bülten ve bülten alan farklı abone sayısı (aktif kullanıcı ölçümünün bir parçası)."""
    esik = an - timedelta(days=gun)
    kosul = (Bulten.tarih >= esik, Bulten.durum == "gonderildi")
    return {
        "gun": gun,
        "bulten": oturum.scalar(select(func.count()).select_from(Bulten).where(*kosul)) or 0,
        "abone": oturum.scalar(select(func.count(func.distinct(Bulten.abone_id))).where(*kosul)) or 0,
    }


def eski_gonderimleri_sil(oturum: Session, once: datetime) -> int:
    """Kapanmış ilanlar tekrar gönderilmeyeceği için eski gönderim kayıtları tutulmaz."""
    return oturum.execute(delete(Gonderim).where(Gonderim.tarih < once)).rowcount or 0
