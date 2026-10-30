"""Sessizlik e-postası: pazartesi, bir haftadır e-posta almamış aboneye "bu hafta yeni ilan yok" + yakın ilanlar.
Boşken gitmez, haftada en fazla bir tane, yalnızca pazartesi, kotadan düşer, tıklama ölçümüne girer."""

import dataclasses
from datetime import UTC, datetime, timedelta

from internreader import depo
from internreader.bulten import bultenleri_gonder
from internreader.bulten.tiklama import jeton_coz
from internreader.db import Abone, Bulten, Gonderim
from tests.test_bulten import AYAR, HEPSI, SahteGonderici, abone_ekle, ilan_ekle
from tests.test_hos_geldin import ilan_ekle as tarihli_ilan_ekle

PAZARTESI = datetime(2026, 11, 9, 4, 30, tzinfo=UTC)  # pazartesi 07:30 Türkiye
IZMIRLI = {**HEPSI, "alanlar": ["yazilim"], "sehirler": ["izmir"]}


def sessiz_abone(oturum, eposta, tercihler=IZMIRLI, onay_gun_once=10, siklik="gunluk"):
    abone_id = abone_ekle(oturum, eposta, tercihler, siklik=siklik)
    with oturum.begin() as o:
        abone = o.get(Abone, abone_id)
        abone.onay_tarihi = abone.olusturma = PAZARTESI - timedelta(days=onay_gun_once)
    return abone_id


def bulten_kaydi(oturum, abone_id, an, durum="gonderildi"):
    with oturum.begin() as o:
        depo.bulten_kaydet(o, abone_id, 1, durum, an)


def sessizlikler(g: SahteGonderici) -> list:
    return [e for e in g.gidenler if e.konu == "Bu hafta sana uyan yeni ilan çıkmadı"]


def firmalar_ekle(oturum, sayi):
    with oturum.begin() as o:
        for n in range(sayi):
            depo.firma_ekle_veya_guncelle(o, f"Firma {n}", web=f"https://f{n}.test", ats="lever", slug=f"f{n}")


def test_sessiz_aboneye_yakin_ilanlarla_kisa_eposta(oturum):
    firmalar_ekle(oturum, 3)
    ilan_ekle(oturum, "https://a.test/1", "Yazılım Stajı", "Ankara", firma="Acme")  # İzmirliye tam uymaz, yakın
    ilan_ekle(oturum, "https://a.test/2", "Veri Stajı", "Ankara", firma="Beta", rol="veri")  # alan korunur: gitmez
    abone_id = sessiz_abone(oturum, "a@x.com")
    g = SahteGonderici()
    rapor = bultenleri_gonder(oturum, g, AYAR, PAZARTESI)
    assert rapor["bos"] == 1 and rapor["sessizlik"] == 1 and rapor["gonderilen"] == 0
    (e,) = g.gidenler
    assert e.alici == "a@x.com" and e.konu == "Bu hafta sana uyan yeni ilan çıkmadı"
    assert "3 şirketin ilan sayfasını her gün taradık" in e.metin and "Yakın ilanlar" in e.html
    assert "Yazılım Stajı" in e.metin and "Veri Stajı" not in e.metin
    assert "List-Unsubscribe" in e.basliklar
    jeton = e.html.split("/api/t/")[1].split('"')[0]
    assert jeton_coz(jeton, AYAR.gizli_anahtar)["t"] == "sessizlik"  # tıklama ölçümüne girer
    with oturum() as o:
        assert [(b.durum, b.ilan_sayisi) for b in o.query(Bulten)] == [("sessizlik", 1)]
        assert o.query(Gonderim).count() == 1  # yakın ilan bir daha önerilmez
        assert o.get(Abone, abone_id).son_bulten is None  # bülten sayılmaz
        assert depo.eposta_sayisi(o, PAZARTESI) == 1
        assert depo.tiklama_raporu(o, PAZARTESI + timedelta(hours=1))["gonderilen_eposta"] == 1


