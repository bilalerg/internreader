"""Jooble kaynağı: ayrıştırma, ön eleme, haftada bir çalışma, kopya eleme, anahtarın kayda düşmemesi, ilan ömrü."""

import dataclasses
import logging
from datetime import date, timedelta

import requests
from sqlalchemy import select, update

from internreader import boru, depo
from internreader.ayar import ayarlari_oku
from internreader.bakim import bakim_yap
from internreader.db import IlanKaydi, simdi
from internreader.isleme.filtre import konum_uygun
from internreader.isleme.guncellik import guncellik
from internreader.kaynaklar.jooble import SORGULAR, jooble_ayristir, jooble_tara, on_elemeden_gecer_mi
from internreader.model import Ilan
from internreader.yz.siniflandirici import IlanSinifi, TopluSiniflandirma
from tests.conftest import SahteHttp, SahteYz

ANAHTAR = "gizli-anahtar"
BUGUN = date(2026, 11, 1)


def _is(no=1, baslik="Yazılım Stajyeri", firma="Küçük Firma", **ek):
    return {
        "id": str(no),
        "title": baslik,
        "company": firma,
        "link": f"https://tr.jooble.org/desc/{no}?ckey=a&pos={no}",
        "location": "Manisa",
        "source": "secretcv.com",
        "type": "Staj",
        "updated": "2026-10-30T19:36:42.0270000",
        "snippet": "<b>Python</b> bilen öğrenci",
        **ek,
    }


def _ayar():
    return dataclasses.replace(ayarlari_oku(), jooble_anahtari=ANAHTAR)


def _yz():
    def cevap(tur, mesaj):
        assert tur is TopluSiniflandirma
        return TopluSiniflandirma(
            sonuclar=[IlanSinifi(no=0, seviye="staj", rol="yazilim", yapay_zeka="yok", gerekce="staj")]
        )

    return SahteYz(cevap)


def test_ayristirma_firmasiz_ve_yasak_kaynakli_sonucu_atar_metni_temizler():
    ilanlar = jooble_ayristir(
        {
            "jobs": [
                _is(1),
                _is(2, firma=""),
                _is(3, source="kariyer.net"),
                _is(4, source="tr.linkedin.com"),
                _is(5, source="youthall.com"),
            ]
        }
    )
    assert [i.url for i in ilanlar] == ["https://tr.jooble.org/desc/1?ckey=a&pos=1"]
    assert ilanlar[0].kaynak == "jooble" and ilanlar[0].tarih == "2026-10-30"
    assert ilanlar[0].aciklama == "Python bilen öğrenci"


def test_kimlik_arama_adresi_degisse_de_ayni_kalir():
    once = jooble_ayristir({"jobs": [_is(7)]})[0]
    sonra = jooble_ayristir({"jobs": [_is(7, link="https://tr.jooble.org/desc/7?ckey=b&pos=33")]})[0]
    assert once.url != sonra.url and once.kimlik == sonra.kimlik


def test_on_eleme_ogrenci_ve_teknik_ister():
    def ilan(baslik, aciklama="", tip=""):
        return Ilan(firma="F", baslik=baslik, url="u", kaynak="jooble", aciklama=aciklama, calisma_tipi=tip)

    assert on_elemeden_gecer_mi(ilan("Software Intern"))
    assert on_elemeden_gecer_mi(ilan("Stajyer", aciklama="yazılım ekibinde çalışacak"))
    assert on_elemeden_gecer_mi(ilan("Backend Developer", tip="Yarı zamanlı"))
    assert not on_elemeden_gecer_mi(ilan("Muhasebe Stajyeri", aciklama="ofis işleri"))
    assert not on_elemeden_gecer_mi(ilan("Senior Software Engineer"))


def test_tarama_sorguyu_tarihle_gonderir_ayni_ilani_bir_kez_alir():
    http = SahteHttp(jsonlar={"tr.jooble.org": {"jobs": [_is(1), _is(2, firma="KÜÇÜK FİRMA")]}})
    ilanlar = jooble_tara(http, ANAHTAR, BUGUN, sorgular=("a", "b"))
    assert len(ilanlar) == 1 and len(http.istekler) == 2
    adres, govde, _ = http.istekler[0]
    assert adres == f"https://tr.jooble.org/api/{ANAHTAR}"
    assert govde["ResultOnPage"] == "100" and govde["location"] == "Türkiye"
    assert govde["datecreatedfrom"] == (BUGUN - timedelta(days=60)).isoformat()


