"""İlanlar ve sınıflandırmalar: kaydetme, kapanan ilanlar, yayınlanacak öğrenci ilanları."""

from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from internreader.db import IlanAyrinti, IlanKaydi, Siniflandirma, simdi
from internreader.depo._ortak import _parcalar, utc
from internreader.model import HEDEF_ROLLER, OGRENCI_SEVIYELERI, Ilan


def ilanlari_kaydet(oturum: Session, ilanlar: list[Ilan], basarili_firmalar: set[str]) -> tuple[list[str], int]:
    """İlanları ekler/günceller. (yeni ilan kimlikleri, kapandığı anlaşılan ilan sayısı) döndürür.

    Kapanma kuralı: bu çalıştırmada başarıyla taranan bir firmanın, daha önce görülüp bu kez görülmeyen
    ilanı kapandı sayılır. Taraması başarısız olan firmanın ilanlarına dokunulmaz (site çöktü diye ilan silinmez).
    """
    an = simdi()
    gelen = {i.kimlik: i for i in ilanlar}
    mevcut: dict[str, IlanKaydi] = {}
    for parca in _parcalar(list(gelen)):
        for kayit in oturum.scalars(select(IlanKaydi).where(IlanKaydi.kimlik.in_(parca))):
            mevcut[kayit.kimlik] = kayit

    yeniler = []
    for kimlik, i in gelen.items():
        kayit = mevcut.get(kimlik)
        if kayit is None:
            kayit = IlanKaydi(kimlik=kimlik, ilk_gorulme=an)
            oturum.add(kayit)
            yeniler.append(kimlik)
        kayit.firma, kayit.baslik, kayit.url, kayit.kaynak = i.firma, i.baslik, i.url, i.kaynak
        kayit.konum, kayit.calisma_tipi, kayit.yayin_tarihi = i.konum, i.calisma_tipi[:80], i.tarih[:10]
        kayit.aciklama, kayit.etiket = i.aciklama[:20_000], i.etiket
        kayit.son_gorulme, kayit.aktif = an, True

    # "Bu çalıştırmada görülmedi" kümeyle bulunur, zaman damgasıyla değil: saat çözünürlüğü kaba olan sistemlerde
    # (Windows) art arda iki çalıştırma aynı zamanı alabiliyor ve "son_gorulme < an" kapananları kaçırıyordu.
    kapanacak = []
    for parca in _parcalar(sorted(basarili_firmalar)):
        sorgu = select(IlanKaydi.kimlik).where(IlanKaydi.firma.in_(parca), IlanKaydi.aktif.is_(True))
        kapanacak += [k for k in oturum.scalars(sorgu) if k not in gelen]
    for parca in _parcalar(kapanacak):
        oturum.execute(update(IlanKaydi).where(IlanKaydi.kimlik.in_(parca)).values(aktif=False))
    return yeniler, len(kapanacak)


def siniflandirilmamislar(oturum: Session, kimlikler: Iterable[str]) -> set[str]:
    """Yapay zekâyla henüz sınıflanmamış ilanlar. Yedek kuralla ("kural") sınıflananlar da yeniden denenir."""
    istenen = list(set(kimlikler))
    var = set()
    for parca in _parcalar(istenen):
        var |= set(
            oturum.scalars(
                select(Siniflandirma.kimlik).where(Siniflandirma.kimlik.in_(parca), Siniflandirma.model != "kural")
            )
        )
    return set(istenen) - var


def siniflandirma_kaydet(oturum: Session, sonuclar: dict[str, dict], model: str) -> None:
    for kimlik, s in sonuclar.items():
        uygun = s["seviye"] in OGRENCI_SEVIYELERI and s["rol"] in HEDEF_ROLLER
        oturum.merge(
            Siniflandirma(
                kimlik=kimlik,
                seviye=s["seviye"],
                rol=s["rol"],
                yapay_zeka=s["yapay_zeka"],
                ogrenciye_uygun=uygun,
                gerekce=s.get("gerekce", "")[:300],
                model=model,
                imza=s.get("imza"),
            )
        )


def yayinlanacak_ilanlar(oturum: Session, sonra: datetime | None = None) -> list[dict]:
    """Aktif ve öğrenciye uygun ilanlar (sınıflandırma bilgisiyle). `sonra` verilirse yalnızca o andan sonra ilk
    kez görülenler — günlük özet için."""
    sorgu = (
        select(IlanKaydi, Siniflandirma, IlanAyrinti)
        .join(Siniflandirma, Siniflandirma.kimlik == IlanKaydi.kimlik)
        .outerjoin(IlanAyrinti, IlanAyrinti.kimlik == IlanKaydi.kimlik)
        .where(IlanKaydi.aktif.is_(True), Siniflandirma.ogrenciye_uygun.is_(True))
        .order_by(IlanKaydi.ilk_gorulme.desc(), IlanKaydi.firma)
    )
    if sonra is not None:
        sorgu = sorgu.where(IlanKaydi.ilk_gorulme > sonra)
    satirlar = []
    for ilan, sinif, ayrinti in oturum.execute(sorgu):
        satirlar.append(
            {
                "kimlik": ilan.kimlik,
                "firma": ilan.firma,
                "baslik": ilan.baslik,
                "url": ilan.url,
                "konum": ilan.konum,
                "kaynak": ilan.kaynak,
                "yayin_tarihi": ilan.yayin_tarihi,
                "ilk_gorulme": utc(ilan.ilk_gorulme).isoformat(),
                "seviye": sinif.seviye,
                "rol": sinif.rol,
                "yapay_zeka": sinif.yapay_zeka,
                "ayrinti": _ayrinti_sozlugu(ayrinti),
            }
        )
    return satirlar


def _ayrinti_sozlugu(a: IlanAyrinti | None) -> dict | None:
    if (
        a is None or a.model == "metin-yok"
    ):  # metni olmayan ilan: tekrar denenmesin diye boş kayıt var, gösterilecek bir şey yok
        return None
    return {
        "ozet": a.ozet,
        "son_basvuru": a.son_basvuru,
        "hedef": a.hedef,
        "calisma_modeli": a.calisma_modeli,
        "ucretli": a.ucretli,
        "teknolojiler": list(a.teknolojiler or []),
    }


def imzayla_kararlar(oturum: Session, imzalar: Iterable[str]) -> dict[str, dict]:
    """Aynı imzaya sahip, yapay zekâyla verilmiş eski kararlar (imza → karar). Yeniden yayınlanan ilan için kullanılır."""
    kararlar: dict[str, dict] = {}
    for parca in _parcalar(sorted(set(imzalar))):
        sorgu = select(Siniflandirma).where(Siniflandirma.imza.in_(parca), Siniflandirma.model != "kural")
        for k in oturum.scalars(sorgu):
            kararlar[k.imza] = {"seviye": k.seviye, "rol": k.rol, "yapay_zeka": k.yapay_zeka, "gerekce": k.gerekce}
    return kararlar


def kapali_ilan_metinlerini_temizle(oturum: Session, once: datetime) -> int:
    """Uzun süredir kapalı ilanların açıklama metni silinir (veritabanı şişmez); başlık, firma ve karar kalır."""
    sonuc = oturum.execute(
        update(IlanKaydi)
        .where(IlanKaydi.aktif.is_(False), IlanKaydi.son_gorulme < once, IlanKaydi.aciklama != "")
        .values(aciklama="")
    )
    return sonuc.rowcount or 0
