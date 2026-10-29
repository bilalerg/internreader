"""Kişiye özel bülten: kategori kuralları (alan, çalışma modeli, girişim), API tercihleri ve uçtan uca tercih matrisi.

Matris testi gerçek akışı çalıştırır: firmalar + ilanlar + sınıflandırma + ayrıntı veritabanına yazılır, her tercih
için bir abone kaydolur, bülten gönderilir. Her abone YALNIZCA kendi tercihine uyan ilanları almalı; uyan ilanı
olmayan aboneye e-posta gitmemeli. Beklenen kümeler elle yazıldı (kuralı kendisiyle sınamamak için).
"""

import dataclasses
from typing import get_args

import pytest
from fastapi.testclient import TestClient

from internreader import depo
from internreader.abonelik import kayit_iste, onayla
from internreader.api import SEVIYELER, Alan, uygulama_olustur
from internreader.ayar import ayarlari_oku
from internreader.bulten import bultenleri_gonder
from internreader.isleme.kategori import ALANLAR, alanlari_bul, calisma_modeli, girisim_mi
from internreader.model import OGRENCI_SEVIYELERI, Ilan

AYAR = dataclasses.replace(ayarlari_oku(), site_adresi="https://internreader.test", gizli_anahtar="test-anahtari")


class SahteGonderici:
    def __init__(self):
        self.gidenler = []

    def gonder(self, eposta) -> None:
        self.gidenler.append(eposta)


# ---------------- kurallar ----------------
def test_alanlar_rol_yapay_zeka_firma_ve_basliktan():
    assert alanlari_bul("yazilim", "yok", "Backend Intern", "Acme", set()) == ["yazilim"]
    assert alanlari_bul("yazilim", "ozunde", "LLM Engineer Intern", "Acme", set()) == ["yazilim", "yapay_zeka"]
    assert alanlari_bul("yazilim", "arti", "Backend Intern", "Acme", set()) == ["yazilim"]  # AI artı: alan değil
    assert alanlari_bul("yazilim", "yok", "Software Engineer", "Dream Games", set()) == ["yazilim", "oyun"]
    assert alanlari_bul("yazilim", "yok", "Unity Developer Intern", "Acme", set()) == ["yazilim", "oyun"]
    assert alanlari_bul("yazilim", "yok", "Software Intern", "Aselsan", {"savunma"}) == ["yazilim", "savunma"]
    assert alanlari_bul("yazilim", "yok", "Cyber Security Intern", "Banka", set()) == ["yazilim", "savunma"]
    assert alanlari_bul("veri", "yok", "Veri Stajyeri", "Koyun Yazılım", set()) == ["veri"]  # "koyun" oyun değil


def test_calisma_modeli_once_konum_sonra_ayrinti():
    assert calisma_modeli("Türkiye, Remote", "ofis") == "uzaktan"
    assert calisma_modeli("Istanbul Headquarters Hybrid", "belirsiz") == "hibrit"
    assert calisma_modeli("Istanbul", "ofis") == "yerinde"
    assert calisma_modeli("Istanbul", "uzaktan") == "uzaktan"
    assert calisma_modeli("", None) == "belirsiz"


