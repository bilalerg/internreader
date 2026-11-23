from ops.firma_temizlik_ozeti import karar


def test_erisilemeyen_sirket_kapanmis_sayilmaz():
    satir = {"faaliyet_durumu": "belirsiz", "site_durumu": "erisilemedi", "ats": "", "kariyer": ""}
    assert karar(satir) == (3, "tekrar_ve_elle_kontrol")


def test_park_edilmis_alan_adi_elle_dogrulanir():
    satir = {"faaliyet_durumu": "adres_sorunlu", "site_durumu": "acildi", "ats": "", "kariyer": ""}
    assert karar(satir) == (1, "alan_adini_elle_dogrula")
