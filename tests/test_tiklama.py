"""Tıklama ölçümü uçtan uca: e-posta → imzalı bağlantı → kayıt → ilana yönlendirme → rapor. Veritabanı kapalıyken bile öğrenci
ilana ulaşır, kayıtta kişisel veri yoktur, güvenlik tarayıcıları rapora girmez, jeton kurcalanamaz."""

import base64
import dataclasses
import json
import re
from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from internreader import abonelik, depo
from internreader.api import HizSiniri, uygulama_olustur
from internreader.ayar import ayarlari_oku
from internreader.bakim import bakim_yap
from internreader.bulten import bultenleri_gonder, hos_geldin_gonder
from internreader.bulten.gonderim import deneme_gonder
from internreader.bulten.tiklama import baglanti_yapici, hafta_etiketi, jeton_coz, jeton_olustur, kisi_kodu
from internreader.db import Tiklama, simdi
from internreader.eposta import Eposta
from internreader.model import Ilan

KOK = Path(__file__).resolve().parents[1]
AYAR = dataclasses.replace(ayarlari_oku(), site_adresi="https://internreader.test", gizli_anahtar="test-anahtari")
TARAYICI = {"user-agent": "Mozilla/5.0 (Windows NT 10.0) Chrome/130"}
SITE = "https://internreader.test"


class SahteGonderici:
    def __init__(self):
        self.gidenler: list[Eposta] = []

    def gonder(self, eposta: Eposta) -> None:
        self.gidenler.append(eposta)


class KapaliVeritabani:
    def begin(self):
        raise OperationalError("SELECT 1", {}, Exception("veritabanı kapalı"))


def ilan_kur(oturum, no: int = 1, firma: str = "Acme") -> Ilan:
    i = Ilan(
        firma=firma,
        baslik=f"Yazılım Stajı {no}",
        url=f"https://isler.test/{firma}/{no}",
        kaynak="lever",
        konum="Istanbul",
    )
    with oturum.begin() as o:
        depo.ilanlari_kaydet(o, [i], set())
        depo.siniflandirma_kaydet(o, {i.kimlik: {"seviye": "staj", "rol": "yazilim", "yapay_zeka": "yok"}}, "test")
    return i


def abone_kur(oturum, eposta: str = "ogrenci@ornek.com") -> int:
    with oturum.begin() as o:
        jeton = abonelik.kayit_iste(o, eposta, {}, "gunluk", "site")
    with oturum.begin() as o:
        return abonelik.onayla(o, jeton).abone_id


def istemci(oturum, sinir: HizSiniri | None = None) -> TestClient:
    return TestClient(uygulama_olustur(AYAR, oturum, SahteGonderici(), tik_siniri=sinir or HizSiniri(1000, 600)))


def baglantilar(eposta: Eposta) -> list[str]:
    return [b.removeprefix(SITE) for b in re.findall(rf'href="({SITE}/api/t/[^"]+)"', eposta.html)]


def bulten_gonder(oturum, an=None) -> Eposta:
    """Dakikalar önce gönderilmiş gibi: anında açılan bağlantı "şüpheli" sayılır."""
    gonderici = SahteGonderici()
    bultenleri_gonder(oturum, gonderici, AYAR, an or simdi() - timedelta(minutes=10))
    return gonderici.gidenler[0]


def tiklamalar(oturum) -> list[Tiklama]:
    with oturum() as o:
        return list(o.query(Tiklama).all())


def rapor(oturum) -> dict:
    with oturum() as o:
        return depo.tiklama_raporu(o, simdi())