@pytest.mark.parametrize(
    "firma, etiket, kaynaklar, ilan_kaynagi, beklenen",
    [
        ("Valven", {"ai"}, {"turkiye.ai"}, "kariyer_sayfasi", True),  # yapay zekâ girişim haritası
        ("Aykan Teknoloji", {"teknopark"}, {"teknopark_istanbul"}, "kariyer_sayfasi", True),
        ("Nova Spark", set(), {"dijitalpark"}, "kariyer_sayfasi", True),
        ("Dream Games", {"ai"}, {"ats_genis"}, "lever", True),  # girişim ilan sistemi + ats_genis
        ("Uber", set(), {"ats_genis"}, "smartrecruiters", False),  # ats_genis tek başına yetmez
        ("Yapı Kredi", {"banka"}, {"ats_genis"}, "greenhouse", False),  # banka etiketi
        ("Aselsan", {"savunma", "teknopark"}, {"teknopark_istanbul"}, "kariyer_sayfasi", False),  # büyük kurum
        ("Sabancı Üniversitesi", {"teknopark"}, {"teknopark_istanbul"}, "kariyer_sayfasi", False),
        ("Kobi Ar-Ge", {"teknopark"}, {"teknopark_istanbul"}, "workday", False),  # kurumsal ilan sistemi
        ("ASPİLSAN Enerji", {"savunma"}, {"savunmakariyer"}, "kariyer_sayfasi", False),  # girişim listesinde değil
        ("Sezzle", {"ai"}, {"ai_listesi"}, "greenhouse", False),
        ("Elle Girişim", {"girisim"}, set(), "kariyer_sayfasi", True),  # elle işaret önce gelir
        ("Elle Kurum", {"kurumsal", "teknopark"}, {"turkiye.ai"}, "kariyer_sayfasi", False),
    ],
)
def test_girisim_kurali(firma, etiket, kaynaklar, ilan_kaynagi, beklenen):
    assert girisim_mi(firma, etiket, kaynaklar, ilan_kaynagi) is beklenen


def test_api_secenekleri_kurallarla_ayni():
    assert get_args(Alan) == ALANLAR
    assert set(SEVIYELER) == OGRENCI_SEVIYELERI


# ---------------- API ----------------
@pytest.fixture
def istemci(oturum):
    return TestClient(uygulama_olustur(AYAR, oturum, SahteGonderici()))


def test_yeni_tercihler_kaydedilir_ve_varsayilan_hepsi(istemci, oturum):
    temel = {"kvkk_onay": True}
    assert istemci.post("/api/abone", json={**temel, "eposta": "eski@x.com"}).status_code == 202
    yeni = {"alanlar": ["savunma", "oyun", "oyun"], "calisma_modelleri": ["uzaktan"], "sadece_girisim": True}
    assert istemci.post("/api/abone", json={**temel, "eposta": "yeni@x.com", **yeni}).status_code == 202
    with oturum() as o:
        eski = depo.abone_eposta_ile(o, "eski@x.com").tercihler
        assert set(eski["alanlar"]) == set(ALANLAR) and eski["calisma_modelleri"] == [] and not eski["sadece_girisim"]
        t = depo.abone_eposta_ile(o, "yeni@x.com").tercihler
        assert t["alanlar"] == ["oyun", "savunma"] and t["calisma_modelleri"] == ["uzaktan"] and t["sadece_girisim"]


@pytest.mark.parametrize(
    "hatali", [{"alanlar": ["oyunn"]}, {"calisma_modelleri": ["ofis"]}, {"alanlar": []}, {"sadece_girisim": "belki"}]
)
def test_gecersiz_tercih_reddedilir(istemci, hatali):
    cevap = istemci.post("/api/abone", json={"eposta": "a@x.com", "kvkk_onay": True, **hatali})
    assert cevap.status_code == 422 and set(cevap.json()["alanlar"]) & set(hatali)


