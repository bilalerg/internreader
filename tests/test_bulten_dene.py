"""Hızlı test komutu: tek adrese, kayıt yazmadan, korumalara takılmadan; adres kayıtlara düşmez."""

import dataclasses
import logging
from datetime import timedelta
from pathlib import Path

import pytest

from internreader import __main__ as komut
from internreader import depo
from internreader.abonelik import iptal_et, iptal_jetonu, kayit_iste, onayla
from internreader.ayar import ayarlari_oku
from internreader.bulten import bultenleri_gonder
from internreader.bulten.gonderim import deneme_gonder
from internreader.db import Bulten, Gonderim, oturum_fabrikasi, simdi
from internreader.model import Ilan

AYAR = dataclasses.replace(ayarlari_oku(), site_adresi="https://internreader.test", gizli_anahtar="test-anahtari")
ADRES = "ben.test.adresi@ornek.com"
KOK = Path(__file__).resolve().parents[1]


class SahteGonderici:
    def __init__(self):
        self.gidenler = []

    def gonder(self, eposta):
        self.gidenler.append(eposta)


def ilan_ekle(oturum, url, baslik, firma="Acme", rol="yazilim", yayin=""):
    i = Ilan(firma=firma, baslik=baslik, url=url, kaynak="lever", konum="Istanbul", tarih=yayin)
    with oturum.begin() as o:
        depo.ilanlari_kaydet(o, [i], set())
        depo.siniflandirma_kaydet(o, {i.kimlik: {"seviye": "staj", "rol": rol, "yapay_zeka": "yok"}}, "test")


def kayit_sayilari(oturum):
    with oturum() as o:
        return o.query(Gonderim).count(), o.query(Bulten).count()


def test_tek_adrese_test_konusuyla_gider_ve_hic_kayit_yazmaz(oturum, tmp_path):
    ilan_ekle(oturum, "https://j.test/1", "Yazılım Stajı")
    g = SahteGonderici()
    rapor = deneme_gonder(oturum, g, AYAR, ADRES, klasor=tmp_path)
    (e,) = g.gidenler
    assert e.alici == ADRES and e.konu == "[TEST] Bugün sana uygun 1 yeni staj ilanı" and "Yazılım Stajı" in e.metin
    assert rapor["gonderildi"] and rapor["tur"] == "bulten" and rapor["ilan"] == 1 and not rapor["kayitli_abone"]
    assert kayit_sayilari(oturum) == (0, 0)
    assert "Yazılım Stajı" in (tmp_path / "test_bulten.html").read_text(encoding="utf-8")  # önizleme
    # Tekrar edilebilir: aynı ilan yine gelir
    deneme_gonder(oturum, g, AYAR, ADRES, klasor=tmp_path)
    assert len(g.gidenler) == 2


def test_korumalara_takilmaz_ve_abonenin_durumunu_degistirmez(oturum, tmp_path):
    ilan_ekle(oturum, "https://j.test/1", "Yazılım Stajı")
    with oturum.begin() as o:
        onayla(o, kayit_iste(o, ADRES, {}, "gunluk", "test"))
    assert bultenleri_gonder(oturum, SahteGonderici(), AYAR)["gonderilen"] == 1  # bugünkü bülten gitti
    with oturum() as o:
        son = depo.abone_eposta_ile(o, ADRES).son_bulten
    sayilar = kayit_sayilari(oturum)
    g = SahteGonderici()
    rapor = deneme_gonder(oturum, g, dataclasses.replace(AYAR, gunluk_bulten_siniri=1), ADRES, klasor=tmp_path)
    assert rapor["gonderildi"] and rapor["kayitli_abone"] and "Yazılım Stajı" in g.gidenler[0].metin
    with oturum() as o:
        assert depo.abone_eposta_ile(o, ADRES).son_bulten == son
    assert kayit_sayilari(oturum) == sayilar
    # Sabah bülteni koruması da bozulmadı
    assert bultenleri_gonder(oturum, SahteGonderici(), AYAR)["hazir_abone"] == 0


def test_kayitli_aboneye_kendi_tercihleri_degilse_tum_ilanlar(oturum, tmp_path):
    ilan_ekle(oturum, "https://j.test/1", "Yazılım Stajı")
    ilan_ekle(oturum, "https://j.test/2", "Veri Stajı", firma="Beta", rol="veri")
    with oturum.begin() as o:
        onayla(o, kayit_iste(o, ADRES, {"alanlar": ["veri"]}, "haftalik", "test"))
    g = SahteGonderici()
    deneme_gonder(oturum, g, AYAR, ADRES.upper(), klasor=tmp_path)  # büyük harfle de abone bulunur
    assert "Veri Stajı" in g.gidenler[0].metin and "Yazılım Stajı" not in g.gidenler[0].metin
    assert "Bu hafta" in g.gidenler[0].konu
    h = SahteGonderici()
    deneme_gonder(oturum, h, AYAR, "baska@ornek.com", klasor=tmp_path)
    assert "Veri Stajı" in h.gidenler[0].metin and "Yazılım Stajı" in h.gidenler[0].metin


