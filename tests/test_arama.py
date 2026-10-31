import dataclasses

import requests
from sqlalchemy import select

from internreader import depo
from internreader.arama import (
    Sonuc,
    ad_alanla_uyusuyor_mu,
    adaylari_ayir,
    arama_kesfi,
    ats_adi,
    basliktan_ad,
    kariyer_adresi_mi,
    kariyer_sayfasi_ara,
    sorgular,
    web_adresi_bul,
)
from internreader.ayar import arama_ayari, ayarlari_oku
from internreader.db import Firma
from tests.conftest import SahteHttp


def _ayar(saglayici="serper"):
    return dataclasses.replace(ayarlari_oku(), arama_saglayici=saglayici, arama_anahtari="test-anahtari")


def _serper(*sonuclar):
    return {"organic": [{"link": u, "title": t} for u, t in sonuclar]}


def _lever(*konumlar):
    return [
        {"text": f"Intern {n}", "hostedUrl": f"https://jobs.lever.co/x/{n}", "categories": {"location": k}}
        for n, k in enumerate(konumlar)
    ]


def test_ilan_siteleri_elenir_panolar_ve_sirket_siteleri_ayrilir():
    sonuclar = [
        Sonuc("https://tr.linkedin.com/jobs/view/123", "Intern - LinkedIn"),
        Sonuc("https://www.kariyer.net/is-ilani/acme-stajyer", "Stajyer"),
        Sonuc("https://www.youthall.com/tr/acme/", "Acme"),
        Sonuc("https://jobs.lever.co/acme/abc", "Acme - Intern"),
        Sonuc("https://piworks.bamboohr.com/careers/3", "Part-Time Engineer"),
        Sonuc("https://www.kaizenloyalty.com/careers", "Careers | Kaizen Loyalty"),
        Sonuc("https://www.kaizenloyalty.com/about", "Hakkımızda"),
    ]
    ats, web, elenen = adaylari_ayir(sonuclar)
    assert ats == {("lever", "acme"): "Acme", ("bamboohr", "piworks"): "Piworks"}
    assert web == {"kaizenloyalty.com": "Kaizen Loyalty"}  # aynı alan adı bir kez
    assert elenen == 3


def test_basliktan_firma_adi():
    assert basliktan_ad("Kariyer | ACME Teknoloji", "acme.com.tr") == "ACME Teknoloji"
    assert basliktan_ad("Software Engineer Intern - Playable Factory", "playablefactory.com") == "Playable Factory"
    assert basliktan_ad("Açık Pozisyonlar", "nova-spark.com") == "Nova Spark"  # başlıkta ad yoksa alan adı
    assert ats_adi("playable-factory") == "Playable Factory"
    assert ats_adi("jobs.siemens.com|en_US/externaljobs") == "Siemens"


def test_sorgu_listesi_ats_ve_genel_sorgulari_icerir():
    s = sorgular()
    assert "site:jobs.lever.co Istanbul" in s and "site:bamboohr.com Türkiye" in s
    assert any("stajyeri" in x for x in s) and len(s) == len(set(s))


def test_arama_kesfi_dogrular_ekler_ve_mevcut_firmaya_baglar(oturum):
    with oturum.begin() as o:
        depo.firma_ekle_veya_guncelle(o, "P.I. Works", web="https://www.piworks.net")

    def serper_cevabi(url, govde):
        if govde["q"] == "site:jobs.lever.co Istanbul":
            return _serper(
                ("https://jobs.lever.co/acme/1", "Acme"),
                ("https://jobs.lever.co/dunya/2", "Dunya"),
                ("https://tr.linkedin.com/jobs/view/9", "LinkedIn"),
            )
        if govde["q"] == "site:bamboohr.com Istanbul":
            return _serper(("https://piworks.bamboohr.com/careers/3", "P.I. Works"))
        if govde["q"].startswith("yazılım stajyeri"):
            return _serper(("https://www.kaizenloyalty.com/careers", "Careers | Kaizen Loyalty"))
        return _serper()

    http = SahteHttp(
        jsonlar={
            "serper.dev": serper_cevabi,
            "lever.co/v0/postings/acme": _lever("Istanbul, Turkey", "Berlin"),
            "lever.co/v0/postings/dunya": _lever("Berlin"),  # aynı kısa ad, Türkiye'de ilanı yok → başka firma
            "piworks.bamboohr.com": {"result": [{"id": "3", "jobOpeningName": "PT", "location": {"city": "Istanbul"}}]},
        }
    )
    rapor = arama_kesfi(_ayar(), oturum, http=http, kesif_yap=False)

    assert rapor["yeni_ats"] == 2 and rapor["yeni_web"] == 1 and rapor["turkiye_disi_ya_da_kapali"] == 1
    with oturum() as o:
        firmalar = {f.ad: f for f in o.scalars(select(Firma))}
    assert firmalar["P.I. Works"].ats == "bamboohr" and "Piworks" not in firmalar  # çift kayıt açılmadı
    assert firmalar["Acme"].ats == "lever" and firmalar["Acme"].kaynak.startswith("arama_")
    assert firmalar["Kaizen Loyalty"].web == "https://kaizenloyalty.com"
    assert "Dunya" not in firmalar
    # anahtar başlıkta gider, ilan sitelerine hiç istek atılmaz
    assert all(b == {"X-API-KEY": "test-anahtari"} for u, _, b in http.istekler if "serper.dev" in u)
    assert not any("linkedin" in u for u, _, _ in http.istekler)