def test_ilk_hatada_durur_anahtar_kayda_ve_rapora_dusmez(oturum, caplog):
    http = SahteHttp()  # hazır cevap yok: 404, hata metninde anahtarlı adres var
    with caplog.at_level(logging.WARNING):
        rapor = boru.tara(_ayar(), oturum, http=http, yz=_yz())
    assert len(http.istekler) == 1
    assert rapor.hatalar == ["jooble: HTTPError 404"]
    assert ANAHTAR not in caplog.text and ANAHTAR not in str(rapor.hatalar)


def test_hata_sonrasi_ertesi_gun_yeniden_dener_basari_sonrasi_haftada_bir(oturum):
    boru.tara(_ayar(), oturum, http=SahteHttp(), yz=_yz())

    http = SahteHttp(jsonlar={"tr.jooble.org": {"jobs": [_is(1)]}})
    rapor = boru.tara(_ayar(), oturum, http=http, yz=_yz())
    assert rapor.jooble_ilan == 1 and len(http.istekler) == len(SORGULAR)

    http = SahteHttp(jsonlar={"tr.jooble.org": {"jobs": [_is(1)]}})
    assert boru.tara(_ayar(), oturum, http=http, yz=_yz()).jooble_ilan == 0
    assert not http.istekler


def test_anahtar_yoksa_istek_gitmez_ara_taramada_da_gitmez(oturum):
    http = SahteHttp()
    boru.tara(ayarlari_oku(), oturum, http=http, yz=_yz())
    boru.tara(_ayar(), oturum, http=http, yz=_yz(), yalnizca_ats=True)
    assert not http.istekler


def test_firmanin_kendi_kaynagindan_okunan_ilan_jooble_dan_tekrar_gelmez(oturum):
    with oturum.begin() as o:
        depo.firma_ekle_veya_guncelle(o, "Vertigo Games", ats="lever", slug="vertigo")
    lever = [
        {
            "text": "Game Developer - Intern",
            "hostedUrl": "https://jobs.lever.co/vertigo/1",
            "categories": {"location": "Istanbul"},
        }
    ]
    http = SahteHttp(
        jsonlar={
            "lever.co": lever,
            "tr.jooble.org": {
                "jobs": [
                    _is(1, baslik="Game Developer - Intern", firma="Vertigo"),
                    _is(2, baslik="Game Developer - Intern", firma="Başka Firma"),
                ]
            },
        }
    )
    rapor = boru.tara(_ayar(), oturum, http=http, yz=_yz())
    assert rapor.jooble_ilan == 1
    with oturum() as o:
        firmalar = set(o.scalars(select(IlanKaydi.firma).where(IlanKaydi.kaynak == "jooble")))
    assert firmalar == {"Başka Firma"}


def test_ayni_adli_firmanin_taramasi_jooble_ilanini_kapatmaz_bakim_kapatir(oturum):
    with oturum.begin() as o:
        depo.firma_ekle_veya_guncelle(o, "Baykar", ats="lever", slug="baykar")
    http = SahteHttp(jsonlar={"lever.co": [], "tr.jooble.org": {"jobs": [_is(1, firma="Baykar")]}})
    boru.tara(_ayar(), oturum, http=http, yz=_yz())
    boru.tara(_ayar(), oturum, http=http, yz=_yz())  # firma başarıyla tarandı, Jooble ilanı bu taramada yok

    def aktif():
        with oturum() as o:
            return o.scalar(select(IlanKaydi.aktif).where(IlanKaydi.kaynak == "jooble"))

    assert aktif() is True
    assert bakim_yap(oturum)["gorulmeyen_jooble"] == 0
    with oturum.begin() as o:
        o.execute(update(IlanKaydi).values(son_gorulme=simdi() - timedelta(days=22)))
    assert bakim_yap(oturum)["gorulmeyen_jooble"] == 1
    assert aktif() is False


def test_konum_ve_guncellik_jooble_kurallari():
    assert konum_uygun(Ilan(firma="F", baslik="B", url="u", kaynak="jooble", konum="Manisa"))
    gecmis = guncellik("jooble", "2026-10-30", None, None, {2024}, BUGUN)
    assert gecmis["bayat"] == "gecmis_donem"
    eski = guncellik("jooble", "2024-01-01", None, None, set(), BUGUN)
    assert eski["surekli_acik"] is False


def test_baglanti_hatasi_taramayi_durdurmaz(oturum):
    http = SahteHttp(jsonlar={"tr.jooble.org": requests.ConnectionError(f"https://tr.jooble.org/api/{ANAHTAR}")})
    rapor = boru.tara(_ayar(), oturum, http=http, yz=_yz())
    assert rapor.hatalar == ["jooble: ConnectionError"] and rapor.jooble_ilan == 0
