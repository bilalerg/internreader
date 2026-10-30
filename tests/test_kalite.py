"""İlk gerçek bültenin elle denetiminden çıkan düzeltmeler (30.10.2026): ilan metninde menü, ilan türü, metne göre rol,
savunma ve girişim etiketi, sıralama ve firma kotası, görünen ad, sabah işini tetikleyen Vercel Cron ucu."""

import dataclasses
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
import requests
from fastapi.testclient import TestClient

from internreader import boru, depo
from internreader.abonelik import kayit_iste, onayla
from internreader.api import is_akisini_tetikle, uygulama_olustur
from internreader.ayar import ayarlari_oku
from internreader.bulten import bultenleri_gonder
from internreader.bulten.secim import bulten_sec
from internreader.db import oturum_fabrikasi
from internreader.ice_aktar import firma_listesini_esitle
from internreader.isleme.guncellik import siralama_anahtari
from internreader.isleme.kategori import ilan_turu_bul, seviye_etiketi
from internreader.kaynaklar.kariyer_sayfasi import ilan_metni
from internreader.model import Ilan
from internreader.yayin import gorunen_ad, seviye_yazisi, zenginlestir
from internreader.yz.ayrinti_cikarici import METIN_SINIRI, IlanAyrintisi
from tests.conftest import SahteHttp, SahteYz

KOK = Path(__file__).resolve().parents[1]
AYAR = dataclasses.replace(ayarlari_oku(), site_adresi="https://internreader.test", gizli_anahtar="test-anahtari")
MENU = "<nav><ul>" + "<li><a href='/x'>Ürünlerimiz ve Hizmetlerimiz</a></li>" * 400 + "</ul></nav>"


def ayrinti(**alanlar) -> IlanAyrintisi:
    temel = {"ozet": "Özet.", "calisma_modeli": "belirsiz", "ucretli": "belirsiz", "teknolojiler": []}
    return IlanAyrintisi(**(temel | alanlar))


# ---------------- ilan metni: menü modele gitmez ----------------
def test_yeditek_gibi_uzun_menude_tarih_sinirin_icinde_kalir():
    ham = (
        f"<html><head><title>Yeditek</title></head><body><header>{MENU}</header>"
        "<h1>Proje Stajı Programı</h1><div>Proje Stajı Programı 08 Mayıs 2023 Kendine güvenen 4. sınıf öğrencileri.</div>"
        "<footer>Tüm hakları saklıdır</footer></body></html>"
    )
    metin = ilan_metni(ham, "Proje Stajı Programı")
    assert "08 Mayıs 2023" in metin[:METIN_SINIRI]
    assert "Ürünlerimiz" not in metin and "Tüm hakları" not in metin and "Yeditek" not in metin


def test_main_oncelikli_ve_icindeki_aside_kalir():
    govde = "İş tanımı. " * 30
    ham = (
        f"{MENU}<main><nav>Geri dön</nav><h1>Stajyer</h1>{govde}"
        "<aside>Application Deadline November 30, 2026</aside></main><footer>Alt bilgi</footer>"
    )
    metin = ilan_metni(ham, "Stajyer")
    assert "November 30, 2026" in metin and "Geri dön" not in metin and "Ürünlerimiz" not in metin


def test_kisa_main_gercek_icerik_sayilmaz_baslik_penceresi_kullanilir():
    # Anlamsal etiket yok (Sestek): menü metni div içinde; başlığın son geçtiği yerden başlanır
    icerik = "We are looking for students who know Angular. " * 10
    ham = (
        "<main>Yükleniyor</main><div>Products Solutions Web Internship Company Resources</div>"
        f"<h1>Web Internship</h1><div>{icerik}</div>"
    )
    metin = ilan_metni(ham, "Web Internship")
    assert metin.startswith("Products Solutions Web Internship") is False or "Angular" in metin
    assert "Angular" in metin and "Company Resources" in metin[:120]  # başlıktan önceki 120 karakter tarih için kalır


def test_baslik_bulunamazsa_iskeletsiz_metnin_tamami():
    assert ilan_metni("<nav>Menü</nav><div>Python stajı</div>", "Başka Başlık") == "Python stajı"


