"""Ara tarama: yalnızca ilan sistemleri, kariyer sayfaları dokunulmadan kalır; yapay zekâ yalnızca yeni ilan için; bülten yok;
veri değişmediyse commit (ve Vercel dağıtımı) yok."""

import json
from pathlib import Path

from internreader import __main__ as komut
from internreader import boru, depo
from internreader.ayar import ayarlari_oku
from internreader.db import Bulten, IlanKaydi
from internreader.model import Ilan
from internreader.yayin.json_disa import icerik_degisti
from internreader.yz.ayrinti_cikarici import IlanAyrintisi
from internreader.yz.siniflandirici import IlanSinifi, TopluSiniflandirma
from tests.conftest import SahteHttp, SahteYz

KOK = Path(__file__).resolve().parents[1]
AYAR = ayarlari_oku()


def lever_ilani(no: int, baslik: str = "Software Engineer Intern") -> dict:
    return {
        "text": f"{baslik} {no}",
        "hostedUrl": f"https://jobs.lever.co/acme/{no}",
        "categories": {"location": "Istanbul", "commitment": "Intern"},
        "createdAt": 1790000000000,
        "descriptionPlain": "Python öğrenci stajı.",
    }


def yz_cevabi(cagrilar: list[str]):
    def cevap(tur, mesaj):
        cagrilar.append(tur.__name__)
        if tur is TopluSiniflandirma:
            sonuclar = [
                IlanSinifi(no=n, seviye="staj", rol="yazilim", yapay_zeka="yok", gerekce="staj")
                for n in range(mesaj.count("[") if mesaj.count("[") else 1)
            ]
            return TopluSiniflandirma(sonuclar=sonuclar)
        return IlanAyrintisi(ozet="Staj.", calisma_modeli="belirsiz", ucretli="belirsiz", teknolojiler=["Python"])

    return cevap


def firmalari_kur(oturum):
    with oturum.begin() as o:
        depo.firma_ekle_veya_guncelle(o, "Acme", ats="lever", slug="acme", kaynak="elle")
        depo.firma_ekle_veya_guncelle(
            o, "Sayfa Firma", web="https://sayfa.test", kariyer="https://sayfa.test/kariyer", kaynak="elle"
        )


def test_kariyer_sayfasi_okunmaz_ilanlari_kapanmaz_yapay_zeka_yalnizca_yeni_ilana(oturum):
    firmalari_kur(oturum)
    sayfa_ilani = Ilan(firma="Sayfa Firma", baslik="Stajyer", url="https://sayfa.test/k#1", kaynak="kariyer_sayfasi")
    with oturum.begin() as o:
        depo.ilanlari_kaydet(o, [sayfa_ilani], set())
    http = SahteHttp(jsonlar={"api.lever.co": [lever_ilani(1)]})
    cagrilar: list[str] = []

    rapor = boru.tara(AYAR, oturum, http=http, yz=SahteYz(yz_cevabi(cagrilar)), yalnizca_ats=True)
    assert rapor.yalnizca_ats and rapor.ats_firma == 1 and rapor.sayfa_firma == 0 and rapor.yeni_ilan == 1
    assert all("sayfa.test" not in url for url, _, _ in http.istekler)  # kariyer sayfası indirilmedi
    assert cagrilar == ["TopluSiniflandirma"]
    with oturum() as o:
        assert o.get(IlanKaydi, sayfa_ilani.kimlik).aktif  # görülmedi diye kapanmadı

    # İkinci tur, yeni ilan yok: yapay zekâ çağrısı yok
    cagrilar.clear()
    assert boru.tara(AYAR, oturum, http=http, yz=SahteYz(yz_cevabi(cagrilar)), yalnizca_ats=True).yeni_ilan == 0
    assert cagrilar == []


def test_ayni_adli_firmanin_sayfa_ilani_ara_taramada_kapanmaz_ats_ilani_kapanir(oturum):
    firmalari_kur(oturum)
    karisik = Ilan(firma="Acme", baslik="Sayfadan", url="https://acme.test/k#1", kaynak="kariyer_sayfasi")
    with oturum.begin() as o:
        depo.ilanlari_kaydet(o, [karisik], set())
    birinci = SahteHttp(jsonlar={"api.lever.co": [lever_ilani(1), lever_ilani(2)]})
    boru.tara(AYAR, oturum, http=birinci, yz=SahteYz(yz_cevabi([])), yalnizca_ats=True)
    ikinci = SahteHttp(jsonlar={"api.lever.co": [lever_ilani(1)]})
    rapor = boru.tara(AYAR, oturum, http=ikinci, yz=SahteYz(yz_cevabi([])), yalnizca_ats=True)
    assert rapor.kapanan_ilan == 1  # panodan kalkan ATS ilanı kapanır
    with oturum() as o:
        assert o.get(IlanKaydi, karisik.kimlik).aktif


