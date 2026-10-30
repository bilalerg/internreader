"""İlan ayrıntıları: öğrenciye uygun ilanlardan yapay zekânın çıkardığı özet, son başvuru, hedef sınıf vb."""

from collections.abc import Iterable

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from internreader.db import IlanAyrinti, IlanKaydi, Siniflandirma
from internreader.depo._ortak import _parcalar

# Ayrıntı çıkarıcının sürümü; artınca aktif öğrenci ilanları bir kez yeniden çıkarılır.
# 2 (29.10.2026): ilan tarihi ve dönem yılı; #çapalı ilanların metni listelendikleri sayfadan bulunuyor.
# 3 (30.10.2026): sayfa metninden menü ayıklanıyor (eskiden model yalnızca menüyü görebiliyordu); ilan türü,
# metne göre rol doğrulama, savunma kanıtı.
AYRINTI_SURUMU = 3


def ayrinti_bekleyenler(oturum: Session, sinir: int = 60, yalnizca_ats: bool = False) -> list[dict]:
    """Aktif, öğrenciye uygun ve ayrıntısı henüz çıkarılmamış ilanlar (en yeniler önce). Ardından eski sürümle
    çıkarılmış olanlar: bunlar bir kez yeniden çıkarılır (çıkarılınca sürüm güncellenir, bir daha gönderilmez)."""
    sorgu = (
        select(IlanKaydi)
        .join(Siniflandirma, Siniflandirma.kimlik == IlanKaydi.kimlik)
        .outerjoin(IlanAyrinti, IlanAyrinti.kimlik == IlanKaydi.kimlik)
        .where(
            IlanKaydi.aktif.is_(True),
            Siniflandirma.ogrenciye_uygun.is_(True),
            or_(IlanAyrinti.kimlik.is_(None), IlanAyrinti.surum < AYRINTI_SURUMU),
        )
        .order_by(IlanAyrinti.kimlik.is_not(None), IlanKaydi.ilk_gorulme.desc())
        .limit(sinir)
    )
    if yalnizca_ats:  # ara tarama: kariyer sayfası okunmaz
        sorgu = sorgu.where(IlanKaydi.kaynak != "kariyer_sayfasi")
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
            ilan_tarihi=alanlar.get("ilan_tarihi"),
            donem_yili=alanlar.get("donem_yili"),
            ilan_turu=alanlar.get("ilan_turu", "is"),
            savunma_kaniti=bool(alanlar.get("savunma_kaniti")),
            surum=AYRINTI_SURUMU,
            calisma_modeli=alanlar.get("calisma_modeli", "belirsiz"),
            ucretli=alanlar.get("ucretli", "belirsiz"),
            teknolojiler=list(alanlar.get("teknolojiler", []))[:8],
            metin_ozeti=metin_ozeti,
            model=model,
        )
    )


def sayfa_basliklari(oturum: Session, adresler: Iterable[str]) -> dict[str, list[str]]:
    """Tek sayfada listelenen ilanlar (adres#çapa): sayfa adresi → o sayfadaki aktif ilan başlıkları. Bir ilanın
    metnini sayfadan keserken bir sonraki ilanın nerede başladığını bulmak için."""
    basliklar: dict[str, list[str]] = {}
    for adres in set(adresler):
        sorgu = select(IlanKaydi.baslik).where(IlanKaydi.url.like(adres + "#%"), IlanKaydi.aktif.is_(True))
        basliklar[adres] = list(oturum.scalars(sorgu))
    return basliklar


def ayrinti_sayisi(oturum: Session, kimlikler: Iterable[str]) -> int:
    toplam = 0
    for parca in _parcalar(sorted(set(kimlikler))):
        toplam += len(list(oturum.scalars(select(IlanAyrinti.kimlik).where(IlanAyrinti.kimlik.in_(parca)))))
    return toplam