# ---------------- ilan türü ve kart etiketi ----------------
def test_ilan_turu_once_kural_sonra_model():
    assert ilan_turu_bul("Midas Coders League", "Kodlama yarışması.") == "yarisma"
    assert ilan_turu_bul("Commencis Cloud Camp 2027", "6 haftalık eğitim.") == "egitim"
    hitit = "Job Posting New Talent Job Details Haven't found any suitable opening? Send us your CV."
    assert ilan_turu_bul("New Talent", hitit) == "genel_basvuru"
    assert ilan_turu_bul("Genel Başvuru", "") == "genel_basvuru"
    # Gerçek ilanın altındaki "aradığını bulamadın mı?" kutusu ilanı CV havuzu yapmaz
    gercek = "Yazılım stajyeri arıyoruz. " * 40 + "Haven't found a suitable position? Send us your CV."
    assert ilan_turu_bul("Yazılım Stajyeri", gercek) == "is"
    assert ilan_turu_bul("Yazılım Akademisi", "Eğitim veriyoruz.", "egitim") == "egitim"  # kural yoksa model
    assert ilan_turu_bul("Kampüs Elçisi", "", "is") == "is"  # "kampüs" kamp değil


def test_kart_etiketi_durust_siniflandirma_degismez():
    assert seviye_etiketi("staj", "Commencis Cloud Camp", "egitim") == "Eğitim programı"
    assert seviye_etiketi("yeni_mezun", "Midas Coders League", "yarisma") == "Yarışma"
    assert seviye_etiketi("junior", "Mobile Engineer (Turkey, All Levels)") == "Tüm seviyeler"
    assert seviye_etiketi("junior", "Junior Developer") == "Junior"
    assert seviye_yazisi({"seviye": "staj"}) == "Staj"  # eski JSON/sözlük


# ---------------- metne göre rol, tür ve yayından düşme ----------------
def ilan_kur(oturum, url, baslik, firma="Acme", kaynak="kariyer_sayfasi", rol="yazilim", yayin=""):
    i = Ilan(firma=firma, baslik=baslik, url=url, kaynak=kaynak, tarih=yayin)
    with oturum.begin() as o:
        depo.ilanlari_kaydet(o, [i], set())
        depo.siniflandirma_kaydet(o, {i.kimlik: {"seviye": "staj", "rol": rol, "yapay_zeka": "yok"}}, "test")
    return i


def test_metin_satis_ya_da_erp_diyorsa_ilan_yayindan_duser(oturum):
    # Başlıktan yazılım gibi duran ilan (Türk SEM, Mavvo): çıkarıcı metni görünce rolü düzeltir
    ilan_kur(oturum, "https://a.test/hotel", "Hotel WD Staj")
    ilan_kur(oturum, "https://a.test/erp", "ERP ve Raporlama Stajyeri")
    ilan_kur(oturum, "https://a.test/goruntu", "Proje Stajı")
    ilan_kur(oturum, "https://a.test/web", "Web Stajı")
    sayfalar = {
        "https://a.test/hotel": "<p>Otel sahiplerine paneli tanıtıp kurulum yapacaksın.</p>",
        "https://a.test/erp": "<p>ERP danışmanlığı, raporlama ve Excel.</p>",
        "https://a.test/goruntu": "<p>Görüntü işleme projeleri.</p>",
        "https://a.test/web": "<p>Angular ile web geliştirme.</p>",
    }

    def cevap(_, mesaj):
        if "Otel sahiplerine" in mesaj:
            return ayrinti(rol="teknik_degil")
        if "ERP danışmanlığı" in mesaj:
            return ayrinti(rol="diger_teknik")
        if "Görüntü işleme" in mesaj:
            return ayrinti(rol="yapay_zeka")
        return ayrinti(rol="yazilim")

    rapor = boru.ayrintilari_zenginlestir(AYAR, oturum, http=SahteHttp(sayfalar=sayfalar), yz=SahteYz(cevap))
    assert rapor["rol_degisen"] == 3
    with oturum() as o:
        ilanlar = {i["baslik"]: i for i in depo.yayinlanacak_ilanlar(o)}
    assert set(ilanlar) == {"Proje Stajı", "Web Stajı"}
    assert ilanlar["Proje Stajı"]["rol"] == "yapay_zeka" and ilanlar["Proje Stajı"]["yapay_zeka"] == "ozunde"
    assert "yapay_zeka" in ilanlar["Proje Stajı"]["alanlar"]


def test_metin_rolu_anlatmiyorsa_karar_degismez(oturum):
    ilan_kur(oturum, "https://a.test/x", "Yazılım Stajı")
    http = SahteHttp(sayfalar={"https://a.test/x": "<p>Başvuru formu.</p>"})
    rapor = boru.ayrintilari_zenginlestir(AYAR, oturum, http=http, yz=SahteYz(lambda *_: ayrinti(rol=None)))
    assert rapor["rol_degisen"] == 0
    with oturum() as o:
        assert depo.yayinlanacak_ilanlar(o)[0]["rol"] == "yazilim"


