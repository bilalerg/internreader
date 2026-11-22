from datetime import UTC, datetime, timedelta

from internreader.db import Firma, IlanDogrulama, IlanKaydi, oturum_fabrikasi
from internreader.firma_faaliyeti import _orneklem, firmalari_denetle, sayfa_kaniti

AN = datetime(2026, 11, 22, tzinfo=UTC)


def test_sayfa_erisimi_ve_footer_yili_faaliyet_kaniti_degildir():
    sonuc = sayfa_kaniti("https://ornek.com", "https://ornek.com", "<footer>© 2026</footer>", AN)
    assert sonuc.durum == "belirsiz"


def test_tarihli_haber_yalnizca_ayni_alanda_kanit_sayilir():
    html = '<article><h2>Yeni ürünümüz</h2><time datetime="2026-10-01"></time><a href="/haber/1">Oku</a></article>'
    assert sayfa_kaniti("https://ornek.com", "https://ornek.com", html, AN).durum == "faal"
    assert (
        sayfa_kaniti(
            "https://ornek.com", "https://ornek.com", html.replace("/haber/1", "https://baska.com/1"), AN
        ).durum
        == "belirsiz"
    )
    assert (
        sayfa_kaniti("https://ornek.com", "https://ornek.com", html.replace("2026-10-01", "2024-10-01"), AN).durum
        == "belirsiz"
    )


def test_park_adres_sorunlu_ama_yonlendirme_belirsiz():
    assert sayfa_kaniti("https://ornek.com", "https://ornek.com", "Domain is for sale", AN).durum == "adres_sorunlu"
    assert sayfa_kaniti("https://ornek.com", "https://yeni.com", "Normal sayfa", AN).durum == "belirsiz"


def test_acik_ilan_kanittir_kuru_mod_veritabanini_degistirmez(tmp_path):
    oturum = oturum_fabrikasi(f"sqlite:///{(tmp_path / 'firma.db').as_posix()}")
    with oturum.begin() as o:
        o.add(Firma(anahtar="ornek.com", ad="Örnek", web="https://ornek.com"))
        o.add(IlanKaydi(kimlik="1", firma="Örnek", baslik="Mühendis", url="https://ornek.com/is", kaynak="sayfa"))
        o.flush()
        o.add(IlanDogrulama(kimlik="1", durum="acik", acik_dogrulama_zamani=datetime.now(UTC)))

    class SahteHttp:
        def sayfa(self, *_args, **_kwargs):
            raise AssertionError("Doğrulanmış açık ilan varsa site yeniden okunmaz")

    rapor = firmalari_denetle(oturum, "test", sinir=1, kuru=True, http=SahteHttp())
    assert rapor["durumlar"] == {"faal": 1}
    with oturum() as o:
        assert o.get(Firma, 1).faaliyet_durumu == "belirsiz"
    firmalari_denetle(oturum, "test", sinir=1, kuru=False, http=SahteHttp())
    with oturum() as o:
        assert o.get(Firma, 1).faaliyet_durumu == "faal"


def test_sonraki_parti_once_hic_denetlenmeyenleri_secer():
    eski = Firma(id=1, anahtar="eski", ad="Eski", kaynak="x", faaliyet_kontrol_zamani=AN)
    yeni = Firma(id=2, anahtar="yeni", ad="Yeni", kaynak="x")
    assert _orneklem([eski, yeni], 1)[0].ad == "Yeni"


def test_eski_acik_ilan_artik_faaliyet_kaniti_degildir(tmp_path):
    oturum = oturum_fabrikasi(f"sqlite:///{(tmp_path / 'eski.db').as_posix()}")
    with oturum.begin() as o:
        o.add(Firma(anahtar="eski", ad="Eski"))
        o.add(IlanKaydi(kimlik="2", firma="Eski", baslik="Mühendis", url="https://ornek.com/is", kaynak="sayfa"))
        o.flush()
        o.add(IlanDogrulama(kimlik="2", durum="acik", acik_dogrulama_zamani=datetime.now(UTC) - timedelta(days=4)))
    rapor = firmalari_denetle(oturum, "test", sinir=1)
    assert rapor["durumlar"] == {"belirsiz": 1}
