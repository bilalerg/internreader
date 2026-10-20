import pytest

from internreader.isleme.filtre import konum_uygun, yedek_siniflandirma
from internreader.isleme.tekillestirme import tekillestir
from internreader.model import HEDEF_ROLLER, OGRENCI_SEVIYELERI, Ilan


def ilan(baslik="X", konum="", kaynak="lever", url="https://u/1", tip=""):
    return Ilan(firma="F", baslik=baslik, url=url, kaynak=kaynak, konum=konum, calisma_tipi=tip)


@pytest.mark.parametrize(
    ("konum", "kaynak", "beklenen"),
    [
        ("Istanbul, İstanbul, Türkiye", "lever", True),
        ("Remote - EMEA", "lever", True),
        ("Chile, Remote", "greenhouse", False),
        ("Foster City, CA (uzaktan)", "ashby", False),
        ("", "kariyer_sayfasi", True),  # listemiz Türk firmaları; konum yoksa Türkiye
        ("", "lever", False),
    ],
)
def test_konum_uygun(konum, kaynak, beklenen):
    assert konum_uygun(ilan(konum=konum, kaynak=kaynak)) is beklenen


def uygun_mu(karar):
    return karar["seviye"] in OGRENCI_SEVIYELERI and karar["rol"] in HEDEF_ROLLER


def test_yedek_kural_satin_alma_muhendisini_ogrenciye_uygun_saymaz():
    # 18.10'daki gerçek hata: ASPİLSAN'ın deneyimli ilanları öğrenci ilanı sayılmıştı
    assert not uygun_mu(yedek_siniflandirma(ilan("Satın Alma Mühendisi/Uzmanı")))


def test_yedek_kural_yazilim_stajini_yakalar():
    karar = yedek_siniflandirma(ilan("Long-Term Software Engineering Intern"))
    assert karar["seviye"] == "staj" and karar["rol"] == "yazilim" and uygun_mu(karar)


def test_yedek_kural_pazarlama_stajini_teknik_saymaz():
    # 18.10'daki gerçek hata: "Social Media Marketing Intern (... AI)" teknik sayılmıştı
    assert not uygun_mu(yedek_siniflandirma(ilan("Social Media Marketing Intern (LinkedIn-Focused | B2B / SaaS / AI)")))


def test_tekillestirme_ayni_url_yi_birlestirir_ve_konumlari_toplar():
    a = ilan("ARGE Gömülü Yazılım Mühendisi", konum="Ankara", url="https://s/#1")
    b = ilan("ARGE Gömülü Yazılım Mühendisi", konum="Kayseri", url="https://s/#1")
    sonuc = tekillestir([a, b])
    assert len(sonuc) == 1 and sonuc[0].konum == "Ankara, Kayseri"
