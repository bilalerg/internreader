"""Ayrıntı çıkarıcı: uydurma denetimi ve boru hattında kayıt (sahte ağ + sahte yapay zekâ)."""

import json
from datetime import date

from internreader import boru, depo
from internreader.ayar import ayarlari_oku
from internreader.model import Ilan
from internreader.yz.ayrinti_cikarici import IlanAyrintisi, denetle, kisalt
from tests.conftest import SahteHttp, SahteYz

BUGUN = date(2026, 10, 19)
METIN = "Python ve SQL bilen, 3. ve 4. sınıf öğrencileri arıyoruz. Hibrit çalışma. Son başvuru 15 Kasım 2026."


def test_denetim_metinde_gecmeyen_teknolojiyi_ve_sacma_tarihi_atar():
    ham = IlanAyrintisi(
        ozet="Veri ekibinde staj.",
        son_basvuru="2019-01-01",  # geçmiş tarih → atılır
        hedef="3. ve 4. sınıf öğrencileri",
        calisma_modeli="hibrit",
        ucretli="belirsiz",
        teknolojiler=["Python", "SQL", "Kubernetes"],  # Kubernetes metinde yok → atılır
    )
    sonuc = denetle(ham, METIN, BUGUN)
    assert sonuc["teknolojiler"] == ["Python", "SQL"] and sonuc["son_basvuru"] is None
    assert denetle(ham.model_copy(update={"son_basvuru": "2026-11-15"}), METIN, BUGUN)["son_basvuru"] == "2026-11-15"


def test_ayrinti_cikarilip_kaydedilir_ve_yayina_girer(oturum, tmp_path):
    i = Ilan(firma="F", baslik="Data Intern", url="https://jobs.lever.co/f/1", kaynak="lever", aciklama=METIN)
    with oturum.begin() as o:
        depo.ilanlari_kaydet(o, [i], set())
        depo.siniflandirma_kaydet(o, {i.kimlik: {"seviye": "staj", "rol": "veri", "yapay_zeka": "yok"}}, "m")

    def cevap(tur, mesaj):
        assert tur is IlanAyrintisi and "Bugünün tarihi" in mesaj
        return IlanAyrintisi(
            ozet="Veri ekibinde staj.",
            son_basvuru="2026-11-15",
            hedef="3. ve 4. sınıf öğrencileri",
            calisma_modeli="hibrit",
            ucretli="belirsiz",
            teknolojiler=["Python", "SQL"],
        )

    yz = SahteYz(cevap)
    rapor = boru.ayrintilari_zenginlestir(ayarlari_oku(), oturum, http=SahteHttp(), yz=yz)
    assert rapor["cikarilan"] == 1 and len(yz.cagrilar) == 1
    # ikinci çalıştırma: ayrıntısı olan ilan tekrar gönderilmez
    assert boru.ayrintilari_zenginlestir(ayarlari_oku(), oturum, http=SahteHttp(), yz=SahteYz(cevap))["bekleyen"] == 0
    boru.yayinla(oturum, cikti_dizini=tmp_path)
    ilan = json.loads((tmp_path / "ilanlar.json").read_text(encoding="utf-8"))["ilanlar"][0]
    assert ilan["ayrinti"]["teknolojiler"] == ["Python", "SQL"] and ilan["ayrinti"]["son_basvuru"] == "2026-11-15"


def test_kisaltma_kelime_ortasindan_kesmez():
    assert (
        kisalt("Bilgisayar Mühendisliği veya benzeri bölümlerden mezun yeni", 40)
        == "Bilgisayar Mühendisliği veya benzeri…"
    )
    assert kisalt("  kısa   metin ", 40) == "kısa metin"
    assert len(kisalt("a " * 200, 120)) <= 120
