from internreader.kaynaklar.kariyer_sayfasi import html_ayikla
from internreader.model import FirmaBilgisi
from internreader.yz.istemci import CiktiBozuk
from internreader.yz.sayfa_okuyucu import (
    Pozisyon,
    SayfaSonucu,
    baglanti_listesi,
    dogrula,
    ilanlara_cevir,
    parcala,
    sayfayi_oku,
)
from tests.conftest import SahteYz

HTML = """<html><head><script>gizli()</script></head><body>
<h1>Kariyer</h1><a href="/ilan/1">Software Engineering Intern</a>
<a href='https://x.com/ilan/2'>Backend Developer</a><p>Genel başvuru için CV gönderin.</p></body></html>"""


def test_html_ayikla_metin_ve_baglanti():
    icerik = html_ayikla(HTML, "https://firma.com/kariyer")
    assert "gizli" not in icerik.metin and "Software Engineering Intern" in icerik.metin
    assert ("Software Engineering Intern", "https://firma.com/ilan/1") in icerik.baglantilar
    assert ("Backend Developer", "https://x.com/ilan/2") in icerik.baglantilar


def test_html_ayikla_bozuk_adresli_baglantiyi_atlar():
    # Gerçek bir sitede görülen hata: köşeli parantezli adres urljoin'i çökertiyordu
    icerik = html_ayikla('<a href="http://[getaquotelink]">Teklif</a><a href="/staj">Staj</a>', "https://f.com/")
    assert icerik.baglantilar == [("Staj", "https://f.com/staj")]


def test_dogrula_uydurma_basligi_atar_ve_linki_numaradan_bulur():
    icerik = html_ayikla(HTML, "https://firma.com/kariyer")
    pozisyonlar = [
        Pozisyon(baslik="Software Engineering Intern", link_no=0, seviye="staj"),
        Pozisyon(baslik="Machine Learning Engineer", link_no=1, seviye="deneyimli"),  # sayfada yok → uydurma
        Pozisyon(baslik="Software Engineering Intern", link_no=0, seviye="staj"),  # tekrar
        Pozisyon(baslik="Backend Developer", link_no=99, seviye="belirsiz"),  # geçersiz numara
    ]
    gecen, atilan = dogrula(pozisyonlar, icerik.metin, icerik.baglantilar)
    assert [p["baslik"] for p in gecen] == ["Software Engineering Intern", "Backend Developer"]
    assert gecen[0]["link"] == "https://firma.com/ilan/1" and gecen[1]["link"] is None
    assert atilan == ["Machine Learning Engineer"]


def test_parcala_uzun_metni_bolup_sinirlar():
    assert parcala("a" * 100, boy=200) == ["a" * 100]
    assert len(parcala("a" * 50_000, boy=12_000, azami=3)) == 3


def test_cevap_kesilirse_parcayi_ikiye_bolup_dener():
    metin = ("Kariyer sayfası. Software Engineering Intern. " * 80).strip()  # ~3.7 bin karakter
    icerik = html_ayikla(f"<p>{metin}</p>", "https://firma.com/k")

    def cevap(tur, mesaj):
        if len(mesaj) > 3_000:  # büyük parça → "yarıda kesildi"
            raise CiktiBozuk("kesildi")
        return SayfaSonucu(
            kariyer_sayfasi_mi=True,
            genel_basvuru_var_mi=False,
            pozisyonlar=[Pozisyon(baslik="Software Engineering Intern", seviye="staj")],
        )

    yz = SahteYz(cevap)
    sonuc = sayfayi_oku(yz, "Firma", icerik)
    assert len(yz.cagrilar) >= 3  # 1 başarısız + en az 2 yarım parça
    assert [p["baslik"] for p in sonuc["pozisyonlar"]] == ["Software Engineering Intern"]


def test_ilanlara_cevir_linksiz_pozisyona_kalici_adres_verir():
    firma = FirmaBilgisi(id=1, ad="Beakwise", etiket=["teknopark"])
    ilanlar = ilanlara_cevir(
        firma,
        "https://b.com/careers",
        {"pozisyonlar": [{"baslik": "Intern", "link": None, "konum": None, "seviye": "staj"}]},
    )
    assert ilanlar[0].url.startswith("https://b.com/careers#") and ilanlar[0].calisma_tipi == "staj"
    assert (
        ilanlara_cevir(
            firma,
            "https://b.com/careers",
            {"pozisyonlar": [{"baslik": "Intern", "link": None, "konum": None, "seviye": "staj"}]},
        )[0].kimlik
        == ilanlar[0].kimlik
    )


def test_baglanti_listesi_parcaya_ozel_ve_kisa():
    baglantilar = [
        ("Software Engineering Intern", "https://firma.com/ilan/1?ref=kariyer"),
        ("Gizlilik", "https://firma.com/gizlilik"),
        ("Backend Developer", "https://jobs.lever.co/firma/2"),
    ]
    liste = baglanti_listesi(
        "Açık pozisyonlar: Software Engineering Intern, Backend Developer", baglantilar, "https://firma.com/kariyer"
    )
    assert (
        liste
        == "[0] Software Engineering Intern -> /ilan/1?ref=kariyer\n[2] Backend Developer -> jobs.lever.co/firma/2"
    )
