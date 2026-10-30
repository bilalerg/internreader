"""Günlük e-posta kotası: bütün e-postalar tek sayaçtan düşer, kaydolmak isteyen kapıda kalmaz, aynı gün iki çalışma kotayı
aşmaz, kota doluyken adres sızmaz. Sınıf ve yurt ağından çok kişi kaydolabilir; aynı adrese art arda e-posta attırılamaz."""

import dataclasses
import re
from collections import Counter
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from internreader import abonelik, depo
from internreader.api import HizSiniri, uygulama_olustur
from internreader.ayar import ayarlari_oku
from internreader.bulten import bultenleri_gonder, hos_geldin_gonder
from internreader.db import Abone, simdi
from internreader.eposta import Eposta
from internreader.model import Ilan

AYAR = dataclasses.replace(ayarlari_oku(), site_adresi="https://internreader.test", gizli_anahtar="test-anahtari")
SABAH = datetime(2026, 11, 3, 4, 30, tzinfo=UTC)


class SahteGonderici:
    def __init__(self, hatali: bool = False):
        self.gidenler: list[Eposta] = []
        self.hatali = hatali

    def gonder(self, eposta: Eposta) -> None:
        if self.hatali:
            raise OSError("421 geçici hata")
        self.gidenler.append(eposta)


def istemci_kur(oturum, gonderici, ayar=AYAR, **sinirlar):
    return TestClient(uygulama_olustur(ayar, oturum, gonderici, **sinirlar))


def genis_istemci(oturum, gonderici, ayar=AYAR):
    genis = HizSiniri(azami=10_000, pencere_sn=600)
    return istemci_kur(oturum, gonderici, ayar, kayit_siniri=genis, jeton_siniri=genis)


def kayit(n, **ek) -> dict:
    return {"eposta": f"o{n}@ornek.com", "kvkk_onay": True, **ek}


def ilan_ekle(oturum, no: int = 1) -> None:
    i = Ilan(firma=f"F{no}", baslik=f"Yazılım Stajı {no}", url=f"https://j.test/{no}", kaynak="lever", konum="Istanbul")
    with oturum.begin() as o:
        depo.ilanlari_kaydet(o, [i], set())
        depo.siniflandirma_kaydet(o, {i.kimlik: {"seviye": "staj", "rol": "yazilim", "yapay_zeka": "yok"}}, "test")


def aboneler_ekle(oturum, adet: int) -> None:
    with oturum.begin() as o:
        for n in range(adet):
            abonelik.kayit_iste(o, f"a{n}@ornek.com", {}, "gunluk", "test")
            depo.abone_eposta_ile(o, f"a{n}@ornek.com").durum = "onayli"


def kullanilan(oturum, an=SABAH) -> int:
    with oturum() as o:
        return depo.eposta_sayisi(o, an)


def test_sayac_azamide_durur_iade_ve_sinirsiz(oturum):
    with oturum.begin() as o:
        assert [depo.eposta_kotasi_ayir(o, SABAH, 2) for _ in range(3)] == [True, True, False]
    assert kullanilan(oturum) == 2
    with oturum.begin() as o:
        depo.eposta_kotasi_iade(o, SABAH)
        assert depo.eposta_kotasi_ayir(o, SABAH, 2) is True
        assert depo.eposta_kotasi_ayir(o, SABAH, 0) is True  # 0 = sınırsız ama yine de sayılır
    assert kullanilan(oturum) == 3


def test_iade_sifirin_altina_inmez(oturum):
    with oturum.begin() as o:
        depo.eposta_kotasi_iade(o, SABAH)
        depo.eposta_kotasi_ayir(o, SABAH, 5)
        depo.eposta_kotasi_iade(o, SABAH)
        depo.eposta_kotasi_iade(o, SABAH)
    assert kullanilan(oturum) == 0


def test_gun_turkiye_saatine_gore_doner(oturum):
    gece_yarisi_oncesi = datetime(2026, 11, 3, 20, 30, tzinfo=UTC)  # Türkiye: 23:30
    gece_yarisi_sonrasi = datetime(2026, 11, 3, 21, 30, tzinfo=UTC)  # Türkiye: ertesi gün 00:30
    with oturum.begin() as o:
        assert depo.eposta_kotasi_ayir(o, gece_yarisi_oncesi, 1) is True
        assert depo.eposta_kotasi_ayir(o, gece_yarisi_oncesi, 1) is False
        assert depo.eposta_kotasi_ayir(o, gece_yarisi_sonrasi, 1) is True


def test_iki_yuz_kisi_ayni_anda_kaydolur_kimse_onaylamasa_da(oturum):
    g = SahteGonderici()
    c = genis_istemci(oturum, g)
    assert {c.post("/api/abone", json=kayit(n)).status_code for n in range(200)} == {202}
    assert len(g.gidenler) == 200 and kullanilan(oturum, simdi()) == 200


def test_iki_yuz_kisi_hemen_onaylasa_da_hepsi_kaydolur_kota_asilmaz(oturum):
    ilan_ekle(oturum)
    g = SahteGonderici()
    c = genis_istemci(oturum, g)
    sonuc = Counter()
    for n in range(200):
        assert c.post("/api/abone", json=kayit(n)).status_code == 202
        jeton = re.search(r"onay\?jeton=([^\s\"&]+)", g.gidenler[-1].metin).group(1)
        sonuc[c.post("/api/abone/onay", json={"jeton": jeton}).json()["hos_geldin"]] += 1
    assert sonuc == {"gonderildi": 75, "atlandi": 125}
    assert len(g.gidenler) == 275 and kullanilan(oturum, simdi()) == 275


