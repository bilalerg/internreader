"""Başvuru kanıtı: ağ hatası kapanış değildir; yanlış sayfanın metni ilanı kapatmaz."""

from datetime import UTC, datetime, timedelta

import pytest
import requests

from internreader import depo
from internreader.ag import HttpIstemci, RobotsEngeli
from internreader.ayar import ayarlari_oku
from internreader.db import IlanDogrulama, IlanKaydi
from internreader.depo.dogrulama import dogrulama_yaz
from internreader.dogrulama import basvurulari_dogrula
from internreader.isleme.basvuru import BasvuruSonucu, alan_yasak, sayfayi_dogrula
from internreader.model import Ilan

URL = "https://acme.test/jobs/123"
BASLIK = "Python Intern"
AN = datetime(2026, 11, 15, 8, tzinfo=UTC)


def sayfa(icerik="", baslik=BASLIK):
    return f"<main><h1>{baslik}</h1>{icerik}</main>"


def karar(html, url=URL, son_url=URL):
    return sayfayi_dogrula(BASLIK, url, son_url, html)


@pytest.mark.parametrize(
    "metin",
    [
        "This position is closed.",
        "We are no longer accepting applications for this role.",
        "Başvurular kapanmıştır.",
        "Şu an başvuru kabul etmiyor",
    ],
)
def test_acik_kapanis_ifadesi(metin):
    assert karar(sayfa(f"<p>{metin}</p>")).durum == "kapali"


def test_200_veya_ilan_basligi_tek_basina_acik_kaniti_degil():
    assert karar(sayfa("<p>Python ve SQL.</p>")).durum == "belirsiz"
    assert karar(sayfa("<button disabled>Apply now</button>")).durum == "belirsiz"
    assert karar(sayfa("<form><fieldset disabled><button>Apply now</button></fieldset></form>")).durum == "belirsiz"
    assert karar(sayfa('<a href="javascript:apply()">Apply now</a>')).durum == "belirsiz"


def test_etkin_basvuru_ve_kapanis_cakisirsa_kapanis_oncelikli():
    kontrol = '<form><input type="email"><button type="submit">Apply now</button></form>'
    assert karar(sayfa(kontrol)).durum == "acik"
    assert karar(sayfa(kontrol + "<p>Applications are closed.</p>")).durum == "kapali"
    assert karar(sayfa('<button type="button">Apply</button>')).durum == "acik"
    assert karar(sayfa('<button type="button" disabled>Apply</button>')).durum == "belirsiz"
    assert karar(sayfa('<form><input type="submit" value="Başvuruyu gönder"></form>')).durum == "acik"


def test_tek_ilan_basligina_kariyer_soneki_eklenebilir():
    html = sayfa('<button type="button">Apply for this Role</button>', BASLIK + " - Acme Careers")
    assert karar(html).durum == "acik"
    assert karar(sayfa("<button>Apply</button>", BASLIK + " - Different job")).durum == "belirsiz"


def test_lever_ilanina_ozel_basvuru_baglantisi():
    url = "https://jobs.lever.co/acme/123"
    html = '<main>Python Intern Istanbul <a href="https://jobs.lever.co/acme/123/apply">Apply for this job</a></main>'
    assert karar(html, url=url, son_url=url).durum == "acik"
    assert karar(html.replace("/123/apply", "/456/apply"), url=url, son_url=url).durum == "belirsiz"
    assert karar(html.replace("Python Intern", "Data Intern"), url=url, son_url=url).durum == "belirsiz"


def test_bireysel_basvuru_formunda_ilan_basligi_url_ve_sayfada_olmali():
    url = "https://curiosity.tech/tr/careers/apply?title=Python+Intern"
    html = '<main><h1>Başvuru Formu</h1><p>Python Intern</p><form><button type="submit">Başvuruyu gönder</button></form></main>'
    assert karar(html, url=url, son_url=url).durum == "acik"
    assert karar(html.replace("Python Intern", "Data Intern"), url=url, son_url=url).durum == "belirsiz"
    assert (
        karar(
            html, url=url.replace("Python+Intern", "Data+Intern"), son_url=url.replace("Python+Intern", "Data+Intern")
        ).durum
        == "belirsiz"
    )


def test_baska_ilan_footer_gizli_metin_ve_negasyon_kapanis_sayilmaz():
    html = sayfa('<p>Build a detector for applications closed messages.</p><a href="/apply">Apply now</a>')
    html += "<footer>Applications are closed</footer>"
    assert karar(html).durum == "acik"
    assert karar(sayfa("<aside>This position is closed</aside>")).durum == "belirsiz"
    assert karar(sayfa("<div hidden>This position is closed</div>")).durum == "belirsiz"
    assert karar(sayfa('<div style="display: none">This position is closed</div>')).durum == "belirsiz"
    assert karar(sayfa('<div class="related-jobs"><h1>Other job</h1>This position is closed</div>')).durum == "belirsiz"


