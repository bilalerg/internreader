"""Hoş geldin e-postası uçtan uca: form → onay → e-posta → kayıt → ertesi sabah tekrar yok; çift tıklama, SMTP hatası,
boş eşleşme, e-posta bütçesi. Gerçek e-posta gönderilmez, ağa çıkılmaz."""

import dataclasses
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from internreader import depo
from internreader.api import HizSiniri, uygulama_olustur
from internreader.ayar import GELISTIRME_ANAHTARI, ayarlari_oku
from internreader.bulten import bultenleri_gonder
from internreader.bulten.secim import yakin_ilanlar
from internreader.db import Bulten, Gonderim, simdi
from internreader.eposta import Eposta
from internreader.model import Ilan

AYAR = dataclasses.replace(ayarlari_oku(), site_adresi="https://internreader.test", gizli_anahtar="test-anahtari")
SECENEKLER = {"kvkk_onay": True}


class SahteGonderici:
    def __init__(self, hatali_konu: str | None = None):
        self.gidenler: list[Eposta] = []
        self.hatali_konu = hatali_konu

    def gonder(self, eposta: Eposta) -> None:
        if self.hatali_konu and self.hatali_konu in eposta.konu:
            raise OSError("550 gönderilemedi")
        self.gidenler.append(eposta)

    @property
    def hos_geldinler(self) -> list[Eposta]:
        return [e for e in self.gidenler if "onayla" not in e.konu]

    def son_jeton(self) -> str:
        onay = [e for e in self.gidenler if "onayla" in e.konu][-1]
        return onay.metin.split("jeton=")[1].split()[0]


def ilan_ekle(
    oturum, url, baslik, firma="Acme", konum="Istanbul", rol="yazilim", yayin="", ayrinti=None, kaynak="lever"
):
    i = Ilan(firma=firma, baslik=baslik, url=url, kaynak=kaynak, konum=konum, tarih=yayin)
    with oturum.begin() as o:
        depo.ilanlari_kaydet(o, [i], set())
        depo.siniflandirma_kaydet(o, {i.kimlik: {"seviye": "staj", "rol": rol, "yapay_zeka": "yok"}}, "test")
        if ayrinti is not None:
            depo.ayrinti_kaydet(o, i.kimlik, {"ozet": "Özet.", **ayrinti}, "ozet", "test")
    return i.kimlik


def istemci_kur(oturum, gonderici, ayar=AYAR):
    genis = HizSiniri(azami=1000, pencere_sn=600)
    return TestClient(uygulama_olustur(ayar, oturum, gonderici, kayit_siniri=genis, jeton_siniri=genis))


def kaydol_onayla(istemci, gonderici, eposta="ogrenci@x.com", **tercihler):
    assert istemci.post("/api/abone", json={"eposta": eposta, **SECENEKLER, **tercihler}).status_code == 202
    return istemci.post("/api/abone/onay", json={"jeton": gonderici.son_jeton()})


def test_onaylayinca_uyan_guncel_ilanlar_hemen_gider_ve_ertesi_sabah_tekrarlanmaz(oturum):
    ilan_ekle(oturum, "https://j.test/yeni", "Yazılım Stajı", yayin=simdi().date().isoformat())
    # 100 günlük ATS ilanı: "yeni" değil (sabah bültenine girmez) ama güncel, hoş geldine girer
    eski = (simdi() - timedelta(days=100)).date().isoformat()
    ilan_ekle(oturum, "https://j.test/eski", "Eski Ama Açık Staj", firma="Beta", yayin=eski)
    # Bayat ilan (kariyer sayfası, 2023 tarihli) girmez
    ilan_ekle(
        oturum,
        "https://j.test/bayat",
        "Bayat Staj",
        firma="Gama",
        kaynak="kariyer_sayfasi",
        konum="",
        ayrinti={"ilan_tarihi": "2023-05-08"},
    )
    g = SahteGonderici()
    cevap = kaydol_onayla(istemci_kur(oturum, g), g)
    assert cevap.status_code == 200
    assert cevap.json() == {"durum": "onaylandi", "hos_geldin": "gonderildi", "siklik": "gunluk"}

    (e,) = g.hos_geldinler
    assert e.alici == "ogrenci@x.com" and e.konu == "Şu an sana uygun 2 ilan"
    assert "Yazılım Stajı" in e.metin and "Eski Ama Açık Staj" in e.metin and "Bayat Staj" not in e.metin
    assert "Şu an sana uygun" in e.html and "Aboneliğin başladı" in e.metin
    assert "List-Unsubscribe" in e.basliklar

    with oturum() as o:
        abone = depo.abone_eposta_ile(o, "ogrenci@x.com")
        assert abone.durum == "onayli" and abone.son_bulten is not None
        assert o.query(Gonderim).count() == 2
        assert [b.durum for b in o.query(Bulten)] == ["hos_geldin"]

    # Aynı Türkiye gününde sabah bülteni ikinci kez gitmez (son_bulten kaydı)
    assert bultenleri_gonder(oturum, SahteGonderici(), AYAR)["hazir_abone"] == 0
    # Ertesi gün: gönderilen ilanlar tekrar gitmez; yeni ilan varsa yalnızca o gider
    yarin = simdi() + timedelta(days=1)
    assert bultenleri_gonder(oturum, SahteGonderici(), AYAR, yarin)["gonderilen"] == 0
    ilan_ekle(oturum, "https://j.test/ertesi", "Ertesi Gün Stajı", firma="Delta")
    sabah = SahteGonderici()
    assert bultenleri_gonder(oturum, sabah, AYAR, yarin)["gonderilen"] == 1
    metin = sabah.gidenler[0].metin
    assert "Ertesi Gün Stajı" in metin and "Yazılım Stajı" not in metin