def test_sinif_agindan_otuz_kisi_kaydolur_sonrasi_sinirlanir(oturum):
    c = istemci_kur(oturum, SahteGonderici())  # varsayılan hız sınırı
    assert {c.post("/api/abone", json=kayit(n)).status_code for n in range(30)} == {202}
    assert c.post("/api/abone", json=kayit(99)).status_code == 429


def test_kota_dolunca_kayitli_ve_kayitsiz_adres_ayni_cevabi_alir(oturum):
    ayar = dataclasses.replace(AYAR, gunluk_eposta_siniri=1)
    g = SahteGonderici()
    c = genis_istemci(oturum, g, ayar)
    assert c.post("/api/abone", json=kayit(1)).status_code == 202
    kayitli, yeni = c.post("/api/abone", json=kayit(1)), c.post("/api/abone", json=kayit(2))
    assert kayitli.status_code == yeni.status_code == 503
    assert kayitli.json() == yeni.json() and len(g.gidenler) == 1


def test_ayni_adrese_on_dakikada_tek_onay_tercih_yine_guncellenir(oturum):
    g = SahteGonderici()
    c = genis_istemci(oturum, g)
    assert c.post("/api/abone", json=kayit(1)).status_code == 202
    assert c.post("/api/abone", json=kayit(1, siklik="haftalik")).status_code == 202
    assert len(g.gidenler) == 1 and kullanilan(oturum, simdi()) == 1  # ikinci istek kota harcamadı
    with oturum.begin() as o:
        abone = o.query(Abone).filter_by(eposta="o1@ornek.com").one()
        assert abone.siklik == "haftalik"
        abone.onay_jetonu_tarihi = simdi() - timedelta(minutes=11)
    assert c.post("/api/abone", json=kayit(1)).status_code == 202
    assert len(g.gidenler) == 2  # süre geçince yeniden gönderilir


def test_onay_gonderilemezse_yer_geri_verilir_hemen_yeniden_denenir(oturum):
    bozuk, saglam = SahteGonderici(hatali=True), SahteGonderici()
    assert genis_istemci(oturum, bozuk).post("/api/abone", json=kayit(1)).status_code == 503
    assert kullanilan(oturum, simdi()) == 0
    assert genis_istemci(oturum, saglam).post("/api/abone", json=kayit(1)).status_code == 202
    assert len(saglam.gidenler) == 1


def test_ayni_gun_iki_calisma_kotayi_asmaz_ertesi_gun_kalanlar_alir(oturum):
    ilan_ekle(oturum)
    aboneler_ekle(oturum, 15)
    ayar = dataclasses.replace(AYAR, gunluk_eposta_siniri=10, onay_payi=0)
    bir, iki, uc = SahteGonderici(), SahteGonderici(), SahteGonderici()
    assert bultenleri_gonder(oturum, bir, ayar, SABAH)["gonderilen"] == 10
    rapor = bultenleri_gonder(oturum, iki, ayar, SABAH + timedelta(hours=2))
    assert rapor["gonderilen"] == 0 and rapor["ertelendi"] == 5
    assert bultenleri_gonder(oturum, uc, ayar, SABAH + timedelta(days=1))["gonderilen"] == 5
    assert {e.alici for e in uc.gidenler}.isdisjoint({e.alici for e in bir.gidenler})


def test_bulten_onay_payina_dokunamaz_kayit_yine_calisir(oturum):
    ilan_ekle(oturum)
    aboneler_ekle(oturum, 8)
    ayar = dataclasses.replace(AYAR, gunluk_eposta_siniri=5, onay_payi=2)
    an = simdi()
    assert bultenleri_gonder(oturum, SahteGonderici(), ayar, an)["gonderilen"] == 3
    g = SahteGonderici()
    c = genis_istemci(oturum, g, ayar)
    assert [c.post("/api/abone", json=kayit(n)).status_code for n in range(3)] == [202, 202, 503]
    assert len(g.gidenler) == 2 and kullanilan(oturum, an) == 5


def test_hos_geldin_kotaya_sayilir_gonderilemezse_geri_verilir(oturum):
    ilan_ekle(oturum)
    aboneler_ekle(oturum, 2)
    with oturum() as o:
        kimlikler = [o.query(Abone).filter_by(eposta=f"a{n}@ornek.com").one().id for n in range(2)]
    ayar = dataclasses.replace(AYAR, gunluk_eposta_siniri=1, onay_payi=0)
    assert hos_geldin_gonder(oturum, SahteGonderici(hatali=True), ayar, kimlikler[0], SABAH) == "hata"
    assert kullanilan(oturum) == 0
    assert hos_geldin_gonder(oturum, SahteGonderici(), ayar, kimlikler[0], SABAH) == "gonderildi"
    assert hos_geldin_gonder(oturum, SahteGonderici(), ayar, kimlikler[1], SABAH) == "atlandi"
    assert kullanilan(oturum) == 1


def test_smtp_hatasi_kotayi_tuketmez(oturum):
    ilan_ekle(oturum)
    aboneler_ekle(oturum, 3)
    rapor = bultenleri_gonder(oturum, SahteGonderici(hatali=True), AYAR, SABAH)
    assert rapor["hata"] == 3 and kullanilan(oturum) == 0
