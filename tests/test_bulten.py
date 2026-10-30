"""Bülten: seçim kuralı, kime ne gider, tekrar gönderilmeme, haftalık zamanlama, hata yalıtımı, e-posta biçimi."""

import dataclasses
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from internreader import depo
from internreader.abonelik import iptal_jetonu, kayit_iste, onayla
from internreader.api import uygulama_olustur
from internreader.ayar import GELISTIRME_ANAHTARI, ayarlari_oku
from internreader.bakim import bakim_yap
from internreader.bulten import bultenleri_gonder, eslesir
from internreader.db import Abone, simdi
from internreader.eposta import Eposta, SmtpGonderici
from internreader.model import Ilan
from internreader.yayin import TURKIYE_SAATI

AYAR = dataclasses.replace(ayarlari_oku(), site_adresi="https://internreader.test", gizli_anahtar="test-anahtari")
HEPSI = {"alanlar": ["yazilim", "yapay_zeka", "veri"], "seviyeler": ["staj", "uzun_donem_staj", "yeni_mezun", "junior"]}


class SahteGonderici:
    def __init__(self, hatali: set[str] | None = None):
        self.gidenler: list[Eposta] = []
        self.hatali = hatali or set()

    def gonder(self, eposta: Eposta) -> None:
        if eposta.alici in self.hatali:
            raise OSError("550 alıcı reddedildi")
        self.gidenler.append(eposta)


def ilan_ekle(oturum, url, baslik, konum, seviye="staj", rol="yazilim", firma="F"):
    i = Ilan(firma=firma, baslik=baslik, url=url, kaynak="lever", konum=konum)
    with oturum.begin() as o:
        depo.ilanlari_kaydet(o, [i], set())
        depo.siniflandirma_kaydet(
            o, {i.kimlik: {"seviye": seviye, "rol": rol, "yapay_zeka": "yok"}}, "claude-haiku-5-5"
        )
    return i.kimlik


def abone_ekle(oturum, eposta, tercihler, siklik="gunluk", onayli=True):
    with oturum.begin() as o:
        jeton = kayit_iste(o, eposta, tercihler, siklik, "site")
        if onayli:
            onayla(o, jeton)
        return depo.abone_eposta_ile(o, eposta).id


def test_secim_kurali_sitedeki_onizlemeyle_ayni():
    ilan = {"rol": "yazilim", "seviye": "staj", "sehirler": ["istanbul"], "uzaktan": False}
    assert eslesir(ilan, {**HEPSI, "sehirler": []})  # şehir seçilmemiş = fark etmez
    assert eslesir(ilan, {**HEPSI, "sehirler": ["istanbul"]})
    assert not eslesir(ilan, {**HEPSI, "sehirler": ["ankara"]})
    assert eslesir({**ilan, "sehirler": []}, {**HEPSI, "sehirler": ["ankara"]})  # konum belirtilmemiş: dahil
    assert eslesir({**ilan, "sehirler": [], "uzaktan": True}, {**HEPSI, "sehirler": ["uzaktan"]})
    assert eslesir({**ilan, "sehirler": [], "uzaktan": True}, {**HEPSI, "sehirler": ["ankara"]})  # uzaktan: her şehir
    assert not eslesir(ilan, {**HEPSI, "alanlar": ["veri"]})
    assert not eslesir({**ilan, "seviye": "yari_zamanli"}, HEPSI)


def test_yalnizca_onayli_abonelere_uyan_yeni_ilanlar_bir_kez_gider(oturum):
    ilan_ekle(oturum, "https://u/1", "Software Engineering Intern", "Istanbul")
    ilan_ekle(oturum, "https://u/2", "Data Intern", "Ankara", rol="veri")
    abone_ekle(oturum, "ist@x.com", {**HEPSI, "sehirler": ["istanbul"]})
    abone_ekle(oturum, "hepsi@x.com", HEPSI)
    abone_ekle(oturum, "onaysiz@x.com", HEPSI, onayli=False)

    g = SahteGonderici()
    rapor = bultenleri_gonder(oturum, g, AYAR)
    alicilar = {e.alici: e for e in g.gidenler}
    assert set(alicilar) == {"ist@x.com", "hepsi@x.com"} and rapor["gonderilen"] == 2
    assert "Software Engineering Intern" in alicilar["ist@x.com"].metin
    assert "Data Intern" not in alicilar["ist@x.com"].metin and "Data Intern" in alicilar["hepsi@x.com"].metin

    # Ertesi gün yeni ilan yok → kimseye e-posta gitmez
    g2 = SahteGonderici()
    yarin = simdi() + timedelta(days=1)
    assert bultenleri_gonder(oturum, g2, AYAR, yarin)["gonderilen"] == 0 and g2.gidenler == []

    # Yeni ilan → yalnızca yeni ilan gider
    ilan_ekle(oturum, "https://u/3", "Junior Backend Developer", "Istanbul", seviye="junior")
    g3 = SahteGonderici()
    bultenleri_gonder(oturum, g3, AYAR, yarin)
    metin = next(e.metin for e in g3.gidenler if e.alici == "ist@x.com")
    assert "Junior Backend Developer" in metin and "Software Engineering Intern" not in metin