def test_cift_tiklama_ikinci_eposta_gondermez(oturum):
    ilan_ekle(oturum, "https://j.test/1", "Yazılım Stajı")
    g = SahteGonderici()
    istemci = istemci_kur(oturum, g)
    assert kaydol_onayla(istemci, g).json()["hos_geldin"] == "gonderildi"
    ikinci = istemci.post("/api/abone/onay", json={"jeton": g.son_jeton()})
    assert ikinci.status_code == 200 and ikinci.json()["hos_geldin"] == "zaten"
    assert len(g.hos_geldinler) == 1


def test_onay_atomik_yalnizca_bir_tiklama_yeni_sayilir(oturum):
    with oturum.begin() as o:
        abone = depo.abone_ekle(o, "a@x.com")
        o.flush()
        abone_id = abone.id
    an = simdi()
    with oturum.begin() as o:
        assert depo.aboneyi_onayla(o, abone_id, an) is True
    with oturum.begin() as o:
        assert depo.aboneyi_onayla(o, abone_id, an) is False


def test_eposta_gonderilemezse_onay_yine_basarili_ve_sabah_bulten_kapatir(oturum):
    ilan_ekle(oturum, "https://j.test/1", "Yazılım Stajı")
    g = SahteGonderici(hatali_konu="Şu an sana uygun")
    cevap = kaydol_onayla(istemci_kur(oturum, g), g)
    assert cevap.status_code == 200 and cevap.json()["hos_geldin"] == "hata"
    assert g.hos_geldinler == []
    with oturum() as o:
        abone = depo.abone_eposta_ile(o, "ogrenci@x.com")
        assert abone.durum == "onayli" and abone.son_bulten is None
        assert o.query(Gonderim).count() == 0
        assert [b.durum for b in o.query(Bulten)] == ["hata"]
    sabah = SahteGonderici()
    assert bultenleri_gonder(oturum, sabah, AYAR)["gonderilen"] == 1  # aynı gün de kapatır: e-posta hiç gitmedi
    assert "Yazılım Stajı" in sabah.gidenler[0].metin


def test_beklenmeyen_hata_da_onayi_bozmaz(oturum, monkeypatch):
    ilan_ekle(oturum, "https://j.test/1", "Yazılım Stajı")

    def bozuk(*_, **__):
        raise RuntimeError("beklenmeyen")

    monkeypatch.setattr(depo, "yayinlanacak_ilanlar", bozuk)
    g = SahteGonderici()
    cevap = kaydol_onayla(istemci_kur(oturum, g), g)
    assert cevap.status_code == 200 and cevap.json()["hos_geldin"] == "hata"
    with oturum() as o:
        assert depo.abone_eposta_ile(o, "ogrenci@x.com").durum == "onayli"