def test_yedi_gun_kurali(oturum):
    ilan_ekle(oturum, "https://a.test/1", "Yazılım Stajı", "Ankara", firma="Acme")
    sessiz_abone(oturum, "yeni@x.com", onay_gun_once=6)  # geçen salı onayladı: henüz bir hafta olmadı
    sessiz_abone(oturum, "hafta@x.com", onay_gun_once=7)  # geçen pazartesi: bir hafta oldu
    yakinda = sessiz_abone(oturum, "yakinda@x.com")
    bulten_kaydi(oturum, yakinda, PAZARTESI - timedelta(days=3))  # cuma bülten aldı
    hos = sessiz_abone(oturum, "hos@x.com")
    bulten_kaydi(oturum, hos, PAZARTESI - timedelta(days=5), depo.HOS_GELDIN_DURUMU)
    gecen = sessiz_abone(oturum, "gecen@x.com")
    bulten_kaydi(oturum, gecen, PAZARTESI - timedelta(days=7) + timedelta(hours=5))  # geçen pazartesi öğlen
    hatali = sessiz_abone(oturum, "hatali@x.com")
    bulten_kaydi(oturum, hatali, PAZARTESI - timedelta(days=2), "hata")  # gitmeyen e-posta sayılmaz
    g = SahteGonderici()
    bultenleri_gonder(oturum, g, AYAR, PAZARTESI)
    assert {e.alici for e in sessizlikler(g)} == {"hafta@x.com", "gecen@x.com", "hatali@x.com"}


def test_yakin_ilan_yoksa_gitmez_kota_harcanmaz(oturum):
    # Tek ilan 100 günlük: bültene girmez (yeni değil), yakın ilan olarak önerilebilir
    eski = (PAZARTESI - timedelta(days=100)).date().isoformat()
    kimlik = tarihli_ilan_ekle(oturum, "https://a.test/1", "Yazılım Stajı", konum="Ankara", yayin=eski)
    sessiz_abone(oturum, "hepsi@x.com", tercihler={})  # tercihsiz: gevşetilecek bir şey yok
    gitti = sessiz_abone(oturum, "gitti@x.com")
    with oturum.begin() as o:  # tek yakın ilan bu aboneye 20 gün önce gitmişti
        depo.gonderim_kaydet(o, o.get(Abone, gitti), [kimlik], PAZARTESI - timedelta(days=20), False)
    g = SahteGonderici()
    rapor = bultenleri_gonder(oturum, g, AYAR, PAZARTESI)
    assert g.gidenler == [] and rapor["sessizlik"] == 0 and rapor["sessizlik_bos"] == 2
    with oturum() as o:
        assert depo.eposta_sayisi(o, PAZARTESI) == 0 and o.query(Bulten).count() == 0
    # Aynı ilan, gönderilmemiş bir aboneye yakın ilan olarak gider
    sessiz_abone(oturum, "yeni@x.com")
    g = SahteGonderici()
    bultenleri_gonder(oturum, g, AYAR, PAZARTESI + timedelta(hours=1))
    assert [e.alici for e in sessizlikler(g)] == ["yeni@x.com"]


def test_hic_ilan_yokken_hic_eposta_gitmez(oturum):
    sessiz_abone(oturum, "a@x.com")
    sessiz_abone(oturum, "b@x.com", tercihler=HEPSI)
    g = SahteGonderici()
    rapor = bultenleri_gonder(oturum, g, AYAR, PAZARTESI)
    assert g.gidenler == [] and rapor["sessizlik"] == 0 and rapor["sessizlik_bos"] == 2
    with oturum() as o:
        assert depo.eposta_sayisi(o, PAZARTESI) == 0 and o.query(Bulten).count() == 0


def test_haftada_bir_ve_hep_yeni_yakin_ilan(oturum):
    ilan_ekle(oturum, "https://a.test/1", "Yazılım Stajı", "Ankara", firma="Acme")
    sessiz_abone(oturum, "a@x.com")
    g = SahteGonderici()
    bultenleri_gonder(oturum, g, AYAR, PAZARTESI)
    ilan_ekle(oturum, "https://b.test/1", "Backend Stajı", "Ankara", firma="Beta")
    # Aynı pazartesi ikinci çalışma (yedek zamanlama, elle tetikleme): ikinci sessizlik yok
    bultenleri_gonder(oturum, g, AYAR, PAZARTESI + timedelta(hours=5))
    assert len(sessizlikler(g)) == 1
    # Ertesi pazartesi yine sessizse: yalnızca daha önce gönderilmemiş yakın ilan
    sonraki = SahteGonderici()
    bultenleri_gonder(oturum, sonraki, AYAR, PAZARTESI + timedelta(days=7, minutes=-120))  # bu kez daha erken saatte
    (e,) = sessizlikler(sonraki)
    assert "Backend Stajı" in e.metin and "Yazılım Stajı" not in e.metin
    # Üçüncü pazartesi önerilecek yeni yakın ilan yok: e-posta gitmez
    ucuncu = SahteGonderici()
    assert bultenleri_gonder(oturum, ucuncu, AYAR, PAZARTESI + timedelta(days=14))["sessizlik_bos"] == 1
    assert ucuncu.gidenler == []