def test_genel_cv_sayfasi_duser_egitim_ve_yarisma_kendi_etiketiyle_kalir(oturum):
    ilan_kur(oturum, "https://a.test/cv", "New Talent")
    ilan_kur(oturum, "https://a.test/kamp", "Cloud Camp 2027")
    ilan_kur(oturum, "https://a.test/lig", "Coders League")
    sayfalar = {
        "https://a.test/cv": "<p>Haven't found any suitable opening? Send us your CV.</p>",
        "https://a.test/kamp": "<p>6 haftalık ücretsiz eğitim.</p>",
        "https://a.test/lig": "<p>Kodlama yarışması.</p>",
    }
    # Model eğitim ve yarışmaya "diger_teknik" dese de rol düzeltilmez (canlıda Cloud Camp böyle düşmüştü)
    yz = SahteYz(lambda *_: ayrinti(rol="diger_teknik"))
    boru.ayrintilari_zenginlestir(AYAR, oturum, http=SahteHttp(sayfalar=sayfalar), yz=yz)
    with oturum() as o:
        ilanlar = {i["baslik"]: i for i in depo.yayinlanacak_ilanlar(o)}
        nedenler = {i["baslik"]: i["bayat"] for i in depo.yayinlanacak_ilanlar(o, bayatlar_dahil=True)}
    assert nedenler["New Talent"] == "genel_basvuru" and "New Talent" not in ilanlar
    assert ilanlar["Cloud Camp 2027"]["seviye_etiketi"] == "Eğitim programı"
    assert ilanlar["Coders League"]["seviye_etiketi"] == "Yarışma"


def test_savunma_listesinden_gelmek_yetmez_metin_kaniti_gerekir(oturum):
    with oturum.begin() as o:
        depo.firma_ekle_veya_guncelle(o, "Mavvo", etiket=["savunma"], kaynak="savunmakariyer")
        depo.firma_ekle_veya_guncelle(o, "Kobi Savunma", etiket=["savunma"], kaynak="savunmakariyer")
    ilan_kur(oturum, "https://a.test/m", "Yazılım Stajı", firma="Mavvo")
    ilan_kur(oturum, "https://a.test/k", "Gömülü Yazılım Stajı", firma="Kobi Savunma")
    sayfalar = {
        "https://a.test/m": "<p>ERP yazılımı geliştiriyoruz.</p>",
        "https://a.test/k": "<p>İnsansız hava aracı yazılımı geliştiriyoruz.</p>",
    }
    boru.ayrintilari_zenginlestir(AYAR, oturum, http=SahteHttp(sayfalar=sayfalar), yz=SahteYz(lambda *_: ayrinti()))
    with oturum() as o:
        ilanlar = {i["firma"]: i for i in depo.yayinlanacak_ilanlar(o)}
    assert ilanlar["Mavvo"]["alanlar"] == ["yazilim"]
    assert ilanlar["Kobi Savunma"]["alanlar"] == ["yazilim", "savunma"]


def test_bugun_calisti_mi_komutu(monkeypatch, tmp_path, capsys):
    from internreader.__main__ import _turkiye_gunu, main

    url = f"sqlite:///{(tmp_path / 'komut.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    assert main(["bugun-calisti-mi"]) == 0
    assert capsys.readouterr().out.strip() == "false"
    fabrika = oturum_fabrikasi(url)
    with fabrika.begin() as o:
        depo.durum_yaz(o, "son_calisma_gunu", _turkiye_gunu())
    assert main(["bugun-calisti-mi"]) == 0
    assert capsys.readouterr().out.strip() == "true"  # GitHub adımı bu çıktıyı okur: başka bir şey yazılmamalı
    fabrika.kw["bind"].dispose()


def test_gorunen_ad_marka():
    assert gorunen_ad("Nova Spark X Teknoloji Anonim Şirketi") == "Patika Global"
    assert gorunen_ad("Beakwise Bilişim Teknolojileri ve Danışmanlık A.Ş.") == "Beakwise"
    assert zenginlestir({"firma": "Nova Spark X Teknoloji Anonim Şirketi"})["firma_gorunen"] == "Patika Global"


# ---------------- sıralama ve firma kotası ----------------
BUGUN = date(2026, 10, 30)


def _ilan(firma, yayin=None, girisim=False, ucretli=False, surekli=False, tur="is", gorulme="2026-10-30"):
    return {
        "kimlik": f"{firma}-{yayin}",
        "firma": firma,
        "baslik": "Staj",
        "rol": "yazilim",
        "seviye": "staj",
        "yayin": yayin,
        "girisim": girisim,
        "surekli_acik": surekli,
        "ilan_turu": tur,
        "ilk_gorulme": f"{gorulme}T04:00:00+00:00",
        "ayrinti": {"ucretli": "evet"} if ucretli else None,
    }