def test_haftalik_abone_pazartesi_sabahi_alir(oturum):
    ilan_ekle(oturum, "https://u/1", "Software Engineering Intern", "Istanbul")
    abone_ekle(oturum, "hafta@x.com", HEPSI, siklik="haftalik")
    bugun = simdi().astimezone(TURKIYE_SAATI)
    # Önümüzdeki pazartesi 07:00 (Türkiye) = 04:00 UTC: sabah işinin saati
    pazartesi = (bugun + timedelta(days=(7 - bugun.weekday()) % 7)).replace(hour=7, minute=0, second=0, microsecond=0)
    assert bultenleri_gonder(oturum, SahteGonderici(), AYAR, pazartesi - timedelta(days=5))["hazir_abone"] == 0
    assert bultenleri_gonder(oturum, SahteGonderici(), AYAR, pazartesi)["gonderilen"] == 1
    ilan_ekle(oturum, "https://u/2", "AI Intern", "Istanbul", rol="yapay_zeka")
    # Aynı pazartesi elle ikinci çalıştırma ve salı: haftalık aboneye yeni e-posta yok
    assert bultenleri_gonder(oturum, SahteGonderici(), AYAR, pazartesi + timedelta(hours=8))["hazir_abone"] == 0
    assert bultenleri_gonder(oturum, SahteGonderici(), AYAR, pazartesi + timedelta(days=1))["hazir_abone"] == 0
    g = SahteGonderici()
    assert bultenleri_gonder(oturum, g, AYAR, pazartesi + timedelta(days=7))["gonderilen"] == 1
    assert "AI Intern" in g.gidenler[0].metin and "Software Engineering Intern" not in g.gidenler[0].metin


def test_haftalik_gun_turkiye_saatine_gore(oturum):
    abone_ekle(oturum, "hafta@x.com", HEPSI, siklik="haftalik")
    with oturum() as o:
        # Pazar 22:00 UTC = pazartesi 01:00 Türkiye → hazır; pazartesi 21:30 UTC = salı 00:30 Türkiye → değil
        assert len(depo.gonderime_hazir_aboneler(o, datetime(2026, 11, 1, 22, 0, tzinfo=UTC))) == 1
        assert depo.gonderime_hazir_aboneler(o, datetime(2026, 11, 2, 21, 30, tzinfo=UTC)) == []


def test_ayni_gun_ikinci_calismada_ikinci_bulten_gitmez(oturum):
    # Vercel tetiklemesi + GitHub yedek zamanlaması aynı gün iki kez çalışabilir
    ilan_ekle(oturum, "https://u/1", "Software Engineering Intern", "Istanbul")
    abone_ekle(oturum, "gun@x.com", HEPSI)
    sabah = datetime(2026, 11, 3, 4, 30, tzinfo=UTC)  # salı 07:30 Türkiye
    assert bultenleri_gonder(oturum, SahteGonderici(), AYAR, sabah)["gonderilen"] == 1
    ilan_ekle(oturum, "https://u/2", "AI Intern", "Istanbul", rol="yapay_zeka")
    # Aynı gün öğlen: yeni ilan olsa da e-posta yok; ertesi sabah gider
    assert bultenleri_gonder(oturum, SahteGonderici(), AYAR, sabah + timedelta(hours=6))["hazir_abone"] == 0
    g = SahteGonderici()
    assert bultenleri_gonder(oturum, g, AYAR, sabah + timedelta(days=1))["gonderilen"] == 1
    assert "AI Intern" in g.gidenler[0].metin
    # Türkiye günü sınırı: 22:00 UTC, Türkiye'de ertesi gün 01:00'dir
    gece = datetime(2026, 11, 4, 22, 0, tzinfo=UTC)
    with oturum() as o:
        assert len(depo.gonderime_hazir_aboneler(o, gece)) == 1


def test_gunluk_sinira_takilan_abone_ayni_gun_ikinci_calismada_alir(oturum):
    ilan_ekle(oturum, "https://u/1", "Software Engineering Intern", "Istanbul")
    for e in ("a@x.com", "b@x.com"):
        abone_ekle(oturum, e, HEPSI)
    sinirli = dataclasses.replace(AYAR, gunluk_bulten_siniri=1)
    sabah = datetime(2026, 11, 3, 4, 30, tzinfo=UTC)
    bir, iki = SahteGonderici(), SahteGonderici()
    assert bultenleri_gonder(oturum, bir, sinirli, sabah)["ertelendi"] == 1
    bultenleri_gonder(oturum, iki, sinirli, sabah + timedelta(hours=2))
    assert {e.alici for e in bir.gidenler} | {e.alici for e in iki.gidenler} == {"a@x.com", "b@x.com"}


