"""Pilot için elle onay modu: sabah işi bülten göndermez, önizleme verir; bülten elle gider ve yalnızca önizlemesi
gitmiş ilanları içerir; yanlış ilan gizlenir, sitede ve e-postada görünmez, yeniden taramada açılmaz."""

import dataclasses
import json
import logging
from datetime import timedelta
from pathlib import Path

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import text, update

from internreader import __main__ as komut
from internreader import boru, depo
from internreader.api import uygulama_olustur
from internreader.ayar import ayarlari_oku
from internreader.boru import TaramaRaporu
from internreader.bulten import bultenleri_gonder, hos_geldin_gonder
from internreader.bulten.gonderim import HAZIRLIK, SON_GONDERIM, hazirligi_yaz, onizleme_gonder
from internreader.db import Bulten, IlanKaydi, motor_olustur, oturum_fabrikasi, simdi
from internreader.model import Ilan
from internreader.sema import alembic_ayari, semayi_hazirla
from tests.test_bulten import AYAR, HEPSI, SahteGonderici, abone_ekle, ilan_ekle

ADRES = "bilal.onizleme@ornek.com"
KOK = Path(__file__).resolve().parents[1]
ELLE = dataclasses.replace(AYAR, bulten_elle=True)


def test_ayar_varsayilan_kapali(monkeypatch):
    monkeypatch.delenv("INTERNREADER_BULTEN_ELLE", raising=False)
    assert ayarlari_oku().bulten_elle is False
    monkeypatch.setenv("INTERNREADER_BULTEN_ELLE", "1")
    assert ayarlari_oku().bulten_elle is True
    monkeypatch.setenv("INTERNREADER_BULTEN_ELLE", "0")
    assert ayarlari_oku().bulten_elle is False