def test_kuru_calistirma_hicbir_sey_yazmaz(oturum):
    http = SahteHttp(
        jsonlar={
            "serper.dev": _serper(("https://www.kaizenloyalty.com/careers", "Careers | Kaizen Loyalty")),
        }
    )
    rapor = arama_kesfi(_ayar(), oturum, sorgu_siniri=2, kuru=True, http=http)
    assert rapor["durum"] == "kuru" and rapor["yeni_web"] == 1 and rapor["sorgu"] == 2
    with oturum() as o:
        assert o.scalar(select(Firma).limit(1)) is None


def test_anahtar_yoksa_atlanir_ve_istek_atilmaz(oturum):
    http = SahteHttp()
    assert arama_kesfi(_ayar(saglayici=""), oturum, http=http) == {"durum": "anahtar-yok"}
    assert http.istekler == []


def test_gecersiz_anahtarda_kota_harcamadan_durur(oturum):
    yanit = requests.Response()
    yanit.status_code = 401
    http = SahteHttp(jsonlar={"serper.dev": requests.HTTPError("401 Client Error: Unauthorized", response=yanit)})
    rapor = arama_kesfi(_ayar(), oturum, http=http)
    assert len(http.istekler) == 1 and len(rapor["hatalar"]) == 1 and rapor.get("sorgu", 0) == 0


def test_brave_saglayicisi_dogru_cevabi_okur(oturum):
    http = SahteHttp(
        jsonlar={
            "api.search.brave.com": {"web": {"results": [{"url": "https://acme.com.tr/kariyer", "title": "Acme"}]}}
        }
    )
    rapor = arama_kesfi(_ayar("brave"), oturum, sorgu_siniri=1, kuru=True, http=http)
    assert rapor["yeni_web"] == 1
    url, _, basliklar = http.istekler[0]
    assert basliklar == {"X-Subscription-Token": "test-anahtari"} and "country=TR" in url


def test_web_adresi_yalnizca_adla_uyusan_siteye_yazilir(oturum):
    with oturum.begin() as o:
        depo.firma_ekle_veya_guncelle(o, "Siemens")
        depo.firma_ekle_veya_guncelle(o, "Nova Spark X Teknoloji")

    def cevap(url, govde):
        if "Siemens" in govde["q"]:
            return _serper(
                ("https://tr.linkedin.com/company/siemens", "x"), ("https://www.siemens.com/tr/tr.html", "x")
            )
        return _serper(("https://patika.dev/kariyer", "Patika"))

    http = SahteHttp(jsonlar={"serper.dev": cevap})
    rapor = web_adresi_bul(_ayar(), oturum, http=http, kesif_yap=False)
    assert rapor["bulunan"] == 1
    with oturum() as o:
        firmalar = {f.ad: f for f in o.scalars(select(Firma))}
    assert firmalar["Siemens"].web == "https://siemens.com" and firmalar["Siemens"].anahtar == "siemens.com"
    assert firmalar["Nova Spark X Teknoloji"].web is None


def test_ad_alan_uyumu():
    assert ad_alanla_uyusuyor_mu("Siemens", "siemens.com.tr")
    assert ad_alanla_uyusuyor_mu("Kaizen Loyalty", "kaizen-loyalty.com")
    assert not ad_alanla_uyusuyor_mu("Nova Spark X Teknoloji", "patika.dev")
    assert not ad_alanla_uyusuyor_mu("ABC Yazılım", "abcd.com")  # 4 harften kısa kelime eşleşme sayılmaz


def test_arama_saglayicisi_secimi(monkeypatch):
    for ad in ("SERPER_API_KEY", "BRAVE_API_KEY", "INTERNREADER_ARAMA_SAGLAYICI"):
        monkeypatch.delenv(ad, raising=False)
    assert arama_ayari() == ("", "")
    monkeypatch.setenv("BRAVE_API_KEY", "b")
    assert arama_ayari() == ("brave", "b")
    monkeypatch.setenv("SERPER_API_KEY", "s")
    assert arama_ayari() == ("serper", "s")  # ikisi de varsa Serper
    monkeypatch.setenv("INTERNREADER_ARAMA_SAGLAYICI", "brave")
    assert arama_ayari() == ("brave", "b")
    monkeypatch.delenv("BRAVE_API_KEY")
    assert arama_ayari() == ("", "")  # seçilen sağlayıcının anahtarı yoksa kapalı