def test_bulten_baglantisi_kaydedilir_ve_ilana_yonlenir(oturum):
    i = ilan_kur(oturum)
    abone_kur(oturum)
    eposta = bulten_gonder(oturum)
    adres = baglantilar(eposta)[0]
    assert i.url not in adres  # adres okunaklı durmuyor ama imzalı; "Başvur" bize gelir

    cevap = istemci(oturum).get(adres, headers=TARAYICI, follow_redirects=False)
    assert cevap.status_code == 302 and cevap.headers["location"] == i.url
    assert cevap.headers["cache-control"] == "no-store"
    satir = tiklamalar(oturum)[0]
    assert (satir.ilan_kimlik, satir.tur, satir.supheli) == (i.kimlik, "bulten", False)
    r = rapor(oturum)
    assert (r["gonderilen_eposta"], r["tiklanan_eposta"], r["tiklama"], r["tiklama_orani"]) == (1, 1, 1, 1.0)
    assert r["en_cok"] == [{"firma": "Acme", "baslik": i.baslik, "tiklama": 1}]


def test_duz_metin_dogrudan_ilana_gider(oturum):
    i = ilan_kur(oturum)
    abone_kur(oturum)
    assert f"Başvur: {i.url}" in bulten_gonder(oturum).metin


def test_kurcalanmis_jeton_siteye_gider_kaydedilmez(oturum):
    i = ilan_kur(oturum)
    abone_kur(oturum)
    adres = baglantilar(bulten_gonder(oturum))[0]
    jeton = adres.removeprefix("/api/t/")
    govde, imza = jeton.rsplit(".", 1)
    veri = json.loads(base64.urlsafe_b64decode(govde + "=" * (-len(govde) % 4)))
    assert veri["u"] == i.url
    sahte = base64.urlsafe_b64encode(json.dumps({**veri, "u": "https://kotu.test"}).encode()).decode().rstrip("=")

    c = istemci(oturum)
    for bozuk in (f"{sahte}.{imza}", f"{govde}.{'0' * 32}", "cop", "a.b"):
        cevap = c.get(f"/api/t/{bozuk}", headers=TARAYICI, follow_redirects=False)
        assert cevap.status_code == 302 and cevap.headers["location"] == AYAR.site_adresi
    assert tiklamalar(oturum) == []
    # Doğru imzayla bile http(s) dışı adres kabul edilmez
    assert jeton_coz(jeton_olustur({"u": "javascript:alert(1)"}, AYAR.gizli_anahtar), AYAR.gizli_anahtar) is None


def test_baska_anahtarla_imzalanan_jeton_reddedilir():
    jeton = jeton_olustur({"u": "https://a.test"}, "eski-anahtar")
    assert jeton_coz(jeton, "yeni-anahtar") is None and jeton_coz(jeton, "eski-anahtar") == {"u": "https://a.test"}


def test_ayni_baglanti_bir_kez_sayilir(oturum):
    ilan_kur(oturum)
    abone_kur(oturum)
    adres = baglantilar(bulten_gonder(oturum))[0]
    c = istemci(oturum)
    for _ in range(3):
        assert c.get(adres, headers=TARAYICI, follow_redirects=False).status_code == 302
    assert len(tiklamalar(oturum)) == 1


def test_tarayici_ve_ani_acilis_supheli_head_kaydedilmez(oturum):
    i = ilan_kur(oturum)
    abone_kur(oturum)
    c = istemci(oturum)
    adres = baglantilar(bulten_gonder(oturum))[0]

    cevap = c.head(adres, headers=TARAYICI, follow_redirects=False)
    assert cevap.status_code == 302 and cevap.headers["location"] == i.url
    assert tiklamalar(oturum) == []

    for tarayici in ("Mozilla/5.0 (compatible; SafeLinks)", "python-requests/2.32", ""):
        c.get(adres, headers={"user-agent": tarayici}, follow_redirects=False)
    assert [s.supheli for s in tiklamalar(oturum)] == [True]
    # Tarayıcının açtığı bağlantıya sonra öğrenci de tıklarsa tıklaması kaybolmaz
    c.get(adres, headers=TARAYICI, follow_redirects=False)
    r = rapor(oturum)
    assert (r["tiklama"], r["elenen_supheli"]) == (1, 1)


def test_anlik_acilis_supheli(oturum):
    ilan_kur(oturum)
    abone_kur(oturum)
    adres = baglantilar(bulten_gonder(oturum, an=simdi()))[0]
    istemci(oturum).get(adres, headers=TARAYICI, follow_redirects=False)
    assert tiklamalar(oturum)[0].supheli is True