# ---------------- uçtan uca matris ----------------
# kod: (başlık, firma, firma etiketi, firmanın listeleri, ilan sistemi, konum, rol, seviye, yapay_zeka, ayrıntı modeli)
ILANLAR = {
    "A1": ("Yapay Zeka Stajyeri", "Valven", ["ai"], "turkiye.ai", "kariyer_sayfasi", "Istanbul", "yapay_zeka",
           "staj", "ozunde", "hibrit"),
    "A2": ("Veri Analisti Stajyeri", "Yapı Kredi", ["banka", "fintech"], "ats_genis,tohum_1810", "kariyer_sayfasi",
           "Istanbul", "veri", "staj", "yok", "ofis"),
    "A3": ("Oyun Geliştirici Stajyeri", "Agave Games", [], "ats_genis", "ashby", "Istanbul", "yazilim", "staj", "yok",
           None),
    "A4": ("Gömülü Yazılım Stajyeri", "Aselsan", ["savunma"], "savunmakariyer,teknopark_istanbul", "kariyer_sayfasi",
           "Ankara", "yazilim", "staj", "yok", "ofis"),
    "A5": ("Junior Backend Developer", "Sezzle", ["ai"], "ai_listesi", "greenhouse", "Türkiye, Remote", "yazilim",
           "junior", "yok", None),
    "A6": ("Siber Güvenlik Stajyeri", "Aykan Teknoloji", ["teknopark"], "teknopark_istanbul", "kariyer_sayfasi", "",
           "yazilim", "staj", "yok", None),
    "A7": ("LLM Backend Stajyeri", "Nova Spark", [], "dijitalpark", "kariyer_sayfasi", "Izmir", "yazilim", "staj",
           "ozunde", "uzaktan"),
}  # fmt: skip
HEPSI = set(ILANLAR)

# abone adı: (tercihler, alması gereken ilanlar). Eksik anahtar = hepsi (eski aboneler böyle kayıtlı).
MATRIS = {
    "ai": ({"alanlar": ["yapay_zeka"]}, {"A1", "A7"}),
    "veri": ({"alanlar": ["veri"]}, {"A2"}),
    "oyun": ({"alanlar": ["oyun"]}, {"A3"}),
    "savunma": ({"alanlar": ["savunma"]}, {"A4", "A6"}),
    "yazilim": ({"alanlar": ["yazilim"]}, {"A3", "A4", "A5", "A6", "A7"}),
    "uzaktan": ({"calisma_modelleri": ["uzaktan"]}, {"A5", "A7"}),
    "hibrit": ({"calisma_modelleri": ["hibrit"]}, {"A1"}),
    "yerinde": ({"calisma_modelleri": ["yerinde"]}, {"A2", "A4"}),
    "girisim": ({"sadece_girisim": True}, {"A1", "A3", "A6", "A7"}),
    "junior": ({"seviyeler": ["junior"]}, {"A5"}),
    "ankara": ({"sehirler": ["ankara"]}, {"A4", "A5", "A6", "A7"}),  # + uzaktan + konum belirtilmemiş
    "izmir": ({"sehirler": ["izmir"]}, {"A5", "A6", "A7"}),
    "ai_girisim_uzaktan": (
        {"alanlar": ["yapay_zeka"], "sadece_girisim": True, "calisma_modelleri": ["uzaktan"]},
        {"A7"},
    ),
    "savunma_yerinde_ankara": (
        {"alanlar": ["savunma"], "calisma_modelleri": ["yerinde"], "sehirler": ["ankara"]},
        {"A4"},
    ),
    "eski_hepsi": ({"alanlar": ["yazilim", "yapay_zeka", "veri"], "seviyeler": sorted(OGRENCI_SEVIYELERI)}, HEPSI),
    "eski_uzaktan_sehri": ({"sehirler": ["uzaktan"]}, {"A5", "A6", "A7"}),
    "eslesen_yok": ({"alanlar": ["oyun"], "calisma_modelleri": ["uzaktan"]}, set()),
}


def _veriyi_kur(oturum) -> dict[str, str]:
    """İlanları kaydeder; kod → başlık döndürür."""
    with oturum.begin() as o:
        for kod, (baslik, firma, etiket, kaynaklar, sistem, konum, rol, seviye, yz, model) in ILANLAR.items():
            for kaynak in kaynaklar.split(","):
                depo.firma_ekle_veya_guncelle(o, firma, etiket=etiket, kaynak=kaynak)
            i = Ilan(firma=firma, baslik=baslik, url=f"https://ilan.test/{kod}", kaynak=sistem, konum=konum)
            depo.ilanlari_kaydet(o, [i], set())
            depo.siniflandirma_kaydet(o, {i.kimlik: {"seviye": seviye, "rol": rol, "yapay_zeka": yz}}, "test")
            if model:
                depo.ayrinti_kaydet(o, i.kimlik, {"ozet": "Kısa özet.", "calisma_modeli": model}, "ozet", "test")
    return {kod: v[0] for kod, v in ILANLAR.items()}


