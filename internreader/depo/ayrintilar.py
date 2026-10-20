"""İlan ayrıntıları: öğrenciye uygun ilanlardan yapay zekânın çıkardığı özet, son başvuru, hedef sınıf vb."""

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from internreader.db import IlanAyrinti, IlanKaydi, Siniflandirma
from internreader.depo._ortak import _parcalar


def ayrinti_bekleyenler(oturum: Session, sinir: int = 60) -> list[dict]:
    """Aktif, öğrenciye uygun ve ayrıntısı henüz çıkarılmamış ilanlar (en yeniler önce)."""
    sorgu = (
        select(IlanKaydi)
        .join(Siniflandirma, Siniflandirma.kimlik == IlanKaydi.kimlik)
        .outerjoin(IlanAyrinti, IlanAyrinti.kimlik == IlanKaydi.kimlik)
        .where(IlanKaydi.aktif.is_(True), Siniflandirma.ogrenciye_uygun.is_(True), IlanAyrinti.kimlik.is_(None))
        .order_by(IlanKaydi.ilk_gorulme.desc())
        .limit(sinir)
    )
    return [
        {
            "kimlik": i.kimlik,
            "firma": i.firma,
            "baslik": i.baslik,
            "url": i.url,
            "kaynak": i.kaynak,
            "konum": i.konum,
            "aciklama": i.aciklama,
        }
        for i in oturum.scalars(sorgu)
    ]


def ayrinti_kaydet(oturum: Session, kimlik: str, alanlar: dict, metin_ozeti: str, model: str) -> None:
    oturum.merge(
        IlanAyrinti(
            kimlik=kimlik,
            ozet=alanlar.get("ozet", "")[:400],
            son_basvuru=alanlar.get("son_basvuru"),
            hedef=alanlar.get("hedef") or None,  # uzunluk çıkarıcıda kelime sınırından kısaltıldı
            calisma_modeli=alanlar.get("calisma_modeli", "belirsiz"),
            ucretli=alanlar.get("ucretli", "belirsiz"),
            teknolojiler=list(alanlar.get("teknolojiler", []))[:8],
            metin_ozeti=metin_ozeti,
            model=model,
        )
    )


def ayrinti_sayisi(oturum: Session, kimlikler: Iterable[str]) -> int:
    toplam = 0
    for parca in _parcalar(sorted(set(kimlikler))):
        toplam += len(list(oturum.scalars(select(IlanAyrinti.kimlik).where(IlanAyrinti.kimlik.in_(parca)))))
    return toplam