def test_pazartesi_disinda_gitmez(oturum):
    ilan_ekle(oturum, "https://a.test/1", "Yazılım Stajı", "Ankara", firma="Acme")
    sessiz_abone(oturum, "a@x.com", onay_gun_once=20)
    for gun in range(1, 7):  # salı → pazar
        g = SahteGonderici()
        assert bultenleri_gonder(oturum, g, AYAR, PAZARTESI + timedelta(days=gun))["sessizlik"] == 0
        assert g.gidenler == []
    # Türkiye takvimi: pazar 22:00 UTC = pazartesi 01:00 Türkiye → pazartesi sayılır
    g = SahteGonderici()
    assert bultenleri_gonder(oturum, g, AYAR, datetime(2026, 11, 15, 22, 0, tzinfo=UTC))["sessizlik"] == 1


def test_bulten_alan_sessizlik_almaz_ve_bulten_kotada_once_gelir(oturum):
    ilan_ekle(oturum, "https://a.test/1", "İzmir Stajı", "Izmir", firma="Acme")
    ilan_ekle(oturum, "https://b.test/1", "Ankara Stajı", "Ankara", firma="Beta")
    sessiz_abone(oturum, "bulten@x.com")  # İzmir ilanı tam uyar: bülten alır
    sessiz_abone(oturum, "ankara@x.com", tercihler={**HEPSI, "sehirler": ["ankara"]})  # Ankara ilanı tam uyar
    sessiz_abone(oturum, "ist@x.com", tercihler={**HEPSI, "alanlar": ["yazilim"], "sehirler": ["istanbul"]})
    sessiz_abone(oturum, "bursa@x.com", tercihler={**HEPSI, "alanlar": ["yazilim"], "sehirler": ["bursa"]})
    sinirli = dataclasses.replace(AYAR, gunluk_eposta_siniri=3, onay_payi=0)
    g = SahteGonderici()
    rapor = bultenleri_gonder(oturum, g, sinirli, PAZARTESI)
    bultenler = [e.alici for e in g.gidenler if e not in sessizlikler(g)]
    assert bultenler == ["bulten@x.com", "ankara@x.com"]  # önce bülten
    assert [e.alici for e in sessizlikler(g)] == ["ist@x.com"]  # kalan tek yer; bursa@ gelecek hafta
    assert rapor["sessizlik"] == 1
    with oturum() as o:
        assert depo.eposta_sayisi(o, PAZARTESI) == 3


def test_haftalik_abone_de_alir(oturum):
    ilan_ekle(oturum, "https://a.test/1", "Yazılım Stajı", "Ankara", firma="Acme")
    sessiz_abone(oturum, "hafta@x.com", siklik="haftalik")
    g = SahteGonderici()
    rapor = bultenleri_gonder(oturum, g, AYAR, PAZARTESI)
    assert rapor["hazir_abone"] == 1 and rapor["bos"] == 1 and [e.alici for e in sessizlikler(g)] == ["hafta@x.com"]


def test_gonderilemeyen_sessizlik_kotayi_iade_eder_ve_hata_sayilir(oturum):
    ilan_ekle(oturum, "https://a.test/1", "Yazılım Stajı", "Ankara", firma="Acme")
    sessiz_abone(oturum, "bozuk@x.com")
    sessiz_abone(oturum, "saglam@x.com")
    g = SahteGonderici(hatali={"bozuk@x.com"})
    rapor = bultenleri_gonder(oturum, g, AYAR, PAZARTESI)
    assert rapor["sessizlik"] == 1 and rapor["hata"] == 1 and [e.alici for e in g.gidenler] == ["saglam@x.com"]
    with oturum() as o:
        assert depo.eposta_sayisi(o, PAZARTESI) == 1
    # Gönderilemeyen e-posta "alınmış" sayılmaz: aynı gün yeniden denenebilir
    yeniden = SahteGonderici()
    bultenleri_gonder(oturum, yeniden, AYAR, PAZARTESI + timedelta(hours=3))
    assert [e.alici for e in yeniden.gidenler] == ["bozuk@x.com"]
