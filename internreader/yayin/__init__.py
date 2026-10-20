"""Yayın: veritabanındaki öğrenci ilanlarını insanların göreceği biçimlere çevirir (WhatsApp, README, JSON)."""

import re
from datetime import datetime, timedelta, timezone

from internreader.isleme.sehir import sehirleri_bul, uzaktan_mi

# Türkiye 2016'dan beri yaz saati uygulamıyor: sabit UTC+3. (zoneinfo Windows'ta ek paket istediği için kullanılmadı.)
TURKIYE_SAATI = timezone(timedelta(hours=3))

SEVIYE_ADI = {
    "staj": "Staj",
    "uzun_donem_staj": "Uzun dönem staj",
    "yari_zamanli": "Yarı zamanlı",
    "junior": "Junior",
    "yeni_mezun": "Yeni mezun",
    "belirsiz": "Belirsiz",
    "deneyimli": "Deneyimli",
}
ROL_ADI = {
    "yazilim": "Yazılım",
    "yapay_zeka": "Yapay zekâ",
    "veri": "Veri",
    "diger_teknik": "Diğer teknik",
    "teknik_degil": "Teknik değil",
}
AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]


def tarih_yazisi(an) -> str:
    return f"{an.day} {AYLAR[an.month - 1]} {an.year}"


def turkiye_tarihi(iso_utc: str) -> str:
    """Veritabanındaki UTC zamanını Türkiye'deki takvim gününe çevirir (YYYY-AA-GG)."""
    return datetime.fromisoformat(iso_utc).astimezone(TURKIYE_SAATI).date().isoformat()


def guvenli_url(url: str) -> str:
    """Markdown bağlantısını bozacak karakterleri kodlar."""
    return url.replace(" ", "%20").replace("(", "%28").replace(")", "%29")


_PARANTEZ = re.compile(r"\s*\([^)]*\)\s*")
_HUKUKI_EK = re.compile(
    r"(?i)\s*\b(anonim\s+şirketi|a\.\s?ş\.?|ltd\.?\s*şti\.?|limited\s+şirketi|sanayi\s+ve\s+ticaret|san\.?\s*ve\s*tic\.?)"
    r"(?=\s|$|\.).*$"
)
_SEKTOR_KELIMESI = re.compile(
    r"(?i)\s+\b(bili[sş]im|teknoloji(leri)?|yaz[ıi]l[ıi]m|dan[ıi][sş]manl[ıi]k|elektronik|m[üu]hendislik|hizmetleri)\b.*$"
)


def gorunen_ad(ad: str) -> str:
    """Resmî unvanı okunur ada çevirir: "Beakwise Bilişim Teknolojileri ve Danışmanlık A.Ş." → "Beakwise",
    "Hitit (havayolu yazılımı)" → "Hitit". Listelerdeki açıklama notları ve hukuki ekler kullanıcıya gösterilmez."""
    sade = _HUKUKI_EK.sub("", _PARANTEZ.sub(" ", ad)).strip(" ,.")
    kisa = _SEKTOR_KELIMESI.sub("", sade).strip(" ,.")
    return kisa or sade or ad.strip()


def zenginlestir(ilan: dict) -> dict:
    """Yayın çıktıları için türetilmiş alanlar: okunur firma adı, şehirler, uzaktan mı."""
    return {
        **ilan,
        "firma_gorunen": gorunen_ad(ilan["firma"]),
        "sehirler": sehirleri_bul(ilan.get("konum", "")),
        "uzaktan": uzaktan_mi(ilan.get("konum", "")),
    }
