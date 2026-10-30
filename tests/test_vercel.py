"""Ücretsiz kurulum (Vercel + Neon + GitHub Actions) için gereken uyumluluklar."""

import importlib.util
import json
from pathlib import Path

from fastapi.testclient import TestClient

from internreader.ayar import ayarlari_oku
from internreader.db import surucu_ekle

KOK = Path(__file__).resolve().parents[1]


def test_neon_adresi_psycopg_surucusune_cevrilir():
    neon = "postgresql://kullanici:parola@ep-x-pooler.eu-central-1.aws.neon.tech/neondb?sslmode=require"
    assert surucu_ekle(neon).startswith("postgresql+psycopg://kullanici:parola@ep-x-pooler")
    assert surucu_ekle("postgres://a:b@h/d") == "postgresql+psycopg://a:b@h/d"
    assert surucu_ekle("postgresql+psycopg://a:b@h/d") == "postgresql+psycopg://a:b@h/d"  # zaten doğru
    assert surucu_ekle("sqlite:///x.db") == "sqlite:///x.db"


def test_bos_gizli_degerler_varsayilana_duser(monkeypatch):
    # GitHub Actions'ta tanımlanmamış gizli değer boş metin olarak gelir
    for ad in ("SMTP_PORT", "INTERNREADER_GIZLI_ANAHTAR", "EPOSTA_KIMDEN", "DATABASE_URL"):
        monkeypatch.setenv(ad, "")
    ayar = ayarlari_oku()
    assert ayar.smtp_port == 587
    assert ayar.gizli_anahtar == "yalnizca-gelistirme-icin-degistir"  # boş anahtarla imza atılmaz
    assert ayar.eposta_kimden.startswith("InternReader")
    assert ayar.veritabani_url.startswith("sqlite")


def test_vercel_girisi_calisir_ve_istemci_ipsi_basliktan_okunur(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'v.db').as_posix()}")
    monkeypatch.setenv("VERCEL", "1")
    spec = importlib.util.spec_from_file_location("vercel_girisi", KOK / "api" / "index.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    istemci = TestClient(modul.app)
    assert istemci.get("/api/saglik").status_code == 200
    # Hız sınırı gerçek IP'ye göre işler: farklı x-real-ip'ler birbirinin sınırını tüketmez
    govde = {"eposta": "deneme@ornek.com", "kvkk_onay": True}
    for _ in range(30):
        istemci.post("/api/abone", json=govde, headers={"x-real-ip": "1.1.1.1"})
    assert istemci.post("/api/abone", json=govde, headers={"x-real-ip": "1.1.1.1"}).status_code == 429
    assert istemci.post("/api/abone", json=govde, headers={"x-real-ip": "2.2.2.2"}).status_code != 429


def test_vercel_ayari_api_yonlendirmesi_ve_guvenlik_basliklari():
    ayar = json.loads((KOK / "vercel.json").read_text(encoding="utf-8"))
    assert {"source": "/api/(.*)", "destination": "/api/index"} in ayar["rewrites"]
    assert ayar["outputDirectory"] == "web/dist"
    basliklar = {b["key"] for kural in ayar["headers"] for b in kural["headers"]}
    assert {"Content-Security-Policy", "Strict-Transport-Security", "X-Content-Type-Options"} <= basliklar
    assert "INTERNREADER_CIKTI=public/veri" in ayar["buildCommand"]