def test_tam_uyan_yoksa_durust_eposta_ve_yakin_ilanlar(oturum):
    ilan_ekle(oturum, "https://j.test/1", "Yazılım Stajı", konum="Ankara")
    ilan_ekle(oturum, "https://j.test/2", "Veri Stajı", firma="Beta", konum="Ankara", rol="veri")
    g = SahteGonderici()
    cevap = kaydol_onayla(istemci_kur(oturum, g), g, alanlar=["yazilim"], sehirler=["izmir"])
    assert cevap.json()["hos_geldin"] == "yakin"
    (e,) = g.hos_geldinler
    assert e.konu == "Şu an seçimlerine tam uyan ilan yok"
    assert "çıkınca ilk sen öğreneceksin" in e.metin and "Yakın ilanlar" in e.metin
    assert "Yakın ilanlar" in e.html
    # Önce şehir gevşer, alan korunur: yazılım seçene veri ilanı gösterilmez
    assert "Yazılım Stajı" in e.metin and "Veri Stajı" not in e.metin
    with oturum() as o:
        assert depo.abone_eposta_ile(o, "ogrenci@x.com").son_bulten is None  # yakın ilan bülten sayılmaz
    # Tam uyan ilan çıkınca ilk sabah gider (aynı gün bile)
    ilan_ekle(oturum, "https://j.test/3", "İzmir Stajı", firma="Delta", konum="Izmir")
    sabah = SahteGonderici()
    assert bultenleri_gonder(oturum, sabah, AYAR)["gonderilen"] == 1
    assert "İzmir Stajı" in sabah.gidenler[0].metin


def test_hic_ilan_yoksa_liste_olmadan_durust_eposta(oturum):
    g = SahteGonderici()
    cevap = kaydol_onayla(istemci_kur(oturum, g), g)
    assert cevap.json()["hos_geldin"] == "bos"
    (e,) = g.hos_geldinler
    assert e.konu == "Şu an seçimlerine tam uyan ilan yok" and "Başvur" not in e.metin and "Yakın ilanlar" not in e.html


def test_yakin_ilanlar_gevsetme_sirasi():
    ilanlar = [
        {
            "kimlik": "a",
            "firma": "A",
            "rol": "yazilim",
            "seviye": "staj",
            "sehirler": ["ankara"],
            "calisma_modeli": "hibrit",
        },
        {
            "kimlik": "b",
            "firma": "B",
            "rol": "veri",
            "seviye": "junior",
            "sehirler": ["izmir"],
            "calisma_modeli": "uzaktan",
        },
    ]
    tercih = {"alanlar": ["yazilim"], "seviyeler": ["staj"], "sehirler": ["bursa"], "calisma_modelleri": ["uzaktan"]}
    assert [i["kimlik"] for i in yakin_ilanlar(ilanlar, tercih)] == ["a"]  # alan ve seviye korunarak bulundu
    assert [i["kimlik"] for i in yakin_ilanlar(ilanlar, {"alanlar": ["oyun"]})] == ["a", "b"]  # son çare alan
    assert yakin_ilanlar([], tercih) == []
    assert yakin_ilanlar(ilanlar, {}) == []  # gevşetilecek tercih yok


def test_butce_dolunca_hos_geldin_atlanir_sabah_bulten_kapatir(oturum):
    ilan_ekle(oturum, "https://j.test/1", "Yazılım Stajı")
    g = SahteGonderici()
    istemci = istemci_kur(oturum, g, dataclasses.replace(AYAR, gunluk_hos_geldin_siniri=1))
    assert kaydol_onayla(istemci, g, "a@x.com").json()["hos_geldin"] == "gonderildi"
    cevap = kaydol_onayla(istemci, g, "b@x.com")
    assert cevap.status_code == 200 and cevap.json()["hos_geldin"] == "atlandi"
    assert [e.alici for e in g.hos_geldinler] == ["a@x.com"]
    sabah = SahteGonderici()
    bultenleri_gonder(oturum, sabah, AYAR)
    assert [e.alici for e in sabah.gidenler] == ["b@x.com"]  # atlanan abone aynı sabah kapatılır


def test_varsayilan_eposta_butcesi_brevo_kotasina_sigar(monkeypatch):
    for ad in (
        "INTERNREADER_GUNLUK_BULTEN_SINIRI",
        "INTERNREADER_GUNLUK_ONAY_SINIRI",
        "INTERNREADER_GUNLUK_HOS_GELDIN_SINIRI",
    ):
        monkeypatch.delenv(ad, raising=False)
    a = ayarlari_oku()
    assert (a.gunluk_bulten_siniri, a.gunluk_onay_siniri, a.gunluk_hos_geldin_siniri) == (200, 50, 50)
    monkeypatch.setenv("INTERNREADER_GUNLUK_HOS_GELDIN_SINIRI", "7")
    assert ayarlari_oku().gunluk_hos_geldin_siniri == 7


