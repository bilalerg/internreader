"""Proje ayarları tek yerde.

Gizli değerler (API anahtarı, veritabanı adresi) kodda değil, .env dosyasında ya da ortam değişkenlerinde durur.
Yerelde varsayılan veritabanı SQLite dosyasıdır; sunucuda DATABASE_URL ile Postgres verilir. Kod ikisinde de aynıdır.
"""

import os
from dataclasses import dataclass
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
VERI = KOK / "veri"
CIKTI = KOK / "cikti"

# 1 milyon token başına USD (girdi, çıktı). Kaynak: Anthropic fiyat tablosu, Ekim 2026.
MODEL_FIYATLARI = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
}


def env_yukle(yol: Path = KOK / ".env") -> None:
    """.env dosyasındaki ANAHTAR=değer satırlarını ortam değişkenlerine yükler (var olanları ezmez)."""
    if not yol.exists():
        return
    for satir in yol.read_text(encoding="utf-8").splitlines():
        satir = satir.strip()
        if not satir or satir.startswith("#") or "=" not in satir:
            continue
        ad, deger = satir.split("=", 1)
        os.environ.setdefault(ad.strip(), deger.strip())


@dataclass(frozen=True)
class Ayarlar:
    veritabani_url: str
    model: str
    calisma_basina_yz_tavani_usd: float  # bir çalıştırmada yapay zekâya harcanabilecek en fazla tutar
    aylik_yz_tavani_usd: float  # takvim ayı boyunca toplam en fazla tutar (dolunca sistem yapay zekâsız çalışır)
    is_parcacigi: int  # aynı anda kaç siteye bağlanılacağı
    yz_is_parcacigi: int  # aynı anda kaç yapay zekâ isteği atılacağı (hız sınırına takılmamak için düşük)
    http_zaman_asimi: int
    kullanici_ajani: str
    site_adresi: str  # e-postalardaki bağlantıların kökü (ör. https://internreader.dev)
    gizli_anahtar: str  # abonelikten çıkış bağlantılarını imzalar; sunucuda mutlaka değiştirilmeli
    # E-posta (SMTP). Sunucu boşsa e-postalar gönderilmez, cikti/giden_eposta/ klasörüne yazılır.
    smtp_sunucu: str
    smtp_port: int
    smtp_kullanici: str
    smtp_parola: str
    eposta_kimden: str  # "InternReader <bulten@alan-adi>"
    eposta_yanit: str  # yanıtların gideceği adres (boş olabilir)
    yz_toplu: bool  # yapay zekâ isteklerini Message Batches API ile yarı fiyatına gönder (sonuç dakikalar sürebilir)


GELISTIRME_ANAHTARI = "yalnizca-gelistirme-icin-degistir"


def ayarlari_oku() -> Ayarlar:
    env_yukle()
    return Ayarlar(
        veritabani_url=os.getenv("DATABASE_URL", f"sqlite:///{(VERI / 'internreader.db').as_posix()}"),
        model=os.getenv("INTERNREADER_MODEL", "claude-haiku-5-5"),
        calisma_basina_yz_tavani_usd=float(os.getenv("INTERNREADER_YZ_TAVANI_USD", "0.50")),
        aylik_yz_tavani_usd=float(os.getenv("INTERNREADER_AYLIK_YZ_TAVANI_USD", "2.00")),
        is_parcacigi=int(os.getenv("INTERNREADER_IS_PARCACIGI", "8")),
        yz_is_parcacigi=int(os.getenv("INTERNREADER_YZ_IS_PARCACIGI", "4")),
        http_zaman_asimi=int(os.getenv("INTERNREADER_HTTP_ZAMAN_ASIMI", "25")),
        kullanici_ajani="InternReader/0.2 (+https://github.com/bilalerg/internreader)",
        site_adresi=os.getenv("INTERNREADER_SITE_ADRESI", "http://localhost:4321").rstrip("/"),
        gizli_anahtar=os.getenv("INTERNREADER_GIZLI_ANAHTAR", GELISTIRME_ANAHTARI),
        smtp_sunucu=os.getenv("SMTP_SUNUCU", ""),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_kullanici=os.getenv("SMTP_KULLANICI", ""),
        smtp_parola=os.getenv("SMTP_PAROLA", ""),
        eposta_kimden=os.getenv("EPOSTA_KIMDEN", "InternReader <bulten@localhost>"),
        eposta_yanit=os.getenv("EPOSTA_YANIT", ""),
        yz_toplu=os.getenv("INTERNREADER_YZ_TOPLU", "0") == "1",
    )