def test_web_adresi_bulunamayan_firma_hemen_yeniden_sorgulanmaz(oturum):
    with oturum.begin() as o:
        depo.firma_ekle_veya_guncelle(o, "Nova Spark X Teknoloji")
    http = SahteHttp(jsonlar={"serper.dev": _serper(("https://patika.dev/kariyer", "Patika"))})
    assert web_adresi_bul(_ayar(), oturum, http=http, kesif_yap=False)["sorgu"] == 1
    assert web_adresi_bul(_ayar(), oturum, http=http, kesif_yap=False).get("sorgu", 0) == 0
    assert len(http.istekler) == 1


def test_kariyer_adresi_yalnizca_firmanin_kendi_kariyer_sayfasidir():
    assert kariyer_adresi_mi("https://www.acme.com.tr/tr/kariyer", "acme.com.tr")
    assert kariyer_adresi_mi("https://kariyer.acme.com.tr/", "acme.com.tr")
    assert not kariyer_adresi_mi("https://www.acme.com.tr/hakkimizda", "acme.com.tr")
    assert not kariyer_adresi_mi("https://www.acme.com.tr/blog/kariyer", "acme.com.tr")
    assert not kariyer_adresi_mi("https://notacme.com.tr/kariyer", "acme.com.tr")


def test_kariyer_sayfasi_aranir_ilan_sistemi_yazilir_ve_ayni_firma_tekrar_sorgulanmaz(oturum):
    with oturum.begin() as o:
        depo.firma_ekle_veya_guncelle(o, "Kurumsal", web="https://kurumsal.com", etiket=["teknopark"])
        depo.firma_ekle_veya_guncelle(o, "Girisim", web="https://girisim.ai", etiket=["girisim"])
        depo.firma_ekle_veya_guncelle(o, "Bos", web="https://bos.com", etiket=["ai"])

    def cevap(url, govde):
        if "site:girisim.ai" in govde["q"]:
            return _serper(("https://girisim.ai/careers", "Careers"))
        if "site:kurumsal.com" in govde["q"]:
            return _serper(("https://kurumsal.com/kariyer", "Kariyer"))
        return _serper(("https://bos.com/hakkimizda", "Biz"))

    sayfalar = {
        "https://girisim.ai/careers": '<a href="https://jobs.lever.co/girisim">Jobs</a>',
        "https://kurumsal.com/kariyer": "<p>Kariyer</p>",
    }
    http = SahteHttp(jsonlar={"serper.dev": cevap}, sayfalar=sayfalar)
    rapor = kariyer_sayfasi_ara(_ayar(), oturum, sinir=2, http=http)
    assert rapor["sorgu"] == 2 and rapor["kalan"] == 1
    gonderilen = [g["q"] for _, g, _ in http.istekler]
    assert "site:girisim.ai" in gonderilen[0] and "site:bos.com" in gonderilen[1]  # öncelik: girişim, sonra ai
    with oturum() as o:
        firmalar = {f.ad: f for f in o.scalars(select(Firma))}
    assert firmalar["Girisim"].ats == "lever" and firmalar["Girisim"].slug == "girisim"
    assert firmalar["Bos"].kariyer is None

    ikinci = SahteHttp(jsonlar={"serper.dev": cevap}, sayfalar=sayfalar)
    rapor = kariyer_sayfasi_ara(_ayar(), oturum, sinir=5, http=ikinci)
    assert rapor["sorgu"] == 1 and rapor["bulunan"] == 1  # yalnızca denenmemiş olan
    with oturum() as o:
        assert o.scalar(select(Firma).where(Firma.ad == "Kurumsal")).kariyer == "https://kurumsal.com/kariyer"


def test_kariyer_aramasi_kuru_modda_yazmaz_ve_anahtarsiz_atlanir(oturum):
    with oturum.begin() as o:
        depo.firma_ekle_veya_guncelle(o, "Firma", web="https://firma.com")
    http = SahteHttp(jsonlar={"serper.dev": _serper(("https://firma.com/careers", "C"))})
    rapor = kariyer_sayfasi_ara(_ayar(), oturum, http=http, kuru=True)
    assert rapor["durum"] == "kuru" and rapor["bulunan"] == 1
    with oturum() as o:
        assert o.scalar(select(Firma)).kariyer is None
    assert kariyer_sayfasi_ara(_ayar(""), oturum)["durum"] == "anahtar-yok"
