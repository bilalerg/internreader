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


def _duz_metin(ham: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", ham))).strip()


_GORUNMEZ = re.compile(r"(?is)<(script|style|noscript|svg|template|head)[\s>].*?</\1>")
_DOLASIM = re.compile(r"(?is)<(nav|footer)[\s>].*?</\1>")
_SITE_ISKELETI = re.compile(r"(?is)<(nav|header|footer|aside)[\s>].*?</\1>")
EN_AZ_ICERIK = 200  # bundan kısa <main>/<article> gerçek içerik değildir (ör. yalnızca başlık)


def ilan_metni(ham: str, baslik: str = "") -> str:
    """İlanın kendi sayfasından yalnızca ilan metni. Sayfanın başındaki menü modele gitmesin diye (Yeditek'te 10.536
    karakter menü, 6.000 karakterlik sınırda ilan hiç görünmüyordu; özet menüden üretiliyordu).
    Sıra: <main>, en uzun <article>; ikisi de yoksa nav/header/footer/aside atılır ve başlığın son geçtiği yerden
    başlanır. <main> içinde aside kalır: "Son başvuru" gibi ilan bilgileri orada olabilir (Beakwise).
    Kariyer sayfası okuyucusu bu fonksiyonu kullanmaz; onun için sayfanın tamamı gerekir (html_ayikla)."""
    temiz = _GORUNMEZ.sub(" ", ham)
    makaleler = sorted(re.findall(r"(?is)<article[\s>].*?</article>", temiz), key=len, reverse=True)
    for blok in re.findall(r"(?is)<main[\s>].*?</main>", temiz) + makaleler[:1]:
        metin = _duz_metin(_DOLASIM.sub(" ", blok))
        if len(metin) >= EN_AZ_ICERIK:
            return metin
    metin = _duz_metin(_SITE_ISKELETI.sub(" ", temiz))
    kucuk, aranan = _kucuk(metin), _kucuk(baslik)
    bas = kucuk.rfind(aranan, 0, max(0, len(kucuk) - EN_AZ_ICERIK)) if aranan else -1
    return metin[max(0, bas - 120) :] if bas >= 0 else metin  # başlıktan hemen önce tarih olabilir


def _kucuk(metin: str) -> str:
    """Büyük "İ" küçülünce iki karakter olur; önce "I" yapılır ki kesme konumları asıl metinle aynı kalsın."""
    return " ".join(metin.split()).replace("İ", "I").lower()


def ilan_bolumu(metin: str, baslik: str, diger_basliklar: list[str], sinir: int = 2_500) -> str:
    """Tek sayfada birden çok ilan listelenen kariyer sayfasında (ilan adresi #çapa ile biter) ilanın kendi bölümü:
    başlığın geçtiği yerden bir sonraki ilan başlığına kadar (en fazla `sinir` karakter). Başlık sayfada birkaç kez
    geçebilir (üstte liste, aşağıda açıklama); en uzun bölüm alınır. Başlık bulunamazsa boş metin."""
    metin = " ".join(metin.split())
    kucuk, aranan = _kucuk(metin), _kucuk(baslik)
    digerleri = [_kucuk(d) for d in diger_basliklar if _kucuk(d) != aranan]
    en_uzun, bas = "", kucuk.find(aranan) if aranan else -1
    while bas >= 0:
        son = bas + sinir
        for d in digerleri:
            i = kucuk.find(d, bas + len(aranan))
            if 0 <= i < son:
                son = i
        if son - bas > len(en_uzun):
            en_uzun = metin[bas:son].strip()
        bas = kucuk.find(aranan, bas + len(aranan))
    return en_uzun


def sayfa_oku(http: HttpIstemci, url: str) -> SayfaIcerigi:
    son_url, ham = http.sayfa(url)
    return html_ayikla(ham, son_url)
