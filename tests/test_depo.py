from datetime import UTC, datetime

from internreader import depo
from internreader.model import Ilan


def ilan(url, baslik="Software Engineering Intern", firma="F"):
    return Ilan(firma=firma, baslik=baslik, url=url, kaynak="lever", konum="Istanbul")


def test_yeni_guncellenen_ve_kapanan_ilanlar(oturum):
    with oturum.begin() as o:
        yeni, kapanan = depo.ilanlari_kaydet(o, [ilan("https://u/1"), ilan("https://u/2")], {"F"})
    assert len(yeni) == 2 and kapanan == 0

    with oturum.begin() as o:  # ikinci gün: u/2 kalkmış, u/3 eklenmiş
        yeni, kapanan = depo.ilanlari_kaydet(o, [ilan("https://u/1"), ilan("https://u/3")], {"F"})
    assert len(yeni) == 1 and kapanan == 1


def test_taramasi_basarisiz_firmanin_ilanlari_kapatilmaz(oturum):
    with oturum.begin() as o:
        depo.ilanlari_kaydet(o, [ilan("https://u/1", firma="Çöken")], {"Çöken"})
    with oturum.begin() as o:
        _, kapanan = depo.ilanlari_kaydet(o, [], set())  # site bugün cevap vermedi
    assert kapanan == 0


def test_yalnizca_ogrenciye_uygun_ilanlar_yayinlanir(oturum):
    with oturum.begin() as o:
        depo.ilanlari_kaydet(o, [ilan("https://u/1"), ilan("https://u/2", "Satın Alma Mühendisi")], {"F"})
    k1, k2 = ilan("https://u/1").kimlik, ilan("https://u/2").kimlik
    with oturum.begin() as o:
        depo.siniflandirma_kaydet(
            o,
            {
                k1: {"seviye": "staj", "rol": "yazilim", "yapay_zeka": "arti"},
                k2: {"seviye": "deneyimli", "rol": "diger_teknik", "yapay_zeka": "yok"},
            },
            "claude-haiku-5-5",
        )
    with oturum() as o:
        yayin = depo.yayinlanacak_ilanlar(o)
        assert [i["kimlik"] for i in yayin] == [k1]
        assert depo.yayinlanacak_ilanlar(o, sonra=datetime(2100, 1, 1, tzinfo=UTC)) == []


def test_kural_ile_siniflananlar_yapay_zekayla_yeniden_denenir(oturum):
    with oturum.begin() as o:
        depo.ilanlari_kaydet(o, [ilan("https://u/1"), ilan("https://u/2")], {"F"})
    k1, k2 = ilan("https://u/1").kimlik, ilan("https://u/2").kimlik
    with oturum.begin() as o:
        depo.siniflandirma_kaydet(
            o, {k1: {"seviye": "staj", "rol": "yazilim", "yapay_zeka": "yok"}}, "claude-haiku-5-5"
        )
        depo.siniflandirma_kaydet(o, {k2: {"seviye": "staj", "rol": "yazilim", "yapay_zeka": "yok"}}, "kural")
    with oturum() as o:
        assert depo.siniflandirilmamislar(o, [k1, k2]) == {k2}


def test_firma_anahtari_alan_adindan_ve_tekrar_eklemede_guncelleme(oturum):
    assert depo.firma_anahtari("X", "https://www.Beakwise.com/") == "beakwise.com"
    with oturum.begin() as o:
        assert depo.firma_ekle_veya_guncelle(o, "Beakwise", web="https://beakwise.com", etiket=["teknopark"]) is True
        o.flush()
        assert (
            depo.firma_ekle_veya_guncelle(
                o, "Beakwise A.Ş.", web="beakwise.com", kariyer="https://beakwise.com/k", etiket=["ai"]
            )
            is False
        )
    with oturum() as o:
        f = depo.aktif_firmalar(o)[0]
        assert f.kariyer == "https://beakwise.com/k" and f.etiket == ["ai", "teknopark"]


def test_ayni_firma_adresli_ve_adresiz_gelince_tek_kayit_olur(oturum):
    with oturum.begin() as o:
        assert depo.firma_ekle_veya_guncelle(o, "VNGRS", etiket=["ai"]) is True
        o.flush()
        assert depo.firma_ekle_veya_guncelle(o, "VNGRS", web="https://vngrs.com") is False  # adres öğrenildi
        o.flush()
        assert depo.firma_ekle_veya_guncelle(o, "VNGRS") is False  # adresiz tekrar
    with oturum() as o:
        firmalar = depo.aktif_firmalar(o)
        assert len(firmalar) == 1 and firmalar[0].web == "https://vngrs.com" and firmalar[0].etiket == ["ai"]


def test_ilan_hunisi_elenenleri_sayar_siniri_gosterir(oturum):
    def kayit(url, baslik, konum, karar=None):
        i = Ilan(firma="Acme", baslik=baslik, url=url, kaynak="lever", konum=konum, tarih="")
        with oturum.begin() as o:
            depo.ilanlari_kaydet(o, [i], set())
            if karar:
                seviye, rol = karar
                depo.siniflandirma_kaydet(o, {i.kimlik: {"seviye": seviye, "rol": rol, "yapay_zeka": "yok"}}, "t")

    kayit("https://a.test/1", "Backend", "Berlin")
    kayit("https://a.test/2", "Bekleyen", "Istanbul")
    kayit("https://a.test/3", "Software Engineer", "Istanbul", ("belirsiz", "yazilim"))
    kayit("https://a.test/4", "Donanım Stajı", "Ankara", ("staj", "diger_teknik"))
    kayit("https://a.test/5", "Yazılım Stajı", "Istanbul", ("staj", "yazilim"))
    with oturum() as o:
        huni = depo.ilan_hunisi(o)
    assert huni["aktif"] == 5 and huni["konum_disi"] == 1 and huni["siniflanmamis"] == 1
    assert huni["ogrenciye_uygun"] == {"yayinda": 1}
    assert huni["ornek_belirsiz"] == ["Acme: Software Engineer"]
    assert huni["ornek_diger_teknik"] == ["Acme: Donanım Stajı"]
