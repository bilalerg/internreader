"""Firmalar: ekleme/güncelleme, keşif sırası, ilan sistemi bilgisi."""

import csv
import io
import re
import urllib.parse
from collections.abc import Iterable
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from internreader.db import Firma, IlanKaydi, simdi
from internreader.isleme.kategori import girisim_gerekcesi
from internreader.model import FirmaBilgisi


def firma_anahtari(ad: str, web: str | None) -> str:
    if web:
        adres = web if web.startswith("http") else f"https://{web}"
        host = urllib.parse.urlparse(adres).netloc.lower().split(":")[0]
        if host:
            return host.removeprefix("www.")
    sade = re.sub(r"\b(a\.?ş\.?|anonim|şirketi|ltd|şti|limited|ticaret|sanayi|ve|tic|san)\b", " ", ad.lower())
    return "ad:" + re.sub(r"[^a-z0-9çğıöşü]", "", sade)[:60]


def firma_ekle_veya_guncelle(
    oturum: Session,
    ad: str,
    web: str = "",
    ats: str = "",
    slug: str = "",
    kariyer: str = "",
    etiket: Iterable[str] = (),
    kaynak: str = "",
) -> bool:
    """Firmayı ekler; zaten varsa yalnızca boş alanlarını doldurur. Yeni eklendiyse True döner.

    Aynı firma bir listede web adresiyle, başka bir listede adresiz gelebilir. Önce alan adıyla, sonra adla
    aranır; adresiz kayıt sonradan adres öğrenirse anahtarı alan adına yükseltilir (çift kayıt oluşmaz).
    """
    anahtar = firma_anahtari(ad, web)
    firma = oturum.scalar(select(Firma).where(Firma.anahtar == anahtar))
    if firma is None:
        ad_anahtari = firma_anahtari(ad, "")
        firma = oturum.scalar(
            select(Firma).where((Firma.anahtar == ad_anahtari) | (Firma.ad == ad.strip())).order_by(Firma.id).limit(1)
        )
        if firma is not None and web and firma.anahtar.startswith("ad:"):
            firma.anahtar = anahtar
    yeni = firma is None
    if yeni:
        firma = Firma(anahtar=anahtar, ad=ad.strip(), etiket=[], kaynak=kaynak)
        oturum.add(firma)
    firma.web = firma.web or web or None
    if ats and not firma.ats:
        firma.ats, firma.slug = ats, slug
    firma.kariyer = firma.kariyer or kariyer or None
    firma.etiket = sorted(set(firma.etiket or []) | {e for e in etiket if e})
    if kaynak and kaynak not in (firma.kaynak or ""):
        firma.kaynak = ",".join(x for x in (firma.kaynak, kaynak) if x)
    return yeni


def _firma_bilgisi(f: Firma) -> FirmaBilgisi:
    return FirmaBilgisi(
        id=f.id,
        ad=f.ad,
        web=f.web or "",
        ats=f.ats or "",
        slug=f.slug or "",
        kariyer=f.kariyer or "",
        etiket=list(f.etiket or []),
    )


def aktif_firmalar(oturum: Session) -> list[FirmaBilgisi]:
    return [_firma_bilgisi(f) for f in oturum.scalars(select(Firma).where(Firma.aktif.is_(True)).order_by(Firma.id))]


def kesif_bekleyenler(
    oturum: Session, yenileme_gunu: int = 30, sinir: int | None = None, kaynak: str | None = None
) -> list[FirmaBilgisi]:
    """Web adresi olup ilan sistemi bilinmeyen ve son `yenileme_gunu` içinde keşfi yapılmamış firmalar.
    `kaynak` verilirse yalnızca o listeden gelenler (ör. yeni eklenen bir tohum listesi)."""
    esik = simdi() - timedelta(days=yenileme_gunu)
    sorgu = (
        select(Firma)
        .where(Firma.aktif.is_(True), Firma.web.is_not(None), Firma.ats.is_(None))
        .where((Firma.kesif_tarihi.is_(None)) | (Firma.kesif_tarihi < esik))
        .order_by(Firma.id)
    )
    if kaynak:
        sorgu = sorgu.where(Firma.kaynak.contains(kaynak))
    if sinir:
        sorgu = sorgu.limit(sinir)
    return [_firma_bilgisi(f) for f in oturum.scalars(sorgu)]


def kesif_sonucu_yaz(oturum: Session, firma_id: int, ats: str, slug: str, kariyer: str) -> None:
    """Keşifte bulunanı yazar. Bulunamayan bilgi silinmez (ör. CSV'den gelen kariyer sayfası korunur)."""
    firma = oturum.get(Firma, firma_id)
    if ats:
        firma.ats, firma.slug = ats, slug
    if kariyer:
        firma.kariyer = kariyer
    firma.kesif_tarihi = simdi()


def ats_kaydini_sifirla(oturum: Session, firma_idler: Iterable[int]) -> None:
    """İlan panosu artık bulunmayan firmaların ATS bilgisini siler ve keşif sırasına geri koyar."""
    for firma_id in firma_idler:
        firma = oturum.get(Firma, firma_id)
        if firma is not None:
            firma.ats = firma.slug = firma.kesif_tarihi = None


def firmayi_kapat(oturum: Session, ad_ya_da_alan: str) -> int:
    """ "İlanımı kaldır" talebi: firmayı taramadan çıkarır, açık ilanlarını yayından kaldırır. Etkilenen firma sayısı.

    Firma adıyla ("Acme Teknoloji") ya da alan adıyla ("acme.com") bulunur. Kayıt silinmez, `aktif=False` olur:
    böylece firma listesi yeniden içe aktarılsa da firma geri gelmez (içe aktarma yalnızca boş alanları doldurur).
    """
    deger = ad_ya_da_alan.strip()
    kosul = Firma.ad == deger
    if "." in deger and " " not in deger:
        kosul = kosul | (Firma.anahtar == firma_anahtari("", deger))
    firmalar = list(oturum.scalars(select(Firma).where(kosul)))
    for f in firmalar:
        f.aktif = False
        oturum.execute(update(IlanKaydi).where(IlanKaydi.firma == f.ad).values(aktif=False))
    return len(firmalar)


def girisim_listesi_csv(oturum: Session) -> str:
    """Bilal'in gözden geçirmesi için: girişim sayılan ve aday firmalar, gerekçesiyle (önce evet, sonra aday)."""
    satirlar = []
    for f in oturum.scalars(select(Firma).where(Firma.aktif.is_(True))):
        kaynaklar = {k for k in (f.kaynak or "").split(",") if k}
        gerekce = girisim_gerekcesi(f.ad, set(f.etiket or []), kaynaklar, f.ats or "")
        if not gerekce.startswith("hayır"):
            satirlar.append(
                (gerekce.split(":")[0], f.ad, gerekce, f.web or "", ",".join(f.etiket or []), f.kaynak or "")
            )
    cikti = io.StringIO()
    yazici = csv.writer(cikti, lineterminator="\n")
    yazici.writerow(["karar", "firma", "gerekce", "web", "etiket", "listeler"])
    yazici.writerows(sorted(satirlar, key=lambda s: (s[0] != "evet", s[1].casefold())))
    return cikti.getvalue()
