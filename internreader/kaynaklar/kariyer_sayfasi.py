"""Kariyer sayfası indirme ve HTML'den görünür metin + bağlantı listesi çıkarma (yapay zekâdan önceki adım)."""

import html
import re
import urllib.parse
from dataclasses import dataclass

from internreader.ag import HttpIstemci

AZAMI_BAGLANTI = 150


@dataclass
class SayfaIcerigi:
    url: str  # yönlendirmeden sonraki son adres
    metin: str  # görünür metin
    baglantilar: list[tuple[str, str]]  # (bağlantı yazısı, mutlak adres)


def mutlak_adres(taban_url: str, href: str) -> str | None:
    """Sayfadaki göreli bağlantıyı tam adrese çevirir. Bozuk adreste (ör. "http://[getaquotelink]") urljoin hata
    fırlatır; gerçek bir sitede bu hata 1.300 firmalık taramayı çökertmişti → None döner, bağlantı atlanır."""
    try:
        return urllib.parse.urljoin(taban_url, html.unescape(href))
    except ValueError:
        return None


def html_ayikla(ham: str, taban_url: str) -> SayfaIcerigi:
    """HTML'den görünür metni ve sayfadaki bağlantıları çıkarır. Ağ kullanmaz (test edilebilir)."""
    temiz = re.sub(r"(?is)<(script|style|noscript|svg|template)[^>]*>.*?</\1>", " ", ham)
    baglantilar = []
    for href, icerik in re.findall(r'(?is)<a[^>]+href=["\']([^"\'#][^"\']{0,300})["\'][^>]*>(.*?)</a>', temiz):
        yazi = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", icerik))).strip()
        mutlak = mutlak_adres(taban_url, href)
        if yazi and mutlak and mutlak.startswith("http") and len(yazi) < 120:
            baglantilar.append((yazi, mutlak))
    metin = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", temiz))).strip()
    return SayfaIcerigi(url=taban_url, metin=metin, baglantilar=list(dict.fromkeys(baglantilar))[:AZAMI_BAGLANTI])


def sayfa_oku(http: HttpIstemci, url: str) -> SayfaIcerigi:
    son_url, ham = http.sayfa(url)
    return html_ayikla(ham, son_url)
