import datetime

from internreader.kaynaklar.ats import greenhouse_ayristir, lever_ayristir, workday_tarihi


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
