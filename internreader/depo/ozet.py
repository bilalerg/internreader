"""Site ve izleme için özet veriler (sayılar, örnek firmalar, yapay zekâ kararlarından örnekler)."""

import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from internreader.db import Firma, IlanKaydi, Siniflandirma, simdi
from internreader.depo.aboneler import abone_sayilari
from internreader.depo.bulten import bulten_istatistigi
from internreader.depo.durum import durum_al
from internreader.depo.ilanlar import yayinlanacak_ilanlar
from internreader.depo.kullanim import bu_ay_harcanan


def taranan_firma_sayisi(oturum: Session) -> int:
    """İlan sistemi ya da kariyer sayfası bilinen (yani her gün gerçekten taranan) aktif firma sayısı."""
    return oturum.scalar(
        select(func.count())
        .select_from(Firma)
        .where(Firma.aktif.is_(True), (Firma.ats.is_not(None)) | (Firma.kariyer.is_not(None)))
    )


def takip_edilen_firma_sayisi(oturum: Session) -> int:
    """Listedeki bütün aktif firmalar (ayda bir keşif yapılır; ilan sayfası bilinenler her sabah taranır)."""
    return oturum.scalar(select(func.count()).select_from(Firma).where(Firma.aktif.is_(True)))


def aktif_konumlar(oturum: Session) -> list[str]:
    return list(oturum.scalars(select(IlanKaydi.konum).where(IlanKaydi.aktif.is_(True))))


def ornek_firma_adlari(oturum: Session, sinir: int = 60) -> list[str]:
    """Taranan firmalardan kısa adlı olanlar (sitedeki tarama animasyonu için; sıra her çalıştırmada aynı)."""
    sorgu = (
        select(Firma.ad)
        .where(Firma.aktif.is_(True), (Firma.ats.is_not(None)) | (Firma.kariyer.is_not(None)))
        .where(func.length(Firma.ad) <= 24)
        .order_by(Firma.id)
    )
    return list(oturum.scalars(sorgu.limit(sinir)))


def ornek_kararlar(oturum: Session, uygun: bool, sinir: int = 8) -> list[dict]:
    """Yapay zekânın gerçek kararlarından örnekler (gerekçesiyle). Elenenler çeşitli olsun diye seviye/rol
    gruplarından sırayla seçilir."""
    sorgu = (
        select(IlanKaydi.baslik, IlanKaydi.firma, Siniflandirma.seviye, Siniflandirma.rol, Siniflandirma.gerekce)
        .join(Siniflandirma, Siniflandirma.kimlik == IlanKaydi.kimlik)
        .where(
            IlanKaydi.aktif.is_(True),
            Siniflandirma.ogrenciye_uygun.is_(uygun),
            Siniflandirma.model != "kural",
            func.length(IlanKaydi.baslik) <= 60,
        )
        .order_by(IlanKaydi.kimlik)
    )
    gruplar: dict[tuple, list[dict]] = {}
    for baslik, firma, seviye, rol, gerekce in oturum.execute(sorgu):
        gruplar.setdefault((seviye, rol), []).append(
            {"baslik": baslik, "firma": firma, "seviye": seviye, "rol": rol, "gerekce": gerekce, "uygun": uygun}
        )
    secilen: list[dict] = []
    while len(secilen) < sinir and any(gruplar.values()):  # gruplardan sırayla birer tane
        for grup in gruplar.values():
            if grup and len(secilen) < sinir:
                secilen.append(grup.pop(0))
    return secilen


def istatistik(oturum: Session) -> dict:
    return {
        "firma": oturum.scalar(select(func.count()).select_from(Firma)),
        "ilan_sistemi_bilinen": oturum.scalar(select(func.count()).select_from(Firma).where(Firma.ats.is_not(None))),
        "kariyer_sayfasi": oturum.scalar(select(func.count()).select_from(Firma).where(Firma.kariyer.is_not(None))),
        "aktif_ilan": oturum.scalar(select(func.count()).select_from(IlanKaydi).where(IlanKaydi.aktif.is_(True))),
        "siniflandirilan": oturum.scalar(select(func.count()).select_from(Siniflandirma)),
        "yayinlanabilir": len(yayinlanacak_ilanlar(oturum)),
        "bu_ay_yz_usd": round(bu_ay_harcanan(oturum), 4),
        "son_tarama": json.loads(durum_al(oturum, "son_tarama") or "null"),
        "aboneler": abone_sayilari(oturum),
        "bulten_son_7_gun": bulten_istatistigi(oturum, simdi()),
    }
