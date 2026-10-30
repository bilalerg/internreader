"""Aynı ilan kişi başına bir kez: firma + başlık aynı, URL farklı (ör. aynı program üç şehir için üç adreste)."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from internreader import depo
from internreader.bakim import bakim_yap
from internreader.bulten import bultenleri_gonder
from internreader.bulten.gonderim import hos_geldin_gonder
from internreader.bulten.secim import bulten_sec, yakin_ilanlar
from internreader.db import Gonderim, IlanKaydi, simdi
from internreader.isleme.tekillestirme import ilan_anahtari
from tests.test_bulten import AYAR, HEPSI, SahteGonderici, abone_ekle, ilan_ekle

SABAH = datetime(2026, 11, 3, 4, 30, tzinfo=UTC)  # salı 07:30 Türkiye


def test_anahtar_turkce_kucuk_harf_noktalama_ve_bosluk_temizler():
    assert ilan_anahtari("Acme A.Ş.", "Yazılım Stajyeri") == ilan_anahtari("ACME A.S.", "YAZILIM STAJYERİ")
    assert ilan_anahtari("Acme", "Yazılım Stajyeri") == ilan_anahtari("Acme", "  yazilim   stajyeri!")
    assert ilan_anahtari("Acme", "Front-End Intern (2027)") == ilan_anahtari("acme", "Frontend Intern 2027")
    assert ilan_anahtari("Acme", "İş Analisti") == ilan_anahtari("Acme", "IS ANALISTI")
    assert ilan_anahtari("Acme", "Staj") != ilan_anahtari("Beta", "Staj")  # farklı firma, farklı ilan
    assert ilan_anahtari("Acme", "Data Intern") != ilan_anahtari("Acme", "Data Engineer Intern")


def test_ayni_eposta_icinde_bir_kez_farkli_firma_ayni_baslik_gider(oturum):
    ilan_ekle(oturum, "https://b.test/ist", "Binance Accelerator Program", "Istanbul", firma="Binance")
    ilan_ekle(oturum, "https://b.test/ank", "Binance Accelerator Program - ", "Ankara", firma="Binance")
    ilan_ekle(oturum, "https://b.test/rmt", "BINANCE ACCELERATOR PROGRAM", "Remote", firma="Binance")
    ilan_ekle(oturum, "https://a.test/1", "Software Engineering Intern", "Istanbul", firma="Acme")
    ilan_ekle(oturum, "https://z.test/1", "Software Engineering Intern", "Istanbul", firma="Zeta")
    abone_ekle(oturum, "a@x.com", HEPSI)
    g = SahteGonderici()
    assert bultenleri_gonder(oturum, g, AYAR, SABAH)["ilan"] == 3
    metin = g.gidenler[0].metin.lower()
    assert metin.count("binance accelerator program") == 1
    assert "acme — software engineering intern" in metin and "zeta — software engineering intern" in metin


def test_kopya_firma_kotasini_harcamaz(oturum):
    ilan_ekle(oturum, "https://b.test/1", "Backend Intern", "Istanbul", firma="Beta")
    ilan_ekle(oturum, "https://b.test/2", "Backend Intern", "Ankara", firma="Beta")
    ilan_ekle(oturum, "https://b.test/3", "Frontend Intern", "Istanbul", firma="Beta")
    abone_ekle(oturum, "a@x.com", HEPSI)
    g = SahteGonderici()
    bultenleri_gonder(oturum, g, AYAR, SABAH)
    assert "Backend Intern" in g.gidenler[0].metin and "Frontend Intern" in g.gidenler[0].metin


def test_sonraki_bultende_yeni_adresli_kopya_gitmez(oturum):
    ilan_ekle(oturum, "https://b.test/eski", "Accelerator Program", "Istanbul", firma="Binance")
    abone_ekle(oturum, "a@x.com", HEPSI)
    assert bultenleri_gonder(oturum, SahteGonderici(), AYAR, SABAH)["gonderilen"] == 1
    # Ertesi gün aynı ilan başka adresle (Workday yeniden yayınlamış), yanında gerçekten yeni bir ilan
    ilan_ekle(oturum, "https://b.test/yeni-adres", "Accelerator  Program", "Istanbul", firma="Binance")
    ilan_ekle(oturum, "https://c.test/1", "Data Intern", "Istanbul", firma="Gama", rol="veri")
    g = SahteGonderici()
    assert bultenleri_gonder(oturum, g, AYAR, SABAH + timedelta(days=1))["ilan"] == 1
    assert "Data Intern" in g.gidenler[0].metin and "Accelerator" not in g.gidenler[0].metin
    # Yalnızca kopya kaldıysa e-posta hiç gitmez
    ilan_ekle(oturum, "https://b.test/ucuncu", "ACCELERATOR PROGRAM", "Ankara", firma="Binance")
    assert bultenleri_gonder(oturum, SahteGonderici(), AYAR, SABAH + timedelta(days=2))["gonderilen"] == 0


def test_sehre_gore_uyan_kopya_gider(oturum):
    # İstanbul kopyası Ankaralıya uymaz; Ankara kopyası gider, iki kopya birden gitmez
    ilan_ekle(oturum, "https://b.test/ist", "Accelerator Program", "Istanbul", firma="Binance")
    ilan_ekle(oturum, "https://b.test/ank", "Accelerator Program", "Ankara", firma="Binance")
    abone_ekle(oturum, "ank@x.com", {**HEPSI, "sehirler": ["ankara"]})
    g = SahteGonderici()
    assert bultenleri_gonder(oturum, g, AYAR, SABAH)["ilan"] == 1
    assert "https://b.test/ank" in g.gidenler[0].metin


def test_hos_geldinde_bir_kez_ve_sonraki_bultende_tekrar_yok(oturum):
    ilan_ekle(oturum, "https://b.test/ist", "Accelerator Program", "Istanbul", firma="Binance")
    ilan_ekle(oturum, "https://b.test/ank", "Accelerator Program", "Ankara", firma="Binance")
    abone_id = abone_ekle(oturum, "a@x.com", HEPSI)
    g = SahteGonderici()
    assert hos_geldin_gonder(oturum, g, AYAR, abone_id, SABAH - timedelta(days=1)) == "gonderildi"
    assert g.gidenler[0].metin.count("Accelerator Program") == 1
    # Üçüncü adres ertesi sabah: aynı ilan, gitmez
    ilan_ekle(oturum, "https://b.test/rmt", "Accelerator Program", "Remote", firma="Binance")
    assert bultenleri_gonder(oturum, SahteGonderici(), AYAR, SABAH)["gonderilen"] == 0


def test_yakin_ilanlar_tekrari_atlar_ve_gonderilenleri_onermez():
    ilan = {"rol": "yazilim", "seviye": "staj", "sehirler": ["ankara"], "calisma_modeli": "hibrit"}
    ilanlar = [
        {**ilan, "kimlik": "a1", "firma": "A", "baslik": "Staj"},
        {**ilan, "kimlik": "a2", "firma": "A", "baslik": "STAJ"},
        {**ilan, "kimlik": "b1", "firma": "B", "baslik": "Staj"},
    ]
    tercih = {"alanlar": ["yazilim"], "sehirler": ["izmir"]}
    assert [i["kimlik"] for i in yakin_ilanlar(ilanlar, tercih)] == ["a1", "b1"]
    gonderilmis = {"a1", ilan_anahtari("A", "Staj")}
    assert [i["kimlik"] for i in yakin_ilanlar(ilanlar, tercih, gonderilmis=gonderilmis)] == ["b1"]
    assert [i["kimlik"] for i in bulten_sec(ilanlar, {}, gonderilmis, 15)] == ["b1"]


def test_bakim_acik_ilanin_eski_gonderim_kaydini_silmez(oturum):
    acik = ilan_ekle(oturum, "https://a.test/acik", "Sürekli Açık Staj", "Istanbul", firma="Acme")
    kapali = ilan_ekle(oturum, "https://b.test/kapali", "Kapanan Staj", "Istanbul", firma="Beta")
    kopyasi_acik = ilan_ekle(oturum, "https://c.test/eski", "Program", "Istanbul", firma="Gama")
    ilan_ekle(oturum, "https://c.test/yeni", "Program", "Ankara", firma="Gama")  # aynı ilan, hâlâ açık
    abone_id = abone_ekle(oturum, "a@x.com", HEPSI)
    with oturum.begin() as o:
        o.execute(update(IlanKaydi).where(IlanKaydi.kimlik.in_([kapali, kopyasi_acik])).values(aktif=False))
        depo.gonderim_kaydet(
            o, depo.abone_id_ile(o, abone_id), [acik, kapali, kopyasi_acik], simdi() - timedelta(days=200), False
        )
    assert bakim_yap(oturum)["eski_gonderim"] == 1
    with oturum() as o:
        assert set(o.scalars(select(Gonderim.ilan_kimlik))) == {acik, kopyasi_acik}
    # 200 gündür açık ilan ve kopyası aynı aboneye yeniden gitmez
    assert bultenleri_gonder(oturum, SahteGonderici(), AYAR)["gonderilen"] == 0
