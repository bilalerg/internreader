"""API uçtan uca: kayıt → onay → çıkış, ve kötüye kullanıma karşı önlemler (gerçek e-posta gönderilmez)."""

import dataclasses
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from internreader import depo
from internreader.api import HizSiniri, uygulama_olustur
from internreader.ayar import ayarlari_oku
from internreader.db import Abone
from internreader.eposta import Eposta


class SahteGonderici:
    def __init__(self):
        self.gidenler: list[Eposta] = []

    def gonder(self, eposta: Eposta) -> None:
        self.gidenler.append(eposta)

    def son_jeton(self) -> str:
        return self.gidenler[-1].metin.split("jeton=")[1].split()[0]


@pytest.fixture
def ortam(oturum):
    gonderici = SahteGonderici()
    ayar = dataclasses.replace(ayarlari_oku(), site_adresi="https://internreader.test", gizli_anahtar="test-anahtari")
    istemci = TestClient(uygulama_olustur(ayar, oturum, gonderici))
    return istemci, gonderici, oturum


KAYIT = {"eposta": "Ogrenci@Ornek.com", "sehirler": ["istanbul"], "alanlar": ["yazilim"], "kvkk_onay": True}


def test_kayit_onay_ve_cikis(ortam):
    istemci, gonderici, oturum = ortam
    assert istemci.post("/api/abone", json=KAYIT).status_code == 202
    assert len(gonderici.gidenler) == 1 and "https://internreader.test/onay?jeton=" in gonderici.gidenler[0].metin
    with oturum() as o:
        abone = depo.abone_eposta_ile(o, "ogrenci@ornek.com")  # küçük harfe çevrildi
        assert abone.durum == "bekliyor" and abone.tercihler["sehirler"] == ["istanbul"]
        assert abone.onay_jetonu_ozeti != gonderici.son_jeton()  # jetonun kendisi değil özeti saklanır

    jeton = gonderici.son_jeton()
    cevap = istemci.post("/api/abone/onay", json={"jeton": jeton}).json()
    assert cevap["durum"] == "onaylandi" and cevap["hos_geldin"] == "bos"  # ilan yok: dürüst hoş geldin e-postası
    assert istemci.post("/api/abone/onay", json={"jeton": jeton}).json()["hos_geldin"] == "zaten"  # ikinci tık
    with oturum() as o:
        abone_id = depo.abone_eposta_ile(o, "ogrenci@ornek.com").id

    from internreader.abonelik import iptal_jetonu

    assert istemci.post("/api/abone/iptal", json={"jeton": iptal_jetonu(abone_id, "test-anahtari")}).status_code == 200
    with oturum() as o:
        assert depo.abone_eposta_ile(o, "ogrenci@ornek.com") is None  # çıkınca e-posta silinir


def test_kayitli_adres_disari_sizmaz(ortam):
    istemci, gonderici, _ = ortam
    istemci.post("/api/abone", json=KAYIT)
    istemci.post("/api/abone/onay", json={"jeton": gonderici.son_jeton()})
    ikinci = istemci.post("/api/abone", json=KAYIT)
    assert (
        ikinci.status_code == 202
        and ikinci.json() == istemci.post("/api/abone", json={**KAYIT, "eposta": "yeni@x.com"}).json()
    )
    onay_epostalari = [e for e in gonderici.gidenler if "onayla" in e.konu]
    assert len(onay_epostalari) == 2  # zaten onaylı adrese yeni onay e-postası gitmez


def test_gecersiz_istekler(ortam):
    istemci, gonderici, _ = ortam
    cevap = istemci.post("/api/abone", json={**KAYIT, "kvkk_onay": False})
    assert cevap.status_code == 422 and cevap.json()["alanlar"] == ["kvkk_onay"]
    assert istemci.post("/api/abone", json={**KAYIT, "eposta": "eposta-degil"}).status_code == 422
    assert istemci.post("/api/abone", json={**KAYIT, "sehirler": ["paris"]}).status_code == 422
    assert istemci.post("/api/abone/onay", json={"jeton": "uydurma-jeton-123"}).status_code == 400
    assert istemci.post("/api/abone/iptal", json={"jeton": "1.sahteimzasahteimza"}).status_code == 400
    assert gonderici.gidenler == []


def test_bal_kupunu_dolduran_bot_kaydedilmez(ortam):
    istemci, gonderici, oturum = ortam
    cevap = istemci.post("/api/abone", json={**KAYIT, "web_sitesi": "http://spam.example"})
    assert cevap.status_code == 202 and gonderici.gidenler == []  # bot farkı anlamaz
    with oturum() as o:
        assert depo.abone_sayilari(o) == {}


def test_hiz_siniri(oturum):
    istemci = TestClient(uygulama_olustur(ayarlari_oku(), oturum, SahteGonderici(), kayit_siniri=HizSiniri(2, 60)))
    kodlar = [istemci.post("/api/abone", json={**KAYIT, "eposta": f"k{n}@x.com"}).status_code for n in range(3)]
    assert kodlar == [202, 202, 429]


def test_suresi_dolan_onay_gecersiz_ve_temizlenir(ortam):
    istemci, gonderici, oturum = ortam
    istemci.post("/api/abone", json=KAYIT)
    with oturum.begin() as o:
        abone = o.query(Abone).one()
        abone.onay_jetonu_tarihi = abone.onay_jetonu_tarihi - timedelta(hours=73)
    assert istemci.post("/api/abone/onay", json={"jeton": gonderici.son_jeton()}).status_code == 400

    from internreader.abonelik import suresi_dolanlari_temizle

    with oturum.begin() as o:
        assert suresi_dolanlari_temizle(o) == 1


def test_saglik_veritabanini_kontrol_eder(ortam):
    istemci, _, _ = ortam
    assert istemci.get("/api/saglik").json() == {"durum": "ok"}

    class BozukOturum:
        def __call__(self):
            raise OperationalError("SELECT 1", {}, Exception("bağlantı yok"))

    ayar = dataclasses.replace(ayarlari_oku(), gizli_anahtar="test-anahtari")
    bozuk = TestClient(uygulama_olustur(ayar, BozukOturum(), SahteGonderici()))
    assert bozuk.get("/api/saglik").status_code == 503


def test_gunluk_onay_siniri_kotayi_botlardan_korur(oturum):
    ayar = dataclasses.replace(
        ayarlari_oku(), site_adresi="https://internreader.test", gizli_anahtar="test-anahtari", gunluk_onay_siniri=2
    )
    gonderici = SahteGonderici()
    istemci = TestClient(uygulama_olustur(ayar, oturum, gonderici))
    for i in range(2):
        assert istemci.post("/api/abone", json={**KAYIT, "eposta": f"o{i}@ornek.com"}).status_code == 202
    cevap = istemci.post("/api/abone", json={**KAYIT, "eposta": "fazla@ornek.com"})
    assert cevap.status_code == 503 and cevap.json()["hata"] == "gunluk_sinir"
    assert len(gonderici.gidenler) == 2  # sınır dolunca e-posta gönderilmez
