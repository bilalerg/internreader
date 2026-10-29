"""Proje ayarları tek yerde.

Gizli değerler (API anahtarı, veritabanı adresi) kodda değil, .env dosyasında ya da ortam değişkenlerinde durur.
Yerelde varsayılan veritabanı SQLite dosyasıdır; sunucuda DATABASE_URL ile Postgres verilir. Kod ikisinde de aynıdır.
"""

import os
from dataclasses import dataclass, field
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
    # Günlük e-posta bütçesi. Varsayılanlar Brevo'nun ücretsiz planına (günde 300) göre: 250 bülten + 50 onay.
    # Ücretli plana geçilince ortam değişkenleriyle yükseltilir; 0 = sınırsız.
    gunluk_bulten_siniri: int = 250
    gunluk_onay_siniri: int = 50
    arama_saglayici: str = ""  # "serper", "brave" ya da "" (arama keşfi kapalı)
    arama_anahtari: str = field(default="", repr=False)  # seçilen sağlayıcının API anahtarı; asla yazdırılmaz


def arama_ayari() -> tuple[str, str]:
    """INTERNREADER_ARAMA_SAGLAYICI açıkça verilmemişse anahtarı bulunan ilk sağlayıcı seçilir."""
    anahtarlar = {"serper": os.getenv("SERPER_API_KEY", ""), "brave": os.getenv("BRAVE_API_KEY", "")}
    secilen = os.getenv("INTERNREADER_ARAMA_SAGLAYICI", "").strip().lower()
    if not secilen:
        secilen = next((ad for ad, anahtar in anahtarlar.items() if anahtar), "")
    return (secilen, anahtarlar[secilen]) if anahtarlar.get(secilen) else ("", "")


GELISTIRME_ANAHTARI = "yalnizca-gelistirme-icin-degistir"


def _ortam(ad: str, varsayilan: str) -> str:
    """Ortam değişkeni; tanımsız ya da BOŞ ise varsayılan. GitHub Actions'ta tanımlanmamış bir gizli değer boş metin
    olarak gelir: int("") çöker, boş gizli anahtar ise imzaları anlamsız kılar."""
    return os.getenv(ad) or varsayilan


def ayarlari_oku() -> Ayarlar:
    env_yukle()
    arama_saglayici, arama_anahtari = arama_ayari()
    return Ayarlar(
        veritabani_url=_ortam("DATABASE_URL", f"sqlite:///{(VERI / 'internreader.db').as_posix()}"),
        model=_ortam("INTERNREADER_MODEL", "claude-haiku-5-5"),
        calisma_basina_yz_tavani_usd=float(_ortam("INTERNREADER_YZ_TAVANI_USD", "0.50")),
        aylik_yz_tavani_usd=float(_ortam("INTERNREADER_AYLIK_YZ_TAVANI_USD", "2.00")),
        is_parcacigi=int(_ortam("INTERNREADER_IS_PARCACIGI", "8")),
        yz_is_parcacigi=int(_ortam("INTERNREADER_YZ_IS_PARCACIGI", "4")),
        http_zaman_asimi=int(_ortam("INTERNREADER_HTTP_ZAMAN_ASIMI", "25")),
        kullanici_ajani="InternReader/0.2 (+https://github.com/bilalerg/internreader)",
        site_adresi=_ortam("INTERNREADER_SITE_ADRESI", "http://localhost:4321").rstrip("/"),
        gizli_anahtar=_ortam("INTERNREADER_GIZLI_ANAHTAR", GELISTIRME_ANAHTARI),
        smtp_sunucu=_ortam("SMTP_SUNUCU", ""),
        smtp_port=int(_ortam("SMTP_PORT", "587")),
        smtp_kullanici=_ortam("SMTP_KULLANICI", ""),
        smtp_parola=_ortam("SMTP_PAROLA", ""),
        eposta_kimden=_ortam("EPOSTA_KIMDEN", "InternReader <bulten@localhost>"),
        eposta_yanit=_ortam("EPOSTA_YANIT", ""),
        yz_toplu=_ortam("INTERNREADER_YZ_TOPLU", "0") == "1",
        gunluk_bulten_siniri=int(_ortam("INTERNREADER_GUNLUK_BULTEN_SINIRI", "250")),
        gunluk_onay_siniri=int(_ortam("INTERNREADER_GUNLUK_ONAY_SINIRI", "50")),
        arama_saglayici=arama_saglayici,
        arama_anahtari=arama_anahtari,
    )
