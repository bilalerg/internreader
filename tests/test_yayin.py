"""Yayın biçimleri: tarih dönüşümü, bağlantı güvenliği, WhatsApp özetinin sınırları."""

from datetime import datetime

from internreader.yayin import TURKIYE_SAATI, gorunen_ad, guvenli_url, turkiye_tarihi, zenginlestir
from internreader.yayin.istatistik import sehir_dagilimi
from internreader.yayin.readme import tablo_metni
from internreader.yayin.whatsapp import AZAMI_ILAN, ozet_metni, taze_mi

AN = datetime(2026, 10, 18, 9, 0, tzinfo=TURKIYE_SAATI)


def ilan(no=1, url="https://jobs.lever.co/firma/1"):
    return {
        "firma": "Firma",
        "baslik": f"Software Engineering Intern {no}",
        "url": url,
        "konum": "",
        "seviye": "staj",
        "rol": "yazilim",
        "yapay_zeka": "arti",
        "ilk_gorulme": "2026-10-17T22:30:00+00:00",  # Türkiye'de 18 Ekim 01:30
    }


def test_eklenme_tarihi_turkiye_saatine_gore():
    assert turkiye_tarihi("2026-10-17T22:30:00+00:00") == "2026-10-18"
    assert "| 2026-10-18 |" in tablo_metni([ilan()], AN)


def test_parantezli_baglanti_markdowni_bozmaz():
    assert guvenli_url("https://f.com/ilan (staj)") == "https://f.com/ilan%20%28staj%29"


def test_whatsapp_ozeti_yeni_ilan_yoksa_cikmaz_ve_uzun_listeyi_keser():
    assert ozet_metni([], AN) is None
    metin = ozet_metni([ilan(n) for n in range(AZAMI_ILAN + 5)], AN, "https://github.com/x")
    assert "+5 ilan daha: https://github.com/x" in metin and "18 Ekim 2026" in metin


def test_kaynakta_aylardir_acik_ilan_yeni_diye_duyurulmaz():
    assert taze_mi({**ilan(), "yayin_tarihi": "2026-10-01"}, AN)
    assert not taze_mi({**ilan(), "yayin_tarihi": "2024-03-15"}, AN)  # yeni keşfedilen firmanın eski ilanı
    assert taze_mi({**ilan(), "yayin_tarihi": ""}, AN)  # tarih bilinmiyorsa taze


def test_resmi_unvan_okunur_ada_cevrilir():
    assert gorunen_ad("Beakwise Bilişim Teknolojileri ve Danışmanlık A.Ş.") == "Beakwise"
    assert gorunen_ad("Hitit (havayolu yazılımı)") == "Hitit"
    assert gorunen_ad("ASPİLSAN Enerji A.Ş.") == "ASPİLSAN Enerji"
    assert gorunen_ad("Good Job Games") == "Good Job Games"


def test_sehir_dagilimi_ve_zenginlestirme():
    assert sehir_dagilimi(["Sarıyer, Istanbul", "İstanbul & Ankara, Turkey", "Türkiye, Remote", ""]) == {
        "istanbul": 2,
        "ankara": 1,
        "uzaktan": 1,
    }
    zengin = zenginlestir({**ilan(), "firma": "Sezzle (Türkiye, uzaktan)", "konum": "Türkiye, Remote"})
    assert zengin["firma_gorunen"] == "Sezzle" and zengin["sehirler"] == [] and zengin["uzaktan"] is True