def test_toplu_acilis_raporda_elenir_tek_tek_acilis_sayilir(oturum):
    for n in range(4):
        ilan_kur(oturum, n, firma=f"F{n}")
    abone_kur(oturum)
    adresler = baglantilar(bulten_gonder(oturum))
    assert len(adresler) == 4
    c = istemci(oturum)
    for adres in adresler[:3]:  # art arda, saniyeler içinde
        c.get(adres, headers=TARAYICI, follow_redirects=False)
    r = rapor(oturum)
    assert (r["tiklama"], r["elenen_supheli"], r["tiklanan_eposta"]) == (0, 3, 0)
    with oturum.begin() as o:
        for n, s in enumerate(o.query(Tiklama).order_by(Tiklama.id).all()):
            s.tarih = simdi() - timedelta(minutes=n * 3)  # aynı üç tıklama dakikalar arayla olsaydı
    r = rapor(oturum)
    assert (r["tiklama"], r["elenen_supheli"], r["tiklanan_eposta"]) == (3, 0, 1)


def test_veritabani_kapaliyken_ogrenci_ilana_ulasir(oturum):
    i = ilan_kur(oturum)
    abone_kur(oturum)
    adres = baglantilar(bulten_gonder(oturum))[0]
    cevap = istemci(KapaliVeritabani()).get(adres, headers=TARAYICI, follow_redirects=False)
    assert cevap.status_code == 302 and cevap.headers["location"] == i.url


def test_hiz_siniri_asilinca_yonlenir_kaydetmez(oturum):
    i = ilan_kur(oturum)
    abone_kur(oturum)
    adres = baglantilar(bulten_gonder(oturum))[0]
    cevap = istemci(oturum, HizSiniri(0, 600)).get(adres, headers=TARAYICI, follow_redirects=False)
    assert cevap.headers["location"] == i.url and tiklamalar(oturum) == []


def test_kayitta_ve_adreste_kisisel_veri_yok_abone_silinince_kayit_kalir(oturum):
    ilan_kur(oturum)
    abone_id = abone_kur(oturum, "gizli.kisi@ornek.com")
    adres = baglantilar(bulten_gonder(oturum))[0]
    veri = jeton_coz(adres.removeprefix("/api/t/"), AYAR.gizli_anahtar)
    assert "gizli.kisi" not in json.dumps(veri) and abone_id not in veri.values()
    istemci(oturum).get(adres, headers=TARAYICI, follow_redirects=False)
    satir = tiklamalar(oturum)[0]
    alanlar = {k: getattr(satir, k) for k in Tiklama.__table__.columns.keys()}
    assert set(alanlar) == {"id", "tarih", "ilan_kimlik", "eposta_no", "kisi", "hafta", "tur", "supheli"}
    assert "gizli.kisi" not in str(alanlar)
    with oturum.begin() as o:
        assert abonelik.iptal_et(o, abonelik.iptal_jetonu(abone_id, AYAR.gizli_anahtar), AYAR.gizli_anahtar)
    assert len(tiklamalar(oturum)) == 1


def test_kisi_kodu_her_hafta_degisir_ayni_hafta_ayni():
    an = simdi()
    bu, sonraki = hafta_etiketi(an), hafta_etiketi(an + timedelta(days=7))
    assert bu != sonraki
    assert kisi_kodu(7, bu, "a") == kisi_kodu(7, bu, "a")
    assert kisi_kodu(7, bu, "a") != kisi_kodu(7, sonraki, "a")
    assert kisi_kodu(7, bu, "a") != kisi_kodu(8, bu, "a")