def test_siralama_yeni_once_girisim_ucretli_one_tarihsiz_ve_surekli_acik_geride():
    ilanlar = [
        _ilan("A surekli", "2022-03-01", girisim=True, surekli=True),
        _ilan("B tarihsiz", None, girisim=True),
        _ilan("C eski", "2026-08-01", girisim=True),
        _ilan("D yeni", "2026-10-28"),
        _ilan("E yeni ucretli", "2026-10-20", ucretli=True),
        _ilan("F yeni girisim", "2026-10-18", girisim=True),
        _ilan("G yeni egitim", "2026-10-29", girisim=True, tur="egitim"),
        _ilan("H taze", "2026-09-30", girisim=True),
    ]
    sirali = [i["firma"] for i in sorted(ilanlar, key=lambda i: siralama_anahtari(i, BUGUN))]
    assert sirali == [
        "F yeni girisim",  # son 14 gün: önce girişim
        "E yeni ucretli",  # sonra ücretli
        "D yeni",
        "G yeni egitim",  # tazelik aynı: iş ilanı eğitimden önce
        "H taze",
        "C eski",
        "B tarihsiz",
        "A surekli",
    ]


def test_firma_basina_en_fazla_iki_ilan_kalanlar_sonraki_bultene(oturum):
    for n in range(4):
        ilan_kur(oturum, f"https://a.test/d{n}", f"Staj D{n}", firma="Dream Games", yayin="2026-10-28")
    ilan_kur(oturum, "https://a.test/s", "Test Stajı", firma="Skymod", yayin="2026-10-27")
    with oturum.begin() as o:
        onayla(o, kayit_iste(o, "a@x.com", {}, "gunluk", "test"))
    sabah = datetime(2026, 10, 30, 4, 30, tzinfo=UTC)

    class Gonderici:
        def __init__(self):
            self.gidenler = []

        def gonder(self, e):
            self.gidenler.append(e)

    bir, iki, uc = Gonderici(), Gonderici(), Gonderici()
    bultenleri_gonder(oturum, bir, AYAR, sabah)
    metin = bir.gidenler[0].metin
    assert sum(f"Staj D{n}" in metin for n in range(4)) == 2 and "Test Stajı" in metin  # Skymod kesimde kalmaz
    bultenleri_gonder(oturum, iki, AYAR, sabah + timedelta(days=1))
    assert sum(f"Staj D{n}" in iki.gidenler[0].metin for n in range(4)) == 2  # kalanlar ertesi gün
    assert bultenleri_gonder(oturum, uc, AYAR, sabah + timedelta(days=2))["gonderilen"] == 0


def test_bulten_sec_azami_ve_gonderilmis():
    ilanlar = [_ilan(f"F{n}", "2026-10-28") for n in range(5)]
    assert len(bulten_sec(ilanlar, {}, set(), 3)) == 3
    assert [i["firma"] for i in bulten_sec(ilanlar, {}, {"F0-2026-10-28"}, 2)] == ["F1", "F2"]


# ---------------- firma listesi eşitleme ----------------
def test_firma_listesi_yalnizca_degisince_aktarilir(oturum, tmp_path):
    yol = tmp_path / "firmalar.csv"
    yol.write_text("ad,web,ats,slug,kariyer,etiket,kaynak\nObilet,,recruitee,obilet,,,ats_genis\n", encoding="utf-8")
    assert firma_listesini_esitle(oturum, yol) is True
    assert firma_listesini_esitle(oturum, yol) is False  # dosya aynı: dokunulmaz
    yol.write_text(
        "ad,web,ats,slug,kariyer,etiket,kaynak\nObilet,,recruitee,obilet,,kurumsal,ats_genis\n", encoding="utf-8"
    )
    assert firma_listesini_esitle(oturum, yol) is True
    with oturum() as o:
        csv_metni = depo.girisim_listesi_csv(o)
    assert "Obilet" not in csv_metni  # kurumsal etiketi aday listesinden de çıkarır
    assert firma_listesini_esitle(oturum, tmp_path / "yok.csv") is False