def test_liste_yonlendirme_ve_bot_engeli_belirsiz():
    assert karar(sayfa("This position is closed", "Other job")).durum == "belirsiz"
    assert karar(sayfa("This position is closed"), son_url="https://acme.test/careers").durum == "belirsiz"
    assert karar(sayfa("This position is closed"), url=URL + "#123").durum == "belirsiz"
    assert karar(sayfa("Verify you are human. This position is closed")).durum == "belirsiz"


def test_ayni_ilanin_yeni_detay_adresi_dogrulanir():
    yeni_adres = "https://acme.test/jobs/python-intern-123"
    assert karar(sayfa('<a href="/apply/123">Apply now</a>'), son_url=yeni_adres).durum == "acik"
    assert karar(sayfa("<p>This position is closed.</p>"), son_url=yeni_adres).durum == "kapali"


def test_kariyer_listesine_yonlenince_yalniz_eslesen_kartin_basvurusu_kanit():
    kariyer = "https://acme.test/careers"
    html = """<h1>Careers</h1>
    <article class="job-card"><h2>Python Intern</h2><a href="/apply/123">Apply now</a></article>
    <article class="job-card"><h2>Data Intern</h2><a href="/apply/456">Apply now</a></article>"""
    assert karar(html, son_url=kariyer) == BasvuruSonucu("acik", "yonlendirilen_listede_eslesen_ilan_karti")
    assert karar(html.replace('<a href="/apply/123">Apply now</a>', "Closed"), son_url=kariyer).durum == "belirsiz"
    assert (
        karar(html.replace('<a href="/apply/123">Apply now</a>', '<a href="#">Apply now</a>'), son_url=kariyer).durum
        == "belirsiz"
    )
    assert karar(html.replace('<a href="/apply/123">Apply now</a>', ""), son_url=kariyer).durum == "belirsiz"
    assert (
        karar(
            html + '<article class="job-card"><h2>Python Intern</h2><a href="/apply/789">Apply now</a></article>',
            son_url=kariyer,
        ).durum
        == "belirsiz"
    )


def test_eslesen_kart_disindaki_basvuru_baglantisi_acik_sayilmaz():
    html = """<h1>Careers</h1>
    <article class="job-card"><h2>Python Intern</h2>Closed</article>
    <article class="job-card"><h2>Data Intern</h2><a href="/apply/456">Apply now</a></article>
    <a href="/apply">Apply now</a>"""
    assert karar(html, son_url="https://acme.test/careers").durum == "belirsiz"


def ilan_kur(oturum, kaynak="kariyer_sayfasi", url=URL):
    i = Ilan(firma="Acme", baslik=BASLIK, url=url, kaynak=kaynak)
    with oturum.begin() as o:
        depo.ilanlari_kaydet(o, [i], set())
        depo.siniflandirma_kaydet(o, {i.kimlik: {"seviye": "staj", "rol": "yazilim", "yapay_zeka": "yok"}}, "test")
    return i


def test_iki_basarili_kayip_arasindaki_hata_sayilmaz_geri_gelirse_sifirlanir(oturum):
    i = ilan_kur(oturum)
    with oturum.begin() as o:
        assert depo.ilanlari_kaydet(o, [], {"Acme"})[1] == 0
        assert depo.ilanlari_kaydet(o, [], set())[1] == 0
        assert o.get(IlanDogrulama, i.kimlik).gorulmeme_sayisi == 1
        depo.ilanlari_kaydet(o, [i], {"Acme"})
        assert o.get(IlanDogrulama, i.kimlik).gorulmeme_sayisi == 0
        assert depo.ilanlari_kaydet(o, [], {"Acme"})[1] == 0
        assert depo.ilanlari_kaydet(o, [], {"Acme"})[1] == 1
        assert not o.get(IlanKaydi, i.kimlik).aktif


def test_kapanis_kaniti_listede_tekrar_gorulunce_ve_hata_olunca_silinmez(oturum):
    i = ilan_kur(oturum, "lever")
    with oturum.begin() as o:
        dogrulama_yaz(o, i.kimlik, BasvuruSonucu("kapali", "ilan_sayfasinda_acik_kapanis_ifadesi"), AN)
        depo.ilanlari_kaydet(o, [], {"Acme"})
        depo.ilanlari_kaydet(o, [], {"Acme"})
        depo.ilanlari_kaydet(o, [i], {"Acme"})
        dogrulama_yaz(o, i.kimlik, BasvuruSonucu("belirsiz", "HTTPError 403"), AN + timedelta(days=1))
    with oturum() as o:
        assert o.get(IlanDogrulama, i.kimlik).durum == "kapali"
        assert depo.yayinlanacak_ilanlar(o, an=AN + timedelta(days=1)) == []
    with oturum.begin() as o:
        dogrulama_yaz(
            o, i.kimlik, BasvuruSonucu("acik", "ilan_sayfasinda_etkin_basvuru_kontrolu"), AN + timedelta(days=2)
        )
    with oturum() as o:
        assert len(depo.yayinlanacak_ilanlar(o, an=AN + timedelta(days=2))) == 1


