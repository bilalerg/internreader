from internreader.model import Ilan
from internreader.yz.istemci import ButceAsildi
from internreader.yz.siniflandirici import (
    IlanSinifi,
    TopluSiniflandirma,
    aciklama_ozeti,
    siniflandir,
    siniflandirma_imzasi,
)
from tests.conftest import SahteYz


def ilanlar(n):
    return [Ilan(firma="F", baslik=f"İlan {i}", url=f"https://u/{i}", kaynak="lever") for i in range(n)]


def test_numaralar_kimliklere_eslenir_ve_toplu_gonderilir():
    def cevap(tur, mesaj):
        satir_sayisi = mesaj.count("\n") + 1
        return TopluSiniflandirma(
            sonuclar=[
                IlanSinifi(no=i, seviye="staj", rol="yazilim", yapay_zeka="yok", gerekce="test")
                for i in range(satir_sayisi)
            ]
        )

    yz = SahteYz(cevap)
    liste = ilanlar(65)
    sonuc = siniflandir(yz, liste, is_parcacigi=1)
    assert len(sonuc) == 65 and set(sonuc) == {i.kimlik for i in liste}
    assert len(yz.cagrilar) == 3  # 30 + 30 + 5 → 3 istek, 65 değil


def test_butce_biterse_cokmeden_eksik_sonucla_doner():
    def cevap(tur, mesaj):
        raise ButceAsildi("tavan")

    assert siniflandir(SahteYz(cevap), ilanlar(5), is_parcacigi=1) == {}


def test_aciklama_ozeti_seviye_cumlelerini_secer():
    aciklama = (
        "We are a fast-growing fintech changing how people pay. Our office is in Istanbul. " * 10
        + "Requirements: 3+ years of experience with Go. Nice to have: Kubernetes."
    )
    ozet = aciklama_ozeti(aciklama)
    assert "3+ years of experience" in ozet and "fintech" not in ozet and len(ozet) <= 400


def test_aciklama_ozeti_ipucu_yoksa_basini_alir():
    assert aciklama_ozeti("Kısa bir tanıtım.\nBaşka bir satır.") == "Kısa bir tanıtım. Başka bir satır."


def test_imza_adres_degil_icerik_uzerinden():
    a = Ilan(firma="Dream Games", baslik="Software Engineer (New Grad)", url="https://x/1", kaynak="workday")
    b = Ilan(firma="Dream Games", baslik="Software Engineer  (new grad)", url="https://x/2", kaynak="workday")
    c = Ilan(firma="Dream Games", baslik="Senior Software Engineer", url="https://x/1", kaynak="workday")
    assert siniflandirma_imzasi(a) == siniflandirma_imzasi(b) != siniflandirma_imzasi(c)
