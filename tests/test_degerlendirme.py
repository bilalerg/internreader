"""Değerlendirme puanlaması: doğruluk, öğrenciye uygunluk isabet/kapsama, belirsiz alanların puanlanmaması."""

from internreader.yz.degerlendirme import degerlendir, puanla
from internreader.yz.siniflandirici import IlanSinifi, TopluSiniflandirma
from tests.conftest import SahteYz

ORNEKLER = [
    {"baslik": "SE Intern", "firma": "A", "beklenen_seviye": "staj", "beklenen_rol": "yazilim"},
    {"baslik": "Senior SE", "firma": "A", "beklenen_seviye": "deneyimli", "beklenen_rol": "yazilim"},
    {"baslik": "Marketing Intern", "firma": "A", "beklenen_seviye": "staj", "beklenen_rol": "teknik_degil"},
    {"baslik": "Operatör", "firma": "A", "beklenen_seviye": None, "beklenen_rol": "diger_teknik"},
]


def karar(seviye, rol):
    return {"seviye": seviye, "rol": rol, "yapay_zeka": "yok", "gerekce": "t"}


def test_puanlama():
    tahminler = [
        karar("staj", "yazilim"),  # doğru, uygun
        karar("junior", "yazilim"),  # seviye yanlış → yanlış pozitif
        karar("staj", "teknik_degil"),  # doğru, uygun değil
        karar("belirsiz", "diger_teknik"),  # seviye puanlanmaz
    ]
    s = puanla(ORNEKLER, tahminler)
    assert s["seviye_dogruluk"] == round(2 / 3, 3) and s["rol_dogruluk"] == 1.0
    assert s["ogrenciye_uygun_isabet"] == 0.5 and s["ogrenciye_uygun_kapsama"] == 1.0
    assert [h["baslik"] for h in s["hatalar"]] == ["Senior SE"]


def test_degerlendirme_siniflandiriciyi_calistirir():
    def cevap(tur, mesaj):
        satirlar = mesaj.splitlines()
        return TopluSiniflandirma(
            sonuclar=[
                IlanSinifi(
                    no=n, seviye="staj" if "Intern" in s else "deneyimli", rol="yazilim", yapay_zeka="yok", gerekce="t"
                )
                for n, s in enumerate(satirlar)
            ]
        )

    sonuc = degerlendir(SahteYz(cevap), ORNEKLER[:2])
    assert sonuc["seviye_dogruluk"] == 1.0 and sonuc["ogrenciye_uygun_kapsama"] == 1.0