def test_hos_geldin_eski_ilanlari_da_alir_gunluk_almaz(oturum, tmp_path):
    eski = (simdi() - timedelta(days=100)).date().isoformat()
    ilan_ekle(oturum, "https://j.test/1", "Eski Staj", yayin=eski)
    g = SahteGonderici()
    rapor = deneme_gonder(oturum, g, AYAR, ADRES, klasor=tmp_path)
    assert rapor["sonuc"] == "uyan_ilan_yok" and not rapor["gonderildi"] and g.gidenler == []
    rapor = deneme_gonder(oturum, g, AYAR, ADRES, hos_geldin=True, klasor=tmp_path)
    assert rapor["tur"] == "hos_geldin" and rapor["gonderildi"]
    assert g.gidenler[0].konu == "[TEST] Şu an sana uygun 1 ilan" and "Eski Staj" in g.gidenler[0].metin
    assert kayit_sayilari(oturum) == (0, 0)


def test_gonderme_secenegi_yalnizca_onizleme_yazar(oturum, tmp_path):
    ilan_ekle(oturum, "https://j.test/1", "Yazılım Stajı")
    g = SahteGonderici()
    rapor = deneme_gonder(oturum, g, AYAR, ADRES, gonder=False, klasor=tmp_path)
    assert g.gidenler == [] and not rapor["gonderildi"] and (tmp_path / "test_bulten.html").exists()


def test_cikis_baglantisi_gercek_aboneligi_silmez(oturum, tmp_path):
    ilan_ekle(oturum, "https://j.test/1", "Yazılım Stajı")
    with oturum.begin() as o:
        onayla(o, kayit_iste(o, ADRES, {}, "gunluk", "test"))
    g = SahteGonderici()
    deneme_gonder(oturum, g, AYAR, ADRES, klasor=tmp_path)
    jeton = iptal_jetonu(0, AYAR.gizli_anahtar)
    assert jeton in g.gidenler[0].metin
    with oturum.begin() as o:
        assert iptal_et(o, jeton, AYAR.gizli_anahtar)  # bağlantı çalışır, kimseyi silmez
    with oturum() as o:
        assert depo.abone_eposta_ile(o, ADRES) is not None


def _komut_ortami(monkeypatch, tmp_path, gonderici):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'k.db').as_posix()}")
    monkeypatch.setattr(komut, "gonderici_olustur", lambda _: gonderici)
    monkeypatch.setattr(komut, "CIKTI", tmp_path / "cikti")


def test_komut_adresi_cikti_ve_kayitlara_yazmaz(monkeypatch, tmp_path, capsys, caplog):
    g = SahteGonderici()
    _komut_ortami(monkeypatch, tmp_path, g)
    fabrika = oturum_fabrikasi(f"sqlite:///{(tmp_path / 'k.db').as_posix()}")
    ilan_ekle(fabrika, "https://j.test/1", "Yazılım Stajı")
    with caplog.at_level(logging.DEBUG):
        assert komut.main(["bulten-dene", ADRES, "--hos-geldin"]) == 0
    cikti = capsys.readouterr()
    assert '"gonderildi": true' in cikti.out and len(g.gidenler) == 1
    assert ADRES not in cikti.out + cikti.err + caplog.text
    assert (tmp_path / "cikti" / "test_bulten.html").exists()
    fabrika.kw["bind"].dispose()


def test_komut_gonderim_hatasinda_adresi_sizdirmaz(monkeypatch, tmp_path, capsys, caplog):
    class Bozuk:
        def gonder(self, _):
            raise OSError(f"550 alıcı reddedildi: {ADRES}")

    _komut_ortami(monkeypatch, tmp_path, Bozuk())
    fabrika = oturum_fabrikasi(f"sqlite:///{(tmp_path / 'k.db').as_posix()}")
    ilan_ekle(fabrika, "https://j.test/1", "Yazılım Stajı")
    with caplog.at_level(logging.DEBUG):
        assert komut.main(["bulten-dene", ADRES]) == 1
    cikti = capsys.readouterr()
    assert ADRES not in cikti.out + cikti.err + caplog.text and "OSError" in cikti.err
    fabrika.kw["bind"].dispose()


def test_is_akisi_yalnizca_elle_ve_adres_gizli_degerden():
    metin = (KOK / ".github/workflows/test_bulten.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch" in metin and "schedule" not in metin
    assert "${{ secrets.TEST_EPOSTA }}" in metin and "::add-mask::" in metin
    assert "inputs.eposta" not in metin and "set -x" not in metin
    assert "gunluk" in metin and "hos-geldin" in metin


@pytest.mark.parametrize("ad", ["ilk", "ikinci"])
def test_bulten_kayit_sayisi_sabit(oturum, tmp_path, ad):
    ilan_ekle(oturum, f"https://j.test/{ad}", "Yazılım Stajı")
    deneme_gonder(oturum, SahteGonderici(), AYAR, ADRES, klasor=tmp_path)
    assert kayit_sayilari(oturum) == (0, 0)
