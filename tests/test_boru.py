"""Uçtan uca: sahte ağ + sahte yapay zekâ ile tam bir tarama ve yayın."""

import dataclasses
import json
from datetime import UTC, datetime

from internreader import boru, depo
from internreader.ayar import ayarlari_oku
from internreader.yz.sayfa_okuyucu import Pozisyon, SayfaSonucu
from internreader.yz.siniflandirici import IlanSinifi, TopluSiniflandirma
from tests.conftest import SahteHttp, SahteYz

LEVER = [
    {
        "text": "Software Engineer (New Grad)",
        "hostedUrl": "https://jobs.lever.co/oyun/1",
        "categories": {"location": "Istanbul"},
    },
    {
        "text": "Senior Backend Engineer",
        "hostedUrl": "https://jobs.lever.co/oyun/2",
        "categories": {"location": "Istanbul"},
    },
    {
        "text": "Software Engineer",
        "hostedUrl": "https://jobs.lever.co/oyun/3",
        "categories": {"location": "Chile, Remote"},
    },
]
KARIYER_HTML = "<h2>Açık pozisyonlar</h2><a href='/i/1'>Long-Term Software Engineering Intern</a><a href='/i/2'>Satın Alma Uzmanı</a>"


def cevap(tur, mesaj):
    if tur is SayfaSonucu:
        return SayfaSonucu(
            kariyer_sayfasi_mi=True,
            genel_basvuru_var_mi=False,
            pozisyonlar=[
                Pozisyon(baslik="Long-Term Software Engineering Intern", link_no=0, seviye="uzun_donem_staj"),
                Pozisyon(baslik="Satın Alma Uzmanı", link_no=1, seviye="deneyimli"),
            ],
        )
    sonuclar = []
    for no, satir in enumerate(mesaj.splitlines()):
        ogrenci = "Intern" in satir or "New Grad" in satir
        sonuclar.append(
            IlanSinifi(
                no=no,
                seviye="staj" if ogrenci else "deneyimli",
                rol="teknik_degil" if "Satın Alma" in satir else "yazilim",
                yapay_zeka="yok",
                gerekce="t",
            )
        )
    return TopluSiniflandirma(sonuclar=sonuclar)


def test_uctan_uca_tarama_ve_yayin(oturum, tmp_path):
    with oturum.begin() as o:
        depo.firma_ekle_veya_guncelle(o, "Oyun Stüdyosu", web="https://oyun.com", ats="lever", slug="oyun")
        depo.firma_ekle_veya_guncelle(o, "Beakwise", web="https://beakwise.com", kariyer="https://beakwise.com/kariyer")
    http = SahteHttp(
        jsonlar={"api.lever.co/v0/postings/oyun": LEVER}, sayfalar={"https://beakwise.com/kariyer": KARIYER_HTML}
    )
    yz = SahteYz(cevap)

    rapor = boru.tara(ayarlari_oku(), oturum, http=http, yz=yz)
    assert rapor.toplam_ilan == 5 and rapor.yeni_ilan == 5
    assert rapor.siniflandirilan == 4  # Şili'deki uzaktan ilan konum ön seçiminde elendi → yapay zekâya gitmedi

    sonuc = boru.yayinla(oturum, cikti_dizini=tmp_path)
    assert sonuc["acik_ilan"] == 2  # New Grad + uzun dönem staj
    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "Long-Term Software Engineering Intern" in readme and "Senior" not in readme
    assert sonuc["whatsapp_dosyasi"] is not None
    site = json.loads((tmp_path / "istatistik.json").read_text(encoding="utf-8"))
    assert site["ogrenci_ilani"] == 2 and site["taranan_firma"] == 2 and site["takip_edilen_firma"] == 2
    assert site["sehirler"]["istanbul"] == 2
    assert {k["uygun"] for k in site["kararlar"]} == {True, False}  # simülasyon için hem kabul hem ret örneği

    # İkinci çalıştırma: sayfa değişmedi → yapay zekâya hiç gidilmez; yeni ilan yok → WhatsApp özeti yok
    yz2 = SahteYz(cevap)
    rapor2 = boru.tara(ayarlari_oku(), oturum, http=http, yz=yz2)
    assert rapor2.sayfa_durumlari["degismedi"] == 1 and yz2.cagrilar == []
    with oturum() as o:
        son = depo.istatistik(o)["son_tarama"]
    assert son["sayfa_durumlari"] == {"degismedi": 1} and son["yz_usd"] == 0
    assert boru.yayinla(oturum, cikti_dizini=tmp_path)["whatsapp_dosyasi"] is None


def test_panosu_kapanan_firma_yeniden_kesfe_alinir(oturum):
    with oturum.begin() as o:
        depo.firma_ekle_veya_guncelle(o, "Taşınan", web="https://tasinan.com", ats="lever", slug="eski-pano")
    rapor = boru.tara(ayarlari_oku(), oturum, http=SahteHttp(), yz=SahteYz(cevap))
    assert len(rapor.hatalar) == 1
    with oturum() as o:
        assert [f.ad for f in depo.kesif_bekleyenler(o)] == ["Taşınan"]  # ATS bilgisi silindi, keşif sırasında


def test_aylik_tavan_dolunca_yapay_zekaya_gidilmez(oturum):
    with oturum.begin() as o:
        depo.firma_ekle_veya_guncelle(o, "Beakwise", web="https://beakwise.com", kariyer="https://beakwise.com/kariyer")
        depo.kullanim_yaz(
            o,
            [
                {
                    "tarih": datetime.now(UTC),
                    "islem": "siniflandirma",
                    "model": "claude-haiku-5-5",
                    "girdi_token": 0,
                    "cikti_token": 0,
                    "maliyet_usd": 2.0,
                }
            ],
        )
    ayar = dataclasses.replace(ayarlari_oku(), aylik_yz_tavani_usd=2.0)
    rapor = boru.tara(ayar, oturum, http=SahteHttp(sayfalar={"https://beakwise.com/kariyer": KARIYER_HTML}))
    assert rapor.sayfa_durumlari["yz-kapali"] == 1 and rapor.yz_usd == 0


def test_adresi_degisen_ayni_ilan_yapay_zekaya_gitmez(oturum):
    with oturum.begin() as o:
        depo.firma_ekle_veya_guncelle(o, "Oyun Stüdyosu", web="https://oyun.com", ats="lever", slug="oyun")
    ilk = [
        {
            "text": "Software Engineer (New Grad)",
            "hostedUrl": "https://jobs.lever.co/oyun/1",
            "categories": {"location": "Istanbul"},
        }
    ]
    yeniden = [{**ilk[0], "hostedUrl": "https://jobs.lever.co/oyun/1-yeniden"}]  # aynı ilan, yeni adres
    yz1 = SahteYz(cevap)
    boru.tara(ayarlari_oku(), oturum, http=SahteHttp(jsonlar={"api.lever.co/v0/postings/oyun": ilk}), yz=yz1)
    yz2 = SahteYz(cevap)
    rapor = boru.tara(
        ayarlari_oku(), oturum, http=SahteHttp(jsonlar={"api.lever.co/v0/postings/oyun": yeniden}), yz=yz2
    )
    assert rapor.imzadan == 1 and rapor.siniflandirilan == 0 and yz2.cagrilar == []
    with oturum() as o:
        assert len(depo.yayinlanacak_ilanlar(o)) == 1  # eski ilan kapandı, yenisi eski kararla yayında