def test_rapor_kisileri_ve_orani_dogru_sayar(oturum):
    ilan_kur(oturum, 1, "A")
    ilan_kur(oturum, 2, "B")
    abone_kur(oturum, "a@ornek.com")
    abone_kur(oturum, "b@ornek.com")
    abone_kur(oturum, "c@ornek.com")
    gonderici = SahteGonderici()
    bultenleri_gonder(oturum, gonderici, AYAR, simdi() - timedelta(minutes=10))
    assert len(gonderici.gidenler) == 3
    c = istemci(oturum)
    for adres in baglantilar(gonderici.gidenler[0]):  # 1. kişi iki ilana
        c.get(adres, headers=TARAYICI, follow_redirects=False)
    c.get(baglantilar(gonderici.gidenler[1])[0], headers=TARAYICI, follow_redirects=False)  # 2. kişi bir ilana
    r = rapor(oturum)
    assert (r["gonderilen_eposta"], r["tiklanan_eposta"], r["tiklama_orani"], r["tiklama"]) == (3, 2, 0.667, 3)
    assert list(r["haftalik_tekil_kisi"].values()) == [2]


def test_hos_geldin_olculur_deneme_rapora_girmez(oturum, tmp_path):
    ilan_kur(oturum)
    abone_id = abone_kur(oturum)
    gonderici = SahteGonderici()
    hos_geldin_gonder(oturum, gonderici, AYAR, abone_id, simdi() - timedelta(minutes=10))
    deneme = SahteGonderici()
    deneme_gonder(oturum, deneme, AYAR, "deneme@ornek.com", klasor=tmp_path, an=simdi() - timedelta(minutes=10))
    c = istemci(oturum)
    c.get(baglantilar(gonderici.gidenler[0])[0], headers=TARAYICI, follow_redirects=False)
    c.get(baglantilar(deneme.gidenler[0])[0], headers=TARAYICI, follow_redirects=False)
    assert {s.tur for s in tiklamalar(oturum)} == {"hos_geldin", "deneme"}
    r = rapor(oturum)
    assert (r["tiklama"], r["deneme"], r["gonderilen_eposta"]) == (1, 1, 1)


def test_baglanti_olmayan_ilan_yoksa_bos_rapor(oturum):
    r = rapor(oturum)
    assert (r["gonderilen_eposta"], r["tiklama_orani"], r["en_cok"]) == (0, None, [])


def test_kaldirilan_ilan_raporu_bozmaz(oturum):
    with oturum.begin() as o:
        depo.tiklama_kaydet(o, "yok", "e1", "k1", "2026-W44", "bulten", False, simdi())
    assert rapor(oturum)["en_cok"] == [{"tiklama": 1}]


def test_bakim_eski_tiklamayi_siler(oturum):
    with oturum.begin() as o:
        depo.tiklama_kaydet(o, "eski", "e1", "k1", "2026-W10", "bulten", False, simdi() - timedelta(days=181))
        depo.tiklama_kaydet(o, "yeni", "e2", "k1", "2026-W44", "bulten", False, simdi() - timedelta(days=10))
    assert bakim_yap(oturum)["eski_tiklama"] == 1
    assert [s.ilan_kimlik for s in tiklamalar(oturum)] == ["yeni"]


def test_baglanti_yapici_ayni_epostada_ayni_numara():
    an = simdi()
    yap = baglanti_yapici(AYAR, 1, "bulten", an)
    a = jeton_coz(yap({"kimlik": "a", "url": "https://x.test/a"}).rsplit("/", 1)[1], AYAR.gizli_anahtar)
    b = jeton_coz(yap({"kimlik": "b", "url": "https://x.test/b"}).rsplit("/", 1)[1], AYAR.gizli_anahtar)
    assert a["e"] == b["e"] and a["i"] == "a" and b["u"] == "https://x.test/b"
    baska = jeton_coz(
        baglanti_yapici(AYAR, 1, "bulten", an)({"kimlik": "a", "url": "https://x.test/a"}).rsplit("/", 1)[1],
        AYAR.gizli_anahtar,
    )
    assert baska["e"] != a["e"]


def test_kvkk_metni_tiklamayi_anlatir():
    metin = (KOK / "web/src/pages/kvkk.astro").read_text(encoding="utf-8")
    assert "tıkladığın" in metin and "180 gün" in metin
    assert abonelik.KVKK_SURUMU == "2026-10-30"