@pytest.fixture
def komut_ortami(monkeypatch, tmp_path):
    """Komut satırı, ağ ve yapay zekâ olmadan: tarama ve ayrıntı adımları boş geçer, e-postalar sahte göndericiye."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'k.db').as_posix()}")
    monkeypatch.setenv("INTERNREADER_BULTEN_ELLE", "1")
    monkeypatch.setenv("INTERNREADER_GIZLI_ANAHTAR", "test-anahtari")
    g = SahteGonderici()
    gercek_yayinla = boru.yayinla
    monkeypatch.setattr(komut, "gonderici_olustur", lambda _: g)
    monkeypatch.setattr(komut, "CIKTI", tmp_path / "cikti")
    monkeypatch.setattr(komut, "firma_listesini_esitle", lambda *_: None)
    monkeypatch.setattr(boru, "yz_olustur", lambda *_: None)
    monkeypatch.setattr(boru, "tara", lambda *_, **__: TaramaRaporu())
    monkeypatch.setattr(boru, "ayrintilari_zenginlestir", lambda *_, **__: {})
    monkeypatch.setattr(boru, "yayinla", lambda o, **k: gercek_yayinla(o, cikti_dizini=tmp_path / "cikti", **k))
    fabrika = oturum_fabrikasi(f"sqlite:///{(tmp_path / 'k.db').as_posix()}")
    yield fabrika, g
    fabrika.kw["bind"].dispose()


def ilk_gorulmeyi_ayarla(oturum, kimlik, an):
    with oturum.begin() as o:
        o.execute(update(IlanKaydi).where(IlanKaydi.kimlik == kimlik).values(ilk_gorulme=an))


def test_elle_modda_sabah_isi_bulten_gondermez_onizleme_verir_bulten_elle_gider(komut_ortami, capsys, caplog):
    oturum, g = komut_ortami
    ilk = ilan_ekle(oturum, "https://a.test/staj-1", "Yazılım Stajı", "Istanbul", firma="Acme")
    abone_ekle(oturum, "ogrenci@x.com", HEPSI)

    assert komut.main(["calistir"]) == 0
    assert g.gidenler == []  # bülten bekliyor
    with oturum() as o:
        assert o.query(Bulten).count() == 0 and depo.durum_al(o, HAZIRLIK)
    # Zamanları açıkça ayarla (saat çözünürlüğü kaba sistemlerde art arda kayıtlar aynı anı alabiliyor)
    an = simdi()
    ilk_gorulmeyi_ayarla(oturum, ilk, an - timedelta(hours=2))
    hazirligi_yaz(oturum, an - timedelta(hours=1))
    capsys.readouterr()

    # Önizleme: yeni ilanların hepsi, adresleri görünür; adres kayıtlara düşmez
    with caplog.at_level(logging.DEBUG):
        assert komut.main(["bulten-dene", ADRES, "--yeni"]) == 0
    cikti = capsys.readouterr()
    (onizleme,) = g.gidenler
    assert onizleme.alici == ADRES and onizleme.konu == "[ÖNİZLEME] Onay bekleyen 1 yeni ilan"
    assert "https://a.test/staj-1" in onizleme.metin and ">https://a.test/staj-1</a>" in onizleme.html
    assert "/api/t/" not in onizleme.html  # tıklama ölçümüne girmez
    assert '"sonuc": "gonderildi"' in cikti.out and ADRES not in cikti.out + cikti.err + caplog.text
    with oturum() as o:
        assert o.query(Bulten).count() == 0  # önizleme kayıt yazmaz

    # Önizlemeden sonra ara tarama yeni ilan buldu: önizlemesi gitmediği için bu bültene girmez
    gec = ilan_ekle(oturum, "https://b.test/staj-2", "Veri Stajı", "Istanbul", firma="Beta", rol="veri")
    ilk_gorulmeyi_ayarla(oturum, gec, an - timedelta(minutes=30))
    g.gidenler.clear()
    assert komut.main(["bulten-gonder"]) == 0
    (bulten,) = g.gidenler
    assert bulten.alici == "ogrenci@x.com" and "Yazılım Stajı" in bulten.metin and "Veri Stajı" not in bulten.metin
    # Aynı gün ikinci kez basılsa da ikinci bülten yok
    assert komut.main(["bulten-gonder"]) == 0 and len(g.gidenler) == 1

    # Gönderdikten sonra önizlenecek ilan yok; geç gelen ilan bir sonraki sabah işinin önizlemesinde
    g.gidenler.clear()
    capsys.readouterr()
    assert komut.main(["bulten-dene", ADRES, "--yeni"]) == 0
    assert g.gidenler == [] and '"sonuc": "yeni_ilan_yok"' in capsys.readouterr().out
    assert komut.main(["calistir"]) == 0 and g.gidenler == []
    assert komut.main(["bulten-dene", ADRES, "--yeni"]) == 0
    (ertesi,) = g.gidenler
    assert "Veri Stajı" in ertesi.metin and "Yazılım Stajı" not in ertesi.metin


def test_elle_mod_kapaliyken_sabah_isi_bulteni_gonderir(komut_ortami, monkeypatch):
    oturum, g = komut_ortami
    monkeypatch.setenv("INTERNREADER_BULTEN_ELLE", "0")
    ilan_ekle(oturum, "https://a.test/1", "Yazılım Stajı", "Istanbul", firma="Acme")
    abone_ekle(oturum, "ogrenci@x.com", HEPSI)
    assert komut.main(["calistir"]) == 0
    assert [e.alici for e in g.gidenler] == ["ogrenci@x.com"]


def test_elle_modda_hazirlik_yoksa_bulten_gitmez(komut_ortami):
    oturum, g = komut_ortami
    ilan_ekle(oturum, "https://a.test/1", "Yazılım Stajı", "Istanbul", firma="Acme")
    abone_ekle(oturum, "ogrenci@x.com", HEPSI)
    assert komut.main(["bulten-gonder"]) == 1 and g.gidenler == []


def test_elle_modda_hos_geldin_otomatik(oturum):
    ilan_ekle(oturum, "https://a.test/1", "Yazılım Stajı", "Istanbul", firma="Acme")
    g = SahteGonderici()
    istemci = TestClient(uygulama_olustur(ELLE, oturum, g))
    assert istemci.post("/api/abone", json={"eposta": "yeni@x.com", "kvkk_onay": True}).status_code == 202
    jeton = g.gidenler[-1].metin.split("jeton=")[1].split()[0]
    assert istemci.post("/api/abone/onay", json={"jeton": jeton}).json()["hos_geldin"] == "gonderildi"
    assert "Yazılım Stajı" in g.gidenler[-1].metin


def test_onizleme_butun_yeni_ilanlari_sinirsiz_gosterir_eski_tarihliyi_isaretler(oturum, tmp_path):
    for n in range(20):  # bültende firma başına 2, e-posta başına 15; önizlemede hepsi
        ilan_ekle(oturum, f"https://a.test/{n}", f"Staj {n}", "Istanbul", firma="Acme")
    with oturum.begin() as o:
        eski = Ilan(firma="Eski", baslik="Eski Staj", url="https://e.test/1", kaynak="lever", tarih="2026-01-01")
        depo.ilanlari_kaydet(o, [eski], set())
        depo.siniflandirma_kaydet(o, {eski.kimlik: {"seviye": "staj", "rol": "yazilim", "yapay_zeka": "yok"}}, "t")
    g = SahteGonderici()
    rapor = onizleme_gonder(oturum, g, AYAR, ADRES, klasor=tmp_path, an=simdi())
    assert rapor["ilan"] == 21 and len(g.gidenler) == 1
    (e,) = g.gidenler
    assert all(f"https://a.test/{n}" in e.metin for n in range(20))
    # Eski tarihli ilan bültene girmez ama sessizlik e-postasında yakın ilan olabilir: listede, işaretli
    assert "Eski Staj" in e.metin and e.metin.count("Eski tarihli: bültene girmez") == 1
    assert "Eski tarihli: bültene girmez" in e.html
    assert (tmp_path / "onizleme.html").exists()


def test_onizleme_son_gonderimden_sonrasini_gosterir_yeni_yoksa_gitmez(oturum, tmp_path):
    eski = ilan_ekle(oturum, "https://a.test/1", "Yazılım Stajı", "Istanbul", firma="Acme")
    abone_ekle(oturum, "ogrenci@x.com", HEPSI)
    an = simdi()
    ilk_gorulmeyi_ayarla(oturum, eski, an - timedelta(hours=2))
    bultenleri_gonder(oturum, SahteGonderici(), AYAR, an - timedelta(hours=1))
    g = SahteGonderici()
    assert onizleme_gonder(oturum, g, AYAR, ADRES, klasor=tmp_path, an=an)["sonuc"] == "yeni_ilan_yok"
    assert g.gidenler == []
    ilan_ekle(oturum, "https://b.test/1", "Veri Stajı", "Istanbul", firma="Beta", rol="veri")
    assert onizleme_gonder(oturum, g, AYAR, ADRES, klasor=tmp_path)["ilan"] == 1
    assert "Veri Stajı" in g.gidenler[0].metin and "Yazılım Stajı" not in g.gidenler[0].metin
    with oturum() as o:
        assert depo.durum_al(o, SON_GONDERIM)


def test_gizli_ilan_yayindan_eposta_dan_duser_yeniden_taramada_donmez(oturum, tmp_path):
    with oturum.begin() as o:
        depo.firma_ekle_veya_guncelle(o, "Acme", web="https://acme.test", ats="lever", slug="acme")
    yanlis = Ilan(firma="Acme", baslik="Sales Intern", url="https://a.test/sales", kaynak="lever", konum="Istanbul")
    kopya = Ilan(firma="Acme", baslik="SALES INTERN", url="https://a.test/sales-ank", kaynak="lever", konum="Ankara")
    dogru = Ilan(firma="Acme", baslik="Backend Intern", url="https://a.test/backend", kaynak="lever", konum="Istanbul")
    with oturum.begin() as o:
        depo.ilanlari_kaydet(o, [yanlis, kopya, dogru], {"Acme"})
        karar = {"seviye": "staj", "rol": "yazilim", "yapay_zeka": "yok", "gerekce": "staj ilanı"}
        depo.siniflandirma_kaydet(o, {i.kimlik: karar for i in (yanlis, kopya, dogru)}, "claude-haiku-5-5")
    with oturum.begin() as o:
        gizlenen = depo.ilan_gizle(o, "https://a.test/sales/")  # sondaki eğik çizgi fark etmez
        assert {i.url for i in gizlenen} == {yanlis.url, kopya.url}  # aynı firma + başlıklı kopya da
        assert depo.ilan_gizle(o, "https://olmayan.test/1") == []

    def gorunenler():
        with oturum() as o:
            return {i["baslik"] for i in depo.yayinlanacak_ilanlar(o)}

    assert gorunenler() == {"Backend Intern"}
    # Yeniden tarama: ilan yine görüldü, aktif kalır ama gizli kalır
    with oturum.begin() as o:
        depo.ilanlari_kaydet(o, [yanlis, kopya, dogru], {"Acme"})
    with oturum() as o:
        kayit = o.get(IlanKaydi, yanlis.kimlik)
        assert kayit.aktif and kayit.gizli
        assert all(k["baslik"] != "Sales Intern" for k in depo.ornek_kararlar(o, uygun=True))
        assert all(i["baslik"] != "Sales Intern" for i in depo.ayrinti_bekleyenler(o))
    assert gorunenler() == {"Backend Intern"}
    # Site verisi, bülten, hoş geldin, önizleme
    boru.yayinla(oturum, cikti_dizini=tmp_path)
    site = json.loads((tmp_path / "ilanlar.json").read_text(encoding="utf-8"))
    assert [i["baslik"] for i in site["ilanlar"]] == ["Backend Intern"]
    assert "Sales" not in (tmp_path / "README.md").read_text(encoding="utf-8")
    abone_id = abone_ekle(oturum, "a@x.com", HEPSI)
    g = SahteGonderici()
    hos_geldin_gonder(oturum, g, AYAR, abone_id)
    bultenleri_gonder(oturum, g, AYAR, simdi() + timedelta(days=1))
    onizleme_gonder(oturum, g, AYAR, ADRES, klasor=tmp_path)
    assert g.gidenler and all("Sales" not in e.metin for e in g.gidenler)
    # Geri alınabilir
    with oturum.begin() as o:
        assert len(depo.ilan_gizle(o, yanlis.url, gizli=False)) == 2
    assert gorunenler() == {"Backend Intern", "Sales Intern", "SALES INTERN"}


def test_ilan_gizle_komutu(komut_ortami, capsys):
    oturum, _ = komut_ortami
    ilan_ekle(oturum, "https://a.test/1", "Yazılım Stajı", "Istanbul", firma="Acme")
    assert komut.main(["ilan-gizle", "https://a.test/1"]) == 0
    assert "1 ilan gizlendi" in capsys.readouterr().out
    with oturum() as o:
        assert depo.yayinlanacak_ilanlar(o) == []
    assert komut.main(["ilan-gizle", "https://a.test/olmayan"]) == 1
    assert komut.main(["ilan-gizle", "https://a.test/1", "--geri-al"]) == 0
    with oturum() as o:
        assert len(depo.yayinlanacak_ilanlar(o)) == 1


def test_goc_var_olan_ilanlari_ve_bagli_kayitlari_korur(tmp_path):
    # 0007 SQLite'ta tabloyu yeniden kurabilir; ilanlara CASCADE ile bağlı karar ve gönderimler silinmemeli
    motor = motor_olustur(f"sqlite:///{(tmp_path / 'g.db').as_posix()}")
    with motor.begin() as baglanti:
        command.upgrade(alembic_ayari(baglanti), "0006")
        baglanti.execute(
            text(
                "INSERT INTO ilanlar (kimlik, firma, baslik, url, kaynak, konum, calisma_tipi, yayin_tarihi, aciklama,"
                " etiket, ilk_gorulme, son_gorulme, aktif) VALUES ('k1', 'Acme', 'Staj', 'https://a.test/1', 'lever',"
                " '', '', '', '', '[]', '2026-10-01', '2026-10-30', 1)"
            )
        )
        baglanti.execute(
            text(
                "INSERT INTO siniflandirmalar (kimlik, seviye, rol, yapay_zeka, ogrenciye_uygun, gerekce, model, tarih)"
                " VALUES ('k1', 'staj', 'yazilim', 'yok', 1, '', 'm', '2026-10-01')"
            )
        )
        baglanti.execute(
            text(
                "INSERT INTO aboneler (eposta, tercihler, siklik, durum, kvkk_surumu, kvkk_onay_tarihi, kaynak,"
                " olusturma) VALUES ('a@x.com', '{}', 'gunluk', 'onayli', 'v', '2026-10-01', 'site', '2026-10-01')"
            )
        )
        baglanti.execute(text("INSERT INTO gonderimler (abone_id, ilan_kimlik, tarih) VALUES (1, 'k1', '2026-10-02')"))
    semayi_hazirla(motor)
    with motor.connect() as baglanti:
        assert baglanti.execute(text("SELECT gizli FROM ilanlar")).scalar() in (0, False)
        assert baglanti.execute(text("SELECT count(*) FROM siniflandirmalar")).scalar() == 1
        assert baglanti.execute(text("SELECT count(*) FROM gonderimler")).scalar() == 1
    motor.dispose()


def test_is_akislari_elle_onay():
    gunluk = (KOK / ".github/workflows/gunluk.yml").read_text(encoding="utf-8")
    assert "INTERNREADER_BULTEN_ELLE: ${{ vars.INTERNREADER_BULTEN_ELLE || '1' }}" in gunluk
    assert 'bulten-dene "$TEST_EPOSTA" --yeni' in gunluk and "::add-mask::" in gunluk
    assert "::warning::TEST_EPOSTA" in gunluk and "set -x" not in gunluk
    # Adres yalnızca önizleme adımında, gizli değerden
    assert gunluk.count("secrets.TEST_EPOSTA") == 1 and gunluk.index("secrets.TEST_EPOSTA") > gunluk.index("Önizleme")

    gonder = (KOK / ".github/workflows/bulten_gonder.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch" in gonder and "schedule" not in gonder and "inputs" not in gonder
    assert "python -m internreader bulten-gonder" in gonder and "group: internreader-veritabani" in gonder
    assert "INTERNREADER_BULTEN_ELLE: ${{ vars.INTERNREADER_BULTEN_ELLE || '1' }}" in gonder

    gizle = (KOK / ".github/workflows/ilan_gizle.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch" in gizle and "schedule" not in gizle and "group: internreader-veritabani" in gizle
    assert "yayinla --ozetsiz" in gizle and "ilanlar-degisti-mi" in gizle
    # Girdi komut satırına doğrudan yazılmaz (kabuk enjeksiyonu): yalnızca ortam değişkeni olarak
    satirlar = [s for s in gizle.splitlines() if "${{ inputs.adres }}" in s]
    assert len(satirlar) == 1 and satirlar[0].strip().startswith("ADRES:")
    assert "SMTP" not in gizle and "ANTHROPIC" not in gizle