def test_belirsizlik_suresini_basarisiz_kontrol_uzatmaz_ve_sonuc_yayinda_aciklanir(oturum):
    i = ilan_kur(oturum)
    with oturum.begin() as o:
        k = o.get(IlanDogrulama, i.kimlik)
        k.ilk_kontrol = AN
        dogrulama_yaz(o, i.kimlik, BasvuruSonucu("acik", "ilan_sayfasinda_etkin_basvuru_kontrolu"), AN)
        dogrulama_yaz(o, i.kimlik, BasvuruSonucu("belirsiz", "Timeout"), AN + timedelta(days=2))
    with oturum() as o:
        yayin = depo.yayinlanacak_ilanlar(o, an=AN + timedelta(days=2))
        assert yayin[0]["dogrulama"]["durum"] == "belirsiz"
        assert depo.yayinlanacak_ilanlar(o, an=AN + timedelta(days=3)) == []
        assert (
            depo.yayinlanacak_ilanlar(o, an=AN + timedelta(days=3), bayatlar_dahil=True)[0]["bayat"]
            == "basvuru_dogrulanamadi"
        )


@pytest.mark.parametrize("kod", [403, 404, 410, 429, 503])
def test_http_hatasi_kapali_olarak_kaydedilmez(oturum, monkeypatch, kod):
    i = ilan_kur(oturum)
    monkeypatch.setattr("internreader.dogrulama.simdi", lambda: AN)
    yanit = requests.Response()
    yanit.status_code = kod

    class Http:
        def sayfa(self, url, **kwargs):
            raise requests.HTTPError(response=yanit)

    assert basvurulari_dogrula(ayarlari_oku(), oturum, http=Http())["belirsiz"] == 1
    with oturum() as o:
        assert o.get(IlanDogrulama, i.kimlik).durum == "belirsiz"
        assert o.get(IlanKaydi, i.kimlik).aktif


def test_gunluk_islem_kapali_ilani_yayindan_cikarir_ayni_gun_tekrar_istek_atmaz(oturum, monkeypatch):
    i = ilan_kur(oturum)
    monkeypatch.setattr("internreader.dogrulama.simdi", lambda: AN)

    class Http:
        cagrilar = 0

        def sayfa(self, url, **kwargs):
            self.cagrilar += 1
            return url, sayfa("<p>This position is closed.</p>")

    http = Http()
    assert basvurulari_dogrula(ayarlari_oku(), oturum, http=http)["kapali"] == 1
    assert basvurulari_dogrula(ayarlari_oku(), oturum, http=http)["kontrol_edilen"] == 0
    assert http.cagrilar == 1
    with oturum() as o:
        assert depo.yayinlanacak_ilanlar(o, an=AN) == []
        assert o.get(IlanKaydi, i.kimlik).aktif  # listede var, ancak başvurusu kapalı


def test_yasak_kaynak_dogrulayici_tarafindan_okunmaz(oturum, monkeypatch):
    ilan_kur(oturum, url="https://www.linkedin.com/jobs/view/123")
    monkeypatch.setattr("internreader.dogrulama.simdi", lambda: AN)

    class Http:
        def sayfa(self, *args, **kwargs):
            pytest.fail("Yasak kaynağa istek atıldı")

    assert basvurulari_dogrula(ayarlari_oku(), oturum, http=Http())["belirsiz"] == 1


def test_yasak_kaynaga_yonlendirmede_hedefe_robots_dahil_istek_atilmaz(monkeypatch):
    http = HttpIstemci("test")
    monkeypatch.setattr(http, "izinli_mi", lambda url: True)
    cagrilar = []

    class Yanit:
        is_redirect = True
        headers = {"location": "https://linkedin.com/jobs/123"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    def get(url, **kwargs):
        cagrilar.append(url)
        assert kwargs["allow_redirects"] is False
        return Yanit()

    monkeypatch.setattr(http.oturum, "get", get)
    with pytest.raises(RobotsEngeli):
        http.sayfa(URL, adres_izinli=lambda u: not alan_yasak(u))
    assert cagrilar == [URL]
