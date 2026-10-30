import datetime
import urllib.parse

import pytest
import requests

from internreader.kaynaklar.ats import greenhouse_ayristir, lever_ayristir, workday_tarihi
from tests.conftest import SahteHttp


def test_lever_ayristirma():
    veri = [
        {
            "text": "Software Engineer (Part-time)",
            "hostedUrl": "https://jobs.lever.co/x/1",
            "categories": {"location": "Istanbul", "commitment": "Part-time"},
            "createdAt": 1700000000000,
            "descriptionPlain": "Unity ve C#",
        }
    ]
    ilan = lever_ayristir("Dream Games", veri)[0]
    assert ilan.baslik == "Software Engineer (Part-time)"
    assert ilan.konum == "Istanbul" and ilan.calisma_tipi == "Part-time" and ilan.kaynak == "lever"
    assert ilan.tarih.startswith("2023-")


def test_greenhouse_html_aciklamayi_duz_metne_cevirir():
    veri = {
        "jobs": [
            {
                "title": "New Grad",
                "absolute_url": "https://gh/1",
                "location": {"name": "Sarıyer, Istanbul"},
                "updated_at": "2026-09-29T10:00:00Z",
                "content": "&lt;p&gt;Go &amp;amp; AWS&lt;/p&gt;",
            }
        ]
    }
    ilan = greenhouse_ayristir("Good Job Games", veri)[0]
    assert ilan.aciklama == "Go & AWS"
    assert ilan.tarih == "2026-09-29"


def test_kimlik_url_den_turetilir_ve_kalicidir():
    a = lever_ayristir("X", [{"text": "A", "hostedUrl": "https://u/1"}])[0]
    b = lever_ayristir("X", [{"text": "Başka başlık", "hostedUrl": "https://u/1"}])[0]
    assert a.kimlik == b.kimlik and len(a.kimlik) == 16


def test_workday_goreli_tarihi_gercek_tarihe_cevrilir():
    bugun = datetime.date(2026, 10, 18)
    assert workday_tarihi("Posted Today", bugun) == "2026-10-18"
    assert workday_tarihi("Posted Yesterday", bugun) == "2026-10-17"
    assert workday_tarihi("Posted 30+ Days Ago", bugun) == "2026-09-18"
    assert workday_tarihi("", bugun) == ""


# ---------- 29.10.2026: BambooHR, Teamtailor, Personio, Avature ----------
def test_bamboohr_ayristirma_konum_ve_uzaktan():
    from internreader.kaynaklar.ats import bamboohr_ayristir

    veri = {
        "meta": {"totalCount": 2},
        "result": [
            {
                "id": "3",
                "jobOpeningName": "Part-Time SW Product Design Engineer",
                "employmentStatusLabel": "Part-Time",
                "location": {"city": "Istanbul", "state": "Turkey"},
                "atsLocation": {"country": None, "city": None},
                "isRemote": None,
            },
            {
                "id": "7",
                "jobOpeningName": "Data Intern",
                "employmentStatusLabel": "Intern",
                "location": {"city": None, "state": None},
                "atsLocation": {"country": "Türkiye", "city": "Ankara"},
                "isRemote": True,
            },
        ],
    }
    a, b = bamboohr_ayristir("P.I. Works", "piworks", veri)
    assert a.url == "https://piworks.bamboohr.com/careers/3" and a.kaynak == "bamboohr"
    assert a.konum == "Istanbul, Turkey" and a.calisma_tipi == "Part-Time"
    assert b.konum == "Ankara, Türkiye (uzaktan)"


