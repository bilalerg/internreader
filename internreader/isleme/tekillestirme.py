"""Tekilleştirme: aynı ilan birden fazla kez gelirse (ör. bir firma aynı pozisyonu iki şehir için listelerse) tek kayıt.

Anahtar ilanın URL'sinden türetilen kimliktir. Aynı kimlik tekrar gelirse konumlar birleştirilir.
Aynı ilan farklı URL'lerle de yayınlanabiliyor (Binance Accelerator Program üç adreste); kayıtlar ayrı kalır, bülten
`ilan_anahtari` ile aynı ilanı bir kez gönderir.
"""

import re
import unicodedata
from collections.abc import Iterable

from internreader.model import Ilan

# Büyük "I" Türkçede "ı", İngilizcede "i" olur; başlıklar iki dilde yazıldığı için noktalı ve noktasız i tek harf sayılır
_I_HARFLERI = str.maketrans({"İ": "i", "I": "i", "ı": "i"})
_HARF_DISI = re.compile(r"[\W_]+")


def _sade(metin: str) -> str:
    """Türkçe küçük harf; şapka ve noktalar düşer ("Yazılım" = "YAZILIM" = "yazilim"), noktalama ve boşluk silinir
    ("Front-End" = "Front End" = "Frontend")."""
    ayrik = unicodedata.normalize("NFKD", (metin or "").translate(_I_HARFLERI).lower())
    return _HARF_DISI.sub("", "".join(h for h in ayrik if not unicodedata.combining(h)))


def ilan_anahtari(firma: str, baslik: str) -> str:
    """Aynı ilanı farklı URL'de tanımak için firma + başlık anahtarı. Firma farklıysa anahtar da farklıdır: başka
    firmanın aynı başlıklı ilanı ayrı ilandır."""
    return f"{_sade(firma)}|{_sade(baslik)}"


def _ayni_firma(a: str, b: str) -> bool:
    """İlan sitesinde firma adı farklı yazılabiliyor ("Vertigo" / "Vertigo Games", "Analog Devices, Inc.")."""
    return a == b or (min(len(a), len(b)) >= 4 and (a.startswith(b) or b.startswith(a)))


def bilinenleri_ele(ilanlar: list[Ilan], bilinen: Iterable[tuple[str, str]]) -> list[Ilan]:
    """İlan sitesinden gelen sonuçlardan, firmanın kendi kaynağından zaten okuduğumuz ilanları (firma, başlık) eler."""
    firmalar: dict[str, set[str]] = {}
    for firma, baslik in bilinen:
        firmalar.setdefault(_sade(baslik), set()).add(_sade(firma))
    return [i for i in ilanlar if not any(_ayni_firma(_sade(i.firma), f) for f in firmalar.get(_sade(i.baslik), ()))]


def firma_adlarini_esle(ilanlar: list[Ilan], adlar: Iterable[str]) -> None:
    """İlan sitesindeki "BAYKAR" bizdeki "Baykar" kaydına bağlanır: firmanın etiketleri (savunma, girişim) ilana geçer."""
    harita = {_sade(a): a for a in adlar}
    for i in ilanlar:
        i.firma = harita.get(_sade(i.firma), i.firma)


def tekillestir(ilanlar: list[Ilan]) -> list[Ilan]:
    tekil: dict[str, Ilan] = {}
    for ilan in ilanlar:
        onceki = tekil.get(ilan.kimlik)
        if onceki is None:
            tekil[ilan.kimlik] = ilan
        elif ilan.konum and ilan.konum not in onceki.konum:
            onceki.konum = f"{onceki.konum}, {ilan.konum}" if onceki.konum else ilan.konum
    return list(tekil.values())