def test_girisim_listesi_gerekcesiyle(oturum):
    with oturum.begin() as o:
        depo.firma_ekle_veya_guncelle(o, "Valven", kaynak="turkiye.ai")
        depo.firma_ekle_veya_guncelle(o, "Agave Games", etiket=["girisim"], kaynak="ats_genis")
        depo.firma_ekle_veya_guncelle(o, "Beakwise", etiket=["teknopark"], kaynak="budotek")
        depo.firma_ekle_veya_guncelle(o, "Aselsan", etiket=["savunma"], kaynak="teknopark_istanbul")
        depo.firma_ekle_veya_guncelle(o, "Kobi", kaynak="savunmakariyer")
    with oturum() as o:
        satirlar = depo.girisim_listesi_csv(o).splitlines()
    assert satirlar[0].startswith("karar,firma,gerekce")
    metin = "\n".join(satirlar)
    assert "evet,Valven,evet: turkiye.ai listesinde" in metin and "evet,Agave Games,evet: elle" in metin
    assert "aday,Beakwise,aday: budotek" in metin
    assert "Aselsan" not in metin and "Kobi" not in metin
    assert satirlar[1].startswith("evet") and satirlar[-1].startswith("aday")  # önce evet, sonra aday


# ---------------- Vercel Cron ucu ----------------
CRON = dataclasses.replace(AYAR, cron_gizli="gizli-deger", github_tetik_tokeni="token-deger")
BASLIK = {"Authorization": "Bearer gizli-deger"}


def _istemci(oturum, ayar=CRON, tetikleyici=lambda _: 204):
    return TestClient(uygulama_olustur(ayar, oturum, SahteGonderici(), tetikleyici=tetikleyici))


class SahteGonderici:
    def gonder(self, _):
        pass


def test_cron_ucu_yetkisiz_istegi_reddeder(oturum):
    cagrilar = []
    istemci = _istemci(oturum, tetikleyici=lambda a: cagrilar.append(a) or 204)
    assert istemci.get("/api/cron/gunluk").status_code == 401
    assert istemci.get("/api/cron/gunluk", headers={"Authorization": "Bearer yanlis"}).status_code == 401
    assert cagrilar == []
    # CRON_SECRET tanımlı değilse boş başlık da yanlış başlık da geçmez
    bos = _istemci(oturum, dataclasses.replace(CRON, cron_gizli=""))
    assert bos.get("/api/cron/gunluk", headers={"Authorization": "Bearer "}).status_code == 401


def test_cron_ucu_tetikler_ve_hatalarda_anlamli_doner(oturum):
    assert _istemci(oturum).get("/api/cron/gunluk", headers=BASLIK).json() == {"durum": "tetiklendi"}
    tokensiz = _istemci(oturum, dataclasses.replace(CRON, github_tetik_tokeni=""))
    cevap = tokensiz.get("/api/cron/gunluk", headers=BASLIK)
    assert cevap.status_code == 503 and cevap.json()["hata"] == "tetik_tokeni_yok"
    assert "yedek" in cevap.json()["mesaj"]
    red = _istemci(oturum, tetikleyici=lambda _: 403).get("/api/cron/gunluk", headers=BASLIK)
    assert red.status_code == 502 and "403" in red.json()["mesaj"] and "token-deger" not in red.text

    def ulasilamadi(_):
        raise requests.ConnectionError("yok")

    cevap = _istemci(oturum, tetikleyici=ulasilamadi).get("/api/cron/gunluk", headers=BASLIK)
    assert cevap.status_code == 502 and cevap.json()["hata"] == "github_ulasilamadi"


def test_github_cagrisi_dogru_adrese_gider(monkeypatch):
    gorulen = {}

    def sahte_post(url, headers, json, timeout):
        gorulen.update(url=url, headers=headers, json=json)
        cevap = requests.Response()
        cevap.status_code = 204
        return cevap

    monkeypatch.setattr(requests, "post", sahte_post)
    assert is_akisini_tetikle(CRON) == 204
    assert gorulen["url"].endswith("/repos/bilalerg/internreader/actions/workflows/gunluk.yml/dispatches")
    assert gorulen["json"] == {"ref": "main"} and gorulen["headers"]["Authorization"] == "Bearer token-deger"


def test_vercel_cron_ve_yedek_zamanlama_tanimli():
    vercel = json.loads((KOK / "vercel.json").read_text(encoding="utf-8"))
    assert vercel["crons"] == [{"path": "/api/cron/gunluk", "schedule": "0 4 * * *"}]
    is_akisi = (KOK / ".github/workflows/gunluk.yml").read_text(encoding="utf-8")
    assert 'cron: "37 6 * * *"' in is_akisi and "bugun-calisti-mi" in is_akisi


@pytest.mark.parametrize("gizli", ["CRON_SECRET", "GITHUB_TETIK_TOKENI"])
def test_gizli_degerler_ayar_ciktisinda_gorunmez(monkeypatch, gizli):
    monkeypatch.setenv(gizli, "cok-gizli-deger")
    assert "cok-gizli-deger" not in repr(ayarlari_oku())
