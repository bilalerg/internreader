"""Keşif: ATS bağlantısı bulma, kariyer bağlantısı seçme ve yoklama (sahte ağ ile)."""

from internreader import depo
from internreader.ayar import ayarlari_oku
from internreader.kesif import firmayi_kesfet, kariyer_baglantilari, kesfet, sayfadan_ats_bul
from internreader.model import FirmaBilgisi
from tests.conftest import SahteHttp


def lever_ilani(konum):
    return {"text": "Software Engineer", "hostedUrl": "https://jobs.lever.co/x/1", "categories": {"location": konum}}


def test_sayfadaki_ats_baglantisi_bulunur():
    assert sayfadan_ats_bul('<a href="https://jobs.lever.co/trendyol">İlanlar</a>') == ("lever", "trendyol")
    assert sayfadan_ats_bul("https://analogdevices.wd1.myworkdayjobs.com/en-US/External") == (
        "workday",
        "analogdevices|wd1|External",
    )


def test_kariyer_baglantisi_dosya_ve_gizlilik_sayfalarini_almaz():
    html = (
        '<a href="/kariyer">Kariyer</a><a href="/gizlilik">Gizlilik</a>'
        '<a href="https://kariyer.tusas.com/storage/logo.png">x</a>'
    )
    assert kariyer_baglantilari("https://firma.com/", html) == ["https://firma.com/kariyer"]


def test_ana_sayfa_engelliyse_bile_yoklama_yapilir():
    firma = FirmaBilgisi(id=1, ad="Getir", web="https://getir.com")
    http = SahteHttp(jsonlar={"api.lever.co/v0/postings/getir": [lever_ilani("Istanbul, Turkey")]})  # sayfa yok
    assert firmayi_kesfet(http, firma, yokla=True) == ("lever", "getir", "", "tamam")
    assert firmayi_kesfet(http, firma, yokla=False)[3] == "erisilemedi"


def test_turkiye_ilani_olmayan_pano_baska_sirket_sayilir():
    firma = FirmaBilgisi(id=1, ad="Innova", web="https://innova.com.tr")
    http = SahteHttp(jsonlar={"api.lever.co/v0/postings/innova": [lever_ilani("Austin, TX")]})
    assert firmayi_kesfet(http, firma, yokla=True)[:2] == ("", "")


def test_kesif_bozuk_baglantida_cokmez_ve_bilineni_silmez(oturum):
    with oturum.begin() as o:
        depo.firma_ekle_veya_guncelle(o, "Bozuk", web="https://bozuk.com")
        depo.firma_ekle_veya_guncelle(o, "Kapalı", web="https://kapali.com", kariyer="https://kapali.com/ik")
        depo.firma_ekle_veya_guncelle(o, "Sağlam", web="https://saglam.com")
    http = SahteHttp(
        jsonlar={"api.lever.co/v0/postings/saglam": []},  # pano var (şu an ilansız) → doğrulama geçer
        sayfalar={
            "https://bozuk.com": '<a href="http://[getaquotelink]">x</a><a href="/kariyer">Kariyer</a>',
            "https://saglam.com": '<a href="/kariyer">Kariyer</a>',
            "https://saglam.com/kariyer": '<a href="https://jobs.lever.co/saglam">Açık pozisyonlar</a>',
        },
    )
    sayac = kesfet(ayarlari_oku(), oturum, http=http)
    assert sayac == {"kariyer_bulunan": 2, "erisilemedi": 1, "ats_bulunan": 1}
    with oturum() as o:
        firmalar = {f.ad: f for f in depo.aktif_firmalar(o)}
    assert firmalar["Bozuk"].kariyer == "https://bozuk.com/kariyer"
    assert firmalar["Kapalı"].kariyer == "https://kapali.com/ik"  # site cevap vermedi diye silinmedi
    assert (firmalar["Sağlam"].ats, firmalar["Sağlam"].slug) == ("lever", "saglam")


def test_sitede_bagli_ama_kapali_pano_kaydedilmez():
    firma = FirmaBilgisi(id=1, ad="Complizen", web="https://complizen.ai")
    http = SahteHttp(sayfalar={"https://complizen.ai": '<a href="https://complizen.breezy.hr">Kariyer</a>'})
    assert firmayi_kesfet(http, firma, yokla=False)[:2] == ("", "")  # breezy JSON 404 → pano yok sayılır