def _aboneleri_kur(oturum) -> None:
    with oturum.begin() as o:
        for ad, (tercihler, _) in MATRIS.items():
            onayla(o, kayit_iste(o, f"{ad}@x.com", tercihler, "gunluk", "test"))


def _alinanlar(gidenler, basliklar: dict[str, str]) -> dict[str, set[str]]:
    return {e.alici.split("@")[0]: {k for k, b in basliklar.items() if b in e.metin} for e in gidenler}


def test_ilan_kategorileri_depodan_gelir(oturum):
    basliklar = _veriyi_kur(oturum)
    with oturum() as o:
        ilanlar = {i["baslik"]: i for i in depo.yayinlanacak_ilanlar(o)}
    a = {kod: ilanlar[b] for kod, b in basliklar.items()}
    assert a["A3"]["alanlar"] == ["yazilim", "oyun"] and a["A3"]["girisim"]
    assert a["A4"]["alanlar"] == ["yazilim", "savunma"] and not a["A4"]["girisim"]
    assert a["A6"]["alanlar"] == ["yazilim", "savunma"]  # firma etiketi değil, başlık: "Siber"
    assert a["A7"]["alanlar"] == ["yazilim", "yapay_zeka"] and a["A7"]["calisma_modeli"] == "uzaktan"
    assert a["A5"]["calisma_modeli"] == "uzaktan" and a["A2"]["calisma_modeli"] == "yerinde"
    assert a["A3"]["calisma_modeli"] == "belirsiz" and a["A1"]["calisma_modeli"] == "hibrit"


def test_her_abone_yalnizca_tercihine_uyan_ilanlari_alir(oturum):
    basliklar = _veriyi_kur(oturum)
    _aboneleri_kur(oturum)
    g = SahteGonderici()
    rapor = bultenleri_gonder(oturum, g, AYAR)

    alinan = _alinanlar(g.gidenler, basliklar)
    beklenen = {ad: ilanlar for ad, (_, ilanlar) in MATRIS.items() if ilanlar}
    assert alinan == beklenen  # fazla ilan da eksik ilan da yok
    assert "eslesen_yok" not in alinan  # uyan ilan yoksa e-posta gitmez
    assert rapor["gonderilen"] == len(beklenen) and rapor["bos"] == 1 and rapor["hata"] == 0
    assert len({e.alici for e in g.gidenler}) == len(g.gidenler)  # kimseye iki e-posta yok


def test_matriste_gunluk_sinir_ve_adil_sira_bozulmaz(oturum):
    basliklar = _veriyi_kur(oturum)
    _aboneleri_kur(oturum)
    sinir = 5
    sinirli = dataclasses.replace(AYAR, gunluk_bulten_siniri=sinir)
    ilk = SahteGonderici()
    rapor = bultenleri_gonder(oturum, ilk, sinirli)
    assert rapor["gonderilen"] == sinir and rapor["ertelendi"] > 0
    ikinci = SahteGonderici()
    bultenleri_gonder(oturum, ikinci, sinirli)  # ertesi gün: dün alamayanlar önce
    assert {e.alici for e in ikinci.gidenler}.isdisjoint({e.alici for e in ilk.gidenler})

    birlesik = _alinanlar(ilk.gidenler, basliklar) | _alinanlar(ikinci.gidenler, basliklar)
    for ad, ilanlar in birlesik.items():
        assert ilanlar == MATRIS[ad][1]  # sınır yüzünden bekleyen abone de yalnızca kendi ilanlarını alır
