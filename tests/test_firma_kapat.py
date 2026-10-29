from sqlalchemy import select

from internreader import depo
from internreader.db import Firma, IlanKaydi
from internreader.model import Ilan


def test_firma_kapatilinca_ilanlari_yayindan_kalkar_ve_ice_aktarma_geri_getirmez(oturum):
    with oturum.begin() as o:
        depo.firma_ekle_veya_guncelle(o, "Acme Teknoloji", web="https://www.acme.com")
        depo.firma_ekle_veya_guncelle(o, "Beta", web="https://beta.io")
        ilanlar = [
            Ilan(firma=f, baslik="Stajyer", url=f"https://{f}/1", kaynak="lever") for f in ("Acme Teknoloji", "Beta")
        ]
        depo.ilanlari_kaydet(o, ilanlar, {"Acme Teknoloji", "Beta"})
    with oturum.begin() as o:
        assert depo.firmayi_kapat(o, "acme.com") == 1  # alan adıyla da bulunur
        assert depo.firmayi_kapat(o, "Olmayan Firma") == 0
    with oturum.begin() as o:
        depo.firma_ekle_veya_guncelle(o, "Acme Teknoloji", web="https://www.acme.com")  # liste yeniden içe aktarıldı
    with oturum() as o:
        aktif = {f.ad: f.aktif for f in o.scalars(select(Firma))}
        ilan_aktif = {i.firma: i.aktif for i in o.scalars(select(IlanKaydi))}
        taranacak = {f.ad for f in depo.aktif_firmalar(o)}
    assert aktif == {"Acme Teknoloji": False, "Beta": True}
    assert ilan_aktif == {"Acme Teknoloji": False, "Beta": True}
    assert taranacak == {"Beta"}