def test_bir_abonenin_hatasi_digerlerini_durdurmaz_ve_gonderilmis_sayilmaz(oturum):
    ilan_ekle(oturum, "https://u/1", "Software Engineering Intern", "Istanbul")
    abone_ekle(oturum, "bozuk@x.com", HEPSI)
    abone_ekle(oturum, "saglam@x.com", HEPSI)
    rapor = bultenleri_gonder(oturum, SahteGonderici(hatali={"bozuk@x.com"}), AYAR)
    assert rapor["gonderilen"] == 1 and rapor["hata"] == 1
    g = SahteGonderici()
    bultenleri_gonder(oturum, g, AYAR)  # ertesi gün: hatalı aboneye ilan yeniden denenir
    assert [e.alici for e in g.gidenler] == ["bozuk@x.com"]


def test_eposta_bicimi_kacis_ve_tek_tikla_cikis_basligi(oturum):
    ilan_ekle(oturum, "https://u/1", "Intern <script>alert(1)</script>", "Istanbul")
    abone_id = abone_ekle(oturum, "a@x.com", HEPSI)
    g = SahteGonderici()
    bultenleri_gonder(oturum, g, AYAR)
    e = g.gidenler[0]
    assert "<script>" not in e.html and "&lt;script&gt;" in e.html
    jeton = iptal_jetonu(abone_id, "test-anahtari")
    assert e.basliklar["List-Unsubscribe"] == f"<https://internreader.test/api/abone/iptal-tek?jeton={jeton}>"
    assert e.basliklar["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert f"https://internreader.test/iptal?jeton={jeton}" in e.metin


def test_tek_tikla_cikis_ucu(oturum):
    abone_id = abone_ekle(oturum, "a@x.com", HEPSI)
    istemci = TestClient(uygulama_olustur(AYAR, oturum, SahteGonderici()))
    jeton = iptal_jetonu(abone_id, "test-anahtari")
    cevap = istemci.post(f"/api/abone/iptal-tek?jeton={jeton}", data={"List-Unsubscribe": "One-Click"})
    assert cevap.status_code == 200
    with oturum() as o:
        assert depo.abone_eposta_ile(o, "a@x.com") is None


def test_smtp_iletisi_metin_html_ve_basliklar_icerir():
    g = SmtpGonderici("smtp.test", 587, "", "", "InternReader <bulten@internreader.test>")
    ileti = g.ileti(Eposta("a@x.com", "Konu", "düz metin", "<p>html</p>", {"List-Unsubscribe": "<https://x/y>"}))
    assert ileti["List-Unsubscribe"] == "<https://x/y>" and ileti["From"].startswith("InternReader")
    assert {p.get_content_type() for p in ileti.iter_parts()} == {"text/plain", "text/html"}


def test_bakim_onaylanmayan_ve_eski_kayitlari_temizler(oturum):
    abone_ekle(oturum, "onaysiz@x.com", HEPSI, onayli=False)
    with oturum.begin() as o:
        a = o.query(Abone).one()
        a.onay_jetonu_tarihi = simdi() - timedelta(hours=80)
    assert bakim_yap(oturum)["onaylanmayan_abonelik"] == 1


def test_gercek_smtp_gelistirme_anahtariyla_gonderilmez(oturum):
    ayar = dataclasses.replace(ayarlari_oku(), smtp_sunucu="smtp.ornek.com", gizli_anahtar=GELISTIRME_ANAHTARI)
    with pytest.raises(RuntimeError, match="GIZLI_ANAHTAR"):
        bultenleri_gonder(oturum, SahteGonderici(), ayar)


def test_gunluk_bulten_siniri_ve_adil_sira(oturum):

    ilan_ekle(oturum, "https://f.com/1", "Yazılım Stajyeri", "İstanbul")
    for e in ("a@x.com", "b@x.com", "c@x.com"):
        abone_ekle(oturum, e, HEPSI)
    sinirli = dataclasses.replace(AYAR, gunluk_bulten_siniri=2)
    g = SahteGonderici()
    rapor = bultenleri_gonder(oturum, g, sinirli)
    assert rapor["gonderilen"] == 2 and rapor["ertelendi"] == 1
    ilk_gun = {e.alici for e in g.gidenler}
    # Ertesi gün: dünkü sınır yüzünden alamayan abone ilk sırada (aynı kişi her gün dışarıda kalmaz)
    ilan_ekle(oturum, "https://f.com/2", "Backend Stajyeri", "İstanbul")
    g2 = SahteGonderici()
    bultenleri_gonder(oturum, g2, sinirli)
    kalan = {"a@x.com", "b@x.com", "c@x.com"} - ilk_gun
    assert g2.gidenler[0].alici in kalan


def test_art_arda_hatada_gonderim_durur(oturum):
    ilan_ekle(oturum, "https://f.com/1", "Yazılım Stajyeri", "İstanbul")
    adresler = [f"k{i}@x.com" for i in range(8)]
    for e in adresler:
        abone_ekle(oturum, e, HEPSI)
    rapor = bultenleri_gonder(oturum, SahteGonderici(hatali=set(adresler)), AYAR)
    assert rapor["hata"] == 5 and rapor["ertelendi"] == 3  # kota dolmuşsa 8'ini de boşuna denemez