def test_haftalik_abone_pazartesi_mantigi_bozulmaz(oturum):
    ilan_ekle(oturum, "https://j.test/1", "Yazılım Stajı")
    g = SahteGonderici()
    cevap = kaydol_onayla(istemci_kur(oturum, g), g, siklik="haftalik")
    assert cevap.json() == {"durum": "onaylandi", "hos_geldin": "gonderildi", "siklik": "haftalik"}
    assert "her pazartesi sabahı" in g.hos_geldinler[0].metin
    # Pazartesi olmayan gün hazır değil; sonraki pazartesi yalnızca yeni ilan
    bugun = simdi()
    gun = (0 - bugun.weekday()) % 7 or 7
    pazartesi = (bugun + timedelta(days=gun)).replace(hour=4, minute=30)
    sali = pazartesi + timedelta(days=1)
    assert bultenleri_gonder(oturum, SahteGonderici(), AYAR, sali)["hazir_abone"] == 0
    assert bultenleri_gonder(oturum, SahteGonderici(), AYAR, pazartesi)["gonderilen"] == 0  # yeni ilan yok
    ilan_ekle(oturum, "https://j.test/2", "Yeni Staj", firma="Beta")
    sonraki = SahteGonderici()
    assert bultenleri_gonder(oturum, sonraki, AYAR, pazartesi + timedelta(days=7))["gonderilen"] == 1
    assert "Yeni Staj" in sonraki.gidenler[0].metin and "Yazılım Stajı" not in sonraki.gidenler[0].metin


def test_firma_kotasi_ve_azami_ilan_bultenle_ayni(oturum):
    for n in range(4):
        ilan_ekle(oturum, f"https://j.test/a{n}", f"A Stajı {n}", firma="Acme")
    for n in range(20):
        ilan_ekle(oturum, f"https://j.test/b{n}", f"Staj {n}", firma=f"Firma {n}")
    g = SahteGonderici()
    kaydol_onayla(istemci_kur(oturum, g), g)
    (e,) = g.hos_geldinler
    assert e.konu == "Şu an sana uygun 15 ilan"
    assert sum(f"A Stajı {n}" in e.metin for n in range(4)) <= 2


def test_gelistirme_anahtariyla_gercek_smtp_gondermez(oturum):
    ilan_ekle(oturum, "https://j.test/1", "Yazılım Stajı")
    ayar = dataclasses.replace(AYAR, smtp_sunucu="smtp.ornek.com", gizli_anahtar=GELISTIRME_ANAHTARI)
    g = SahteGonderici()
    cevap = kaydol_onayla(istemci_kur(oturum, g, ayar), g)
    assert cevap.status_code == 200 and cevap.json()["hos_geldin"] == "atlandi" and g.hos_geldinler == []


@pytest.mark.parametrize("gecersiz", ["yanlis-jeton-degeri"])
def test_gecersiz_jeton_hos_geldin_gondermez(oturum, gecersiz):
    g = SahteGonderici()
    assert istemci_kur(oturum, g).post("/api/abone/onay", json={"jeton": gecersiz}).status_code == 400
    assert g.gidenler == []


def test_onay_suresi_dolduysa_hos_geldin_yok(oturum):
    ilan_ekle(oturum, "https://j.test/1", "Yazılım Stajı")
    g = SahteGonderici()
    istemci = istemci_kur(oturum, g)
    istemci.post("/api/abone", json={"eposta": "a@x.com", **SECENEKLER})
    with oturum.begin() as o:
        depo.abone_eposta_ile(o, "a@x.com").onay_jetonu_tarihi = simdi() - timedelta(hours=80)
    assert istemci.post("/api/abone/onay", json={"jeton": g.son_jeton()}).status_code == 400
    assert g.hos_geldinler == []


def test_turkiye_gunu_koruma_ile_uyumlu(oturum):
    # Gece 23:30 TR onay → ertesi sabah bülten engellenmez (yeni Türkiye günü), gönderilenler tekrar gitmez
    ilan_ekle(oturum, "https://j.test/1", "Yazılım Stajı")
    g = SahteGonderici()
    kaydol_onayla(istemci_kur(oturum, g), g)
    with oturum.begin() as o:
        depo.abone_eposta_ile(o, "ogrenci@x.com").son_bulten = datetime.fromisoformat("2026-11-03T20:30:00+00:00")
    ilan_ekle(oturum, "https://j.test/2", "Sabah Stajı", firma="Beta")
    sabah = SahteGonderici()
    an = datetime.fromisoformat("2026-11-04T04:30:00+00:00")  # 07:30 TR, ertesi gün
    assert bultenleri_gonder(oturum, sabah, AYAR, an)["gonderilen"] == 1
    assert "Sabah Stajı" in sabah.gidenler[0].metin and "Yazılım Stajı" not in sabah.gidenler[0].metin