def test_anlik_404_ara_taramada_ilan_sistemi_kaydini_silmez_gunluk_tarama_siler(oturum):
    firmalari_kur(oturum)
    bos = SahteHttp()  # bilinmeyen adres: 404
    boru.tara(AYAR, oturum, http=bos, yz=SahteYz(yz_cevabi([])), yalnizca_ats=True)
    with oturum() as o:
        assert [f.ad for f in depo.aktif_firmalar(o) if f.ats == "lever"] == ["Acme"]
    boru.tara(AYAR, oturum, http=bos, yz=SahteYz(yz_cevabi([])))
    with oturum() as o:
        assert [f.ad for f in depo.aktif_firmalar(o) if f.ats == "lever"] == []


def test_ozetsiz_ayrinti_kariyer_sayfasi_okumaz(oturum):
    sayfa = Ilan(firma="Sayfa", baslik="Yazılım Stajı", url="https://sayfa.test/ilan", kaynak="kariyer_sayfasi")
    ats = Ilan(
        firma="Acme", baslik="Data Intern", url="https://jobs.lever.co/a/1", kaynak="lever", aciklama="Python stajı."
    )
    with oturum.begin() as o:
        depo.ilanlari_kaydet(o, [sayfa, ats], set())
        kararlar = {"seviye": "staj", "rol": "veri", "yapay_zeka": "yok"}
        depo.siniflandirma_kaydet(o, {sayfa.kimlik: kararlar, ats.kimlik: kararlar}, "test")
    http = SahteHttp()
    cagrilar: list[str] = []
    rapor = boru.ayrintilari_zenginlestir(AYAR, oturum, http=http, yz=SahteYz(yz_cevabi(cagrilar)), yalnizca_ats=True)
    assert rapor["bekleyen"] == 1 and rapor["cikarilan"] == 1 and http.istekler == []
    with oturum() as o:
        assert [i["kimlik"] for i in depo.ayrinti_bekleyenler(o)] == [sayfa.kimlik]  # sayfa ilanı sabaha kalır


def test_yayinla_ozetsiz_isareti_ilerletmez(oturum, tmp_path):
    i = Ilan(firma="Acme", baslik="Staj", url="https://j.test/1", kaynak="lever", konum="Istanbul")
    with oturum.begin() as o:
        depo.ilanlari_kaydet(o, [i], set())
        depo.siniflandirma_kaydet(o, {i.kimlik: {"seviye": "staj", "rol": "yazilim", "yapay_zeka": "yok"}}, "test")
    rapor = boru.yayinla(oturum, cikti_dizini=tmp_path, ozet_yaz=False)
    assert rapor["acik_ilan"] == 1 and rapor["whatsapp_dosyasi"] is None
    with oturum() as o:
        assert depo.durum_al(o, "son_whatsapp_ozeti") is None
        assert o.query(Bulten).count() == 0  # bülten gönderilmedi


def test_damga_tek_basina_degisiklik_sayilmaz():
    eski = {"surum": 1, "guncelleme": "2026-10-30T07:00:00+03:00", "sayi": 1, "ilanlar": [{"kimlik": "a"}]}
    assert not icerik_degisti(json.dumps({**eski, "guncelleme": "2026-10-30T13:00:00+03:00"}), json.dumps(eski))
    assert icerik_degisti(
        json.dumps({**eski, "sayi": 2, "ilanlar": [{"kimlik": "a"}, {"kimlik": "b"}]}), json.dumps(eski)
    )
    assert icerik_degisti(json.dumps(eski), None) and icerik_degisti(json.dumps(eski), "bozuk {")


def test_komut_damga_farkinda_false_yazar_veritabanina_baglanmaz(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("DATABASE_URL", "postgresql://baglanilmamali.invalid/x")
    eski, yeni = tmp_path / "eski.json", tmp_path / "yeni.json"
    govde = {"surum": 1, "guncelleme": "2026-10-30T07:00:00+03:00", "ilanlar": []}
    eski.write_text(json.dumps(govde), encoding="utf-8")
    yeni.write_text(json.dumps({**govde, "guncelleme": "2026-10-30T13:00:00+03:00"}), encoding="utf-8")
    assert komut.main(["ilanlar-degisti-mi", str(yeni), str(eski)]) == 0
    assert capsys.readouterr().out.strip() == "false"
    yeni.write_text(json.dumps({**govde, "ilanlar": [{"kimlik": "a"}]}), encoding="utf-8")
    komut.main(["ilanlar-degisti-mi", str(yeni), str(eski)])
    assert capsys.readouterr().out.strip() == "true"
    komut.main(["ilanlar-degisti-mi", str(yeni), str(tmp_path / "yok.json")])
    assert capsys.readouterr().out.strip() == "true"


def test_is_akisi_kurallari():
    metin = (KOK / ".github/workflows/ara_tarama.yml").read_text(encoding="utf-8")
    assert 'cron: "23 */6 * * *"' in metin and "group: internreader-veritabani" in metin
    assert "tara --yalnizca-ats --yz-tavani 0.05" in metin and "yayinla --ozetsiz" in metin
    assert "steps.fark.outputs.degisti == 'true'" in metin
    assert "calistir" not in metin and "bulten" not in metin and "SMTP" not in metin
    gunluk = (KOK / ".github/workflows/gunluk.yml").read_text(encoding="utf-8")
    assert "group: internreader-veritabani" in gunluk
