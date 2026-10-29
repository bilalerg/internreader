from sqlalchemy import select

from internreader.db import IlanKaydi
from internreader.depo import ilanlari_kaydet
from internreader.isleme.maske import kisisel_veriyi_maskele
from internreader.model import Ilan


def test_kisisel_eposta_maskelenir_rol_adresi_korunur():
    metin = "CV'nizi ik@acme.com.tr adresine, sorularınızı ayse.yilmaz@acme.com.tr adresine iletin. careers@acme.io"
    sonuc = kisisel_veriyi_maskele(metin)
    assert "ik@acme.com.tr" in sonuc and "careers@acme.io" in sonuc
    assert "ayse.yilmaz" not in sonuc and "[e-posta]" in sonuc


def test_telefon_bicimleri_maskelenir():
    for numara in ("+90 532 123 45 67", "0216 555 12 34", "(0532) 123-45-67", "5321234567", "0850.222.33.44"):
        assert kisisel_veriyi_maskele(f"Tel: {numara}.") == "Tel: [telefon].", numara


def test_telefon_olmayan_sayilar_bozulmaz():
    metin = "Son başvuru 2026-10-29, maaş 35.000 TL, ISO 27001, Python 3.12, ilan no 527260"
    assert kisisel_veriyi_maskele(metin) == metin


def test_veritabanina_maskelenmis_metin_yazilir(oturum):
    ilan = Ilan(
        firma="Acme",
        baslik="Stajyer",
        url="https://acme.com/1",
        kaynak="lever",
        aciklama="Bilgi için Mehmet Bey: 0532 123 45 67, mehmet@acme.com",
    )
    with oturum.begin() as o:
        ilanlari_kaydet(o, [ilan], {"Acme"})
    with oturum() as o:
        aciklama = o.scalar(select(IlanKaydi.aciklama))
    assert aciklama == "Bilgi için Mehmet Bey: [telefon], [e-posta]"