TEAMTAILOR_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:tt="https://teamtailor.com/locations"><channel><title>Acme</title>
<item><title>Backend Intern</title><description>&lt;p&gt;Python &amp;amp; SQL&lt;/p&gt;</description>
<pubDate>Fri, 23 Oct 2026 08:04:49 +0200</pubDate><link>https://acme.teamtailor.com/jobs/1-backend-intern</link>
<remoteStatus>hybrid</remoteStatus><tt:locations><tt:location><tt:city>Istanbul</tt:city>
<tt:country>Turkey</tt:country></tt:location></tt:locations></item>
<item><title></title><link>https://acme.teamtailor.com/jobs/2</link></item>
</channel></rss>"""


def test_teamtailor_rss_ayristirma():
    from internreader.kaynaklar.ats import teamtailor_ayristir

    ilanlar = teamtailor_ayristir("Acme", TEAMTAILOR_RSS)
    assert len(ilanlar) == 1  # başlıksız öğe atlanır
    i = ilanlar[0]
    assert i.baslik == "Backend Intern" and i.kaynak == "teamtailor"
    assert i.konum == "Istanbul, Turkey (hibrit)" and i.tarih == "2026-10-23"
    assert i.aciklama == "Python & SQL"


def test_personio_xml_ayristirma():
    from internreader.kaynaklar.ats import personio_ayristir

    xml = """<?xml version="1.0" encoding="UTF-8"?><workzag-jobs><position><id>42</id><office>Istanbul</office>
    <name>Working Student Software</name><employmentType>intern</employmentType><schedule>part-time</schedule>
    <createdAt>2026-10-20T09:00:00+00:00</createdAt><jobDescriptions><jobDescription><name>Görev</name>
    <value><![CDATA[<p>FastAPI ve React</p>]]></value></jobDescription></jobDescriptions></position>
    <position><name>Kimliksiz</name></position></workzag-jobs>"""
    ilanlar = personio_ayristir("Acme", "acme", xml)
    assert len(ilanlar) == 1  # kimliği olmayan pozisyonun bağlantısı kurulamaz
    i = ilanlar[0]
    assert i.url == "https://acme.jobs.personio.de/job/42" and i.konum == "Istanbul"
    assert i.calisma_tipi == "intern, part-time" and i.tarih == "2026-10-20" and i.aciklama == "FastAPI ve React"


def _avature_rss(*ogeler):
    govde = "".join(
        f"<item><title>{b}</title><link>{u}</link><pubDate>Tue, 22 Aug 2023</pubDate></item>" for b, u in ogeler
    )
    return f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>{govde}</channel></rss>'


def _avature_detay(konumlar, tarih="16-Sep-2026", mod="Hybrid (Remote/Office)"):
    def alan(ad, deger):
        return (
            f'<div class="article__content__view__field"><div class="article__content__view__field__label"> {ad} </div>'
            f'<div class="article__content__view__field__value"> {deger} </div></div>'
        )

    yerler = "".join(f'<li class="list__item"> {k} </li>' for k in konumlar)
    return (
        f"<main><article>{alan('Posted since', tarih)}{alan('Job type', 'Part-time')}{alan('Work mode', mod)}"
        f"{alan('Location(s)', f'<ul>{yerler}</ul>')}</article>"
        "<article>Develop modern web applications for the Gebze factory. Angular and TypeScript required.</article></main>"
    )


def test_avature_konum_tarih_ve_metin_detay_sayfasindan():
    from internreader.isleme.kategori import calisma_modeli
    from internreader.isleme.sehir import sehirleri_bul
    from internreader.kaynaklar.ats import AVATURE_ARAMALARI, avature

    kok = "https://jobs.siemens.com/en_US/externaljobs/SearchJobs/feed/?search="
    site = "https://jobs.siemens.com/externaljobs/JobDetail"
    sayfalar = {kok + urllib.parse.quote(a): _avature_rss() for a in AVATURE_ARAMALARI}
    sayfalar[kok + "Turkey"] = _avature_rss(
        ("Part Time Working Student (Front End Developer)", f"{site}/Front-End/522625"),
        ("Tester Intern", f"{site}/Tester/508759"),  # arama "Turkey" dese de ilan Slovakya'da
        ("Senior Robotics Engineer", f"{site}/Senior/517494"),  # öğrenci ilanı değil: detay sayfası açılmaz
    )
    sayfalar[kok + "Istanbul"] = _avature_rss(
        ("Part Time Working Student (Front End Developer)", f"{site}/Front-End/522625"),  # tekrar
    )
    sayfalar[f"{site}/Front-End/522625"] = _avature_detay(["Gebze - Kocaeli - Türkiye", "Kocaeli - Kocaeli - Türkiye"])
    sayfalar[f"{site}/Tester/508759"] = _avature_detay(["Zilina - Zilina - Slovakia"])

    (ilan,) = avature(SahteHttp(sayfalar=sayfalar), "Siemens", "jobs.siemens.com|en_US/externaljobs")
    assert ilan.baslik == "Part Time Working Student (Front End Developer)"
    assert ilan.konum == "Gebze, Kocaeli, Türkiye; Kocaeli, Kocaeli, Türkiye (Hibrit)"
    assert sehirleri_bul(ilan.konum) == ["kocaeli"] and calisma_modeli(ilan.konum, None) == "hibrit"
    assert ilan.tarih == "2026-09-16" and ilan.calisma_tipi == "Part-time"
    assert "Angular" in ilan.aciklama


def test_avature_kalkmis_ilan_atlanir_baska_hata_firmayi_basarisiz_sayar():
    from internreader.kaynaklar.ats import AVATURE_ARAMALARI, avature

    kok = "https://jobs.siemens.com/en_US/externaljobs/SearchJobs/feed/?search="
    sayfalar = {kok + urllib.parse.quote(a): _avature_rss() for a in AVATURE_ARAMALARI}
    sayfalar[kok + "Turkey"] = _avature_rss(("Tester Intern", "https://jobs.siemens.com/d/1"))

    class Hatali(SahteHttp):
        def __init__(self, kod):
            super().__init__(sayfalar=sayfalar)
            self.kod = kod

        def sayfa(self, url, robots_kontrolu=True):
            if url.endswith("/d/1"):
                yanit = requests.Response()
                yanit.status_code = self.kod
                raise requests.HTTPError(str(self.kod), response=yanit)
            return super().sayfa(url)

    assert avature(Hatali(404), "Siemens", "jobs.siemens.com|en_US/externaljobs") == []
    with pytest.raises(requests.HTTPError):
        avature(Hatali(500), "Siemens", "jobs.siemens.com|en_US/externaljobs")
