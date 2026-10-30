"""İlanlar ve sınıflandırmalar: kaydetme, kapanan ilanlar, yayınlanacak öğrenci ilanları."""

from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from internreader.db import Firma, IlanAyrinti, IlanKaydi, Siniflandirma, simdi
from internreader.depo._ortak import _parcalar, utc
from internreader.isleme.guncellik import baslik_yillari, donem_yillari, guncellik, siralama_anahtari
from internreader.isleme.kategori import (
    alanlari_bul,
    calisma_modeli,
    girisim_mi,
    savunma_metinde,
    seviye_etiketi,
)
from internreader.isleme.maske import kisisel_veriyi_maskele
from internreader.isleme.tekillestirme import ilan_anahtari
from internreader.model import HEDEF_ROLLER, OGRENCI_SEVIYELERI, Ilan
from internreader.yayin import TURKIYE_SAATI


def ilanlari_kaydet(
    oturum: Session, ilanlar: list[Ilan], basarili_firmalar: set[str], sayfa_ilanlari_korunsun: bool = False
) -> tuple[list[str], int]:
    """İlanları ekler/günceller. (yeni ilan kimlikleri, kapandığı anlaşılan ilan sayısı) döndürür.
    `sayfa_ilanlari_korunsun`: ara tarama kariyer sayfalarını okumaz; o kaynaktan gelen ilanlar görülmedi diye kapanmaz.

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
        kayit.aciklama, kayit.etiket = kisisel_veriyi_maskele(i.aciklama)[:20_000], i.etiket
        kayit.son_gorulme, kayit.aktif = an, True

    # "Bu çalıştırmada görülmedi" kümeyle bulunur, zaman damgasıyla değil: saat çözünürlüğü kaba olan sistemlerde
    # (Windows) art arda iki çalıştırma aynı zamanı alabiliyor ve "son_gorulme < an" kapananları kaçırıyordu.
    kapanacak = []
    for parca in _parcalar(sorted(basarili_firmalar)):
        sorgu = select(IlanKaydi.kimlik).where(IlanKaydi.firma.in_(parca), IlanKaydi.aktif.is_(True))
        if sayfa_ilanlari_korunsun:
            sorgu = sorgu.where(IlanKaydi.kaynak != "kariyer_sayfasi")
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


def rol_guncelle(oturum: Session, kimlik: str, rol: str | None) -> bool:
    """Ayrıntı çıkarıcı metnin tamamını görerek rolü doğruladı: karar buna göre düzeltilir. Rol hedef dışına çıkarsa
    ilan yayından düşer. Düzeltilen karar imzayla da geçerli: aynı ilan yeniden yayınlanırsa eskisi dönmez."""
    karar = oturum.get(Siniflandirma, kimlik)
    if rol is None or karar is None or karar.rol == rol:
        return False
    karar.rol = rol
    karar.ogrenciye_uygun = karar.seviye in OGRENCI_SEVIYELERI and rol in HEDEF_ROLLER
    if rol == "yapay_zeka" and karar.yapay_zeka == "yok":
        karar.yapay_zeka = "ozunde"
    return True


def yayinlanacak_ilanlar(
    oturum: Session,
    sonra: datetime | None = None,
    an: datetime | None = None,
    bayatlar_dahil: bool = False,
    once: datetime | None = None,
) -> list[dict]:
    """Aktif, öğrenciye uygun, elle gizlenmemiş ve bayat olmayan ilanlar (sınıflandırma bilgisiyle). `sonra` verilirse
    yalnızca o andan sonra ilk kez görülenler — günlük özet için; `once` verilirse yalnızca o ana kadar görülenler — elle
    onay modunda önizlemesi gitmemiş ilan bültene girmesin diye. Bülten kategorileri (alanlar, çalışma modeli, girişim)
    ve güncellik (yayin, surekli_acik) burada eklenir: kurallar internreader/isleme/kategori.py ve guncellik.py'de.
    `bayatlar_dahil`: bayat ilanlar da "bayat" nedeniyle döner (rapor için)."""
    bugun = (an or simdi()).astimezone(TURKIYE_SAATI).date()
    sorgu = (
        select(IlanKaydi, Siniflandirma, IlanAyrinti)
        .join(Siniflandirma, Siniflandirma.kimlik == IlanKaydi.kimlik)
        .outerjoin(IlanAyrinti, IlanAyrinti.kimlik == IlanKaydi.kimlik)
        .where(IlanKaydi.aktif.is_(True), IlanKaydi.gizli.is_(False), Siniflandirma.ogrenciye_uygun.is_(True))
        .order_by(IlanKaydi.ilk_gorulme.desc(), IlanKaydi.firma)
    )
    if sonra is not None:  # SQLite saat dilimi saklamaz: karşılaştırma UTC
        sorgu = sorgu.where(IlanKaydi.ilk_gorulme > sonra.astimezone(UTC))
    if once is not None:
        sorgu = sorgu.where(IlanKaydi.ilk_gorulme <= once.astimezone(UTC))
    sonuclar = list(oturum.execute(sorgu))
    firmalar = _firma_profilleri(oturum, {ilan.firma for ilan, _, _ in sonuclar})
    satirlar = []
    for ilan, sinif, ayrinti in sonuclar:
        etiket, kaynaklar = firmalar.get(ilan.firma, (set(), set()))
        etiket = etiket | set(ilan.etiket or [])
        ayrinti_sozlugu = _ayrinti_sozlugu(ayrinti)
        yillar = baslik_yillari(ilan.baslik) | donem_yillari(ilan.aciklama)
        if ayrinti is not None and ayrinti.donem_yili:
            yillar.add(ayrinti.donem_yili)
        durum = guncellik(
            ilan.kaynak,
            ilan.yayin_tarihi,
            ayrinti.son_basvuru if ayrinti else None,
            ayrinti.ilan_tarihi if ayrinti else None,
            yillar,
            bugun,
            ayrinti.ilan_turu if ayrinti else "is",
        )
        if durum["bayat"] and not bayatlar_dahil:
            continue
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
                "ayrinti": ayrinti_sozlugu,
                "alanlar": alanlari_bul(
                    sinif.rol,
                    sinif.yapay_zeka,
                    ilan.baslik,
                    ilan.firma,
                    etiket,
                    bool(ayrinti and ayrinti.savunma_kaniti) or savunma_metinde(ilan.aciklama),
                ),
                "calisma_modeli": calisma_modeli(ilan.konum, (ayrinti_sozlugu or {}).get("calisma_modeli")),
                "girisim": girisim_mi(ilan.firma, etiket, kaynaklar, ilan.kaynak),
                "yayin": durum["yayin"],
                "surekli_acik": durum["surekli_acik"],
                "ilan_turu": ayrinti.ilan_turu if ayrinti else "is",
                "seviye_etiketi": seviye_etiketi(sinif.seviye, ilan.baslik, ayrinti.ilan_turu if ayrinti else "is"),
                **({"bayat": durum["bayat"]} if bayatlar_dahil else {}),
            }
        )
    satirlar.sort(key=lambda i: siralama_anahtari(i, bugun))
    return satirlar


def _firma_profilleri(oturum: Session, adlar: set[str]) -> dict[str, tuple[set[str], set[str]]]:
    """Firma adı → (etiketler, geldiği listeler). Aynı adla birden çok kayıt varsa birleştirilir."""
    profiller: dict[str, tuple[set[str], set[str]]] = {}
    for parca in _parcalar(sorted(adlar)):
        for ad, etiket, kaynak in oturum.execute(
            select(Firma.ad, Firma.etiket, Firma.kaynak).where(Firma.ad.in_(parca))
        ):
            etiketler, kaynaklar = profiller.setdefault(ad, (set(), set()))
            etiketler |= set(etiket or [])
            kaynaklar |= {k for k in (kaynak or "").split(",") if k}
    return profiller


def _ayrinti_sozlugu(a: IlanAyrinti | None) -> dict | None:
    if (
        a is None or a.model == "metin-yok"
    ):  # metni olmayan ilan: tekrar denenmesin diye boş kayıt var, gösterilecek bir şey yok
        return None
    return {
        "ozet": a.ozet,
        "son_basvuru": a.son_basvuru,
        "ilan_tarihi": a.ilan_tarihi,
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


def ilan_gizle(oturum: Session, url: str, gizli: bool = True) -> list[IlanKaydi]:
    """Elle onay: yanlış ilanı sitede ve e-postada gösterme (`gizli=False` geri alır). Etkilenen ilanlar döner; adres
    bulunamazsa boş liste. Aynı firma + başlıklı kopyalar da birlikte gizlenir: bülten onları aynı ilan sayar
    (isleme/tekillestirme.py → ilan_anahtari), biri gizlenip öteki kalsaydı yanlış ilan öteki adresle giderdi.
    Tarama `gizli` alanına dokunmaz: ilan yeniden görülse de açılmaz. Başka adresle yeniden yayınlanan kopya yeni ilandır,
    yeniden gizlenmesi gerekir."""
    adres = url.strip()
    hedef = oturum.scalars(select(IlanKaydi).where(IlanKaydi.url.in_({adres, adres.rstrip("/"), adres + "/"}))).first()
    if hedef is None:
        return []
    anahtar = ilan_anahtari(hedef.firma, hedef.baslik)
    kopyalar = [
        i
        for i in oturum.scalars(select(IlanKaydi).where(IlanKaydi.firma == hedef.firma))
        if ilan_anahtari(i.firma, i.baslik) == anahtar
    ]
    for i in kopyalar:
        i.gizli = gizli
    return kopyalar
