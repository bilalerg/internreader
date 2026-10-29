"""Komut satırı arayüzü.

Kullanım (proje klasöründe):
  python -m internreader ice-aktar veri/firmalar.csv     firma listesini veritabanına al
  python -m internreader kesif [--yokla] [--kaynak K]    firmaların ilan sistemini / kariyer sayfasını bul (ayda bir)
  python -m internreader arama-kesif [--kuru] [--web-bul N]  arama API'siyle yeni firma bul (haftada bir; anahtar ister)
  python -m internreader firma-kapat "Acme"               "ilanımı kaldır" talebi: firmayı taramadan ve yayından çıkar
  python -m internreader tara [--yz-tavani 0.50]         ilanları topla + sınıflandır
  python -m internreader yayinla                         README tablosu, JSON ve WhatsApp özeti üret
  python -m internreader bulten-gonder                  abonelere kişiye özel bülten (SMTP yoksa dosyaya yazar)
  python -m internreader bakim                           süresi dolan kayıtları temizle
  python -m internreader calistir                        tara + yayinla + bülten + bakım (sunucunun her sabahki işi)
  python -m internreader durum                           veritabanı özeti, yapay zekâ harcaması, bülten sayıları
  python -m internreader api [--port 8000]               sitenin abonelik API'si (geliştirme sunucusu)
  python -m internreader degerlendir                     sınıflandırıcı doğruluğu (etiketli set; ~0,002 $)
  python -m internreader goc-uret "açıklama"             model değişikliğinden yeni veritabanı göçü üret (geliştirici)
"""

import argparse
import dataclasses
import json
import logging
from datetime import date
from pathlib import Path

from internreader import boru, depo
from internreader.arama import arama_kesfi, web_adresi_bul
from internreader.ayar import CIKTI, VERI, ayarlari_oku
from internreader.bakim import bakim_yap
from internreader.bulten import bultenleri_gonder
from internreader.db import oturum_fabrikasi
from internreader.eposta import gonderici_olustur
from internreader.gunluk import kayit_kur
from internreader.ice_aktar import eski_onbellegi_ice_aktar, firmalari_ice_aktar
from internreader.kesif import kesfet
from internreader.yz.degerlendirme import degerlendir, seti_oku

kayit = logging.getLogger("internreader")


def main(argv: list[str] | None = None) -> int:
    ayristirici = argparse.ArgumentParser(prog="internreader", description="Türkiye staj ilanı toplayıcı")
    ayristirici.add_argument("--ayrinti", action="store_true", help="ayrıntılı kayıt (DEBUG)")
    alt = ayristirici.add_subparsers(dest="komut", required=True)

    p = alt.add_parser("ice-aktar", help="firma CSV'sini veritabanına al")
    p.add_argument("csv", type=Path)
    p.add_argument("--kaynak", default="")
    p.add_argument("--eski-onbellek", type=Path, default=None, help="v0.1'in sayfa_onbellek.json dosyası (tek sefer)")

    p = alt.add_parser("kesif", help="ilan sistemi ve kariyer sayfası keşfi")
    p.add_argument("--sinir", type=int, default=None)
    p.add_argument("--yokla", action="store_true", help="ATS API'lerini firma adından tahminle yokla (yavaş)")
    p.add_argument("--kaynak", default=None, help="yalnızca bu kaynaktan gelen firmalar (ör. tohum_1810)")

    p = alt.add_parser("arama-kesif", help="arama API'siyle listede olmayan firmaları bul (haftada bir)")
    p.add_argument("--sorgu-siniri", type=int, default=None, help="en fazla kaç sorgu atılsın (kota denemesi için)")
    p.add_argument("--kuru", action="store_true", help="hiçbir şey yazma, yalnızca bulunacakları raporla")
    p.add_argument("--web-bul", type=int, default=0, metavar="N", help="ayrıca adresi olmayan N firmaya web adresi ara")
    p = alt.add_parser("firma-kapat", help='"ilanımı kaldır" talebi: firmayı taramadan ve yayından çıkar')
    p.add_argument("firma", help='firma adı ("Acme Teknoloji") ya da alan adı ("acme.com")')

    for ad in ("tara", "calistir"):
        p = alt.add_parser(ad)
        p.add_argument(
            "--yz-tavani", type=float, default=None, help="bu çalıştırma için en fazla yapay zekâ harcaması ($)"
        )
    p = alt.add_parser("yayinla")
    p.add_argument("--liste-linki", default="", help="WhatsApp özetinin sonuna eklenecek tam liste adresi")
    alt.add_parser("durum")
    alt.add_parser("bulten-gonder", help="abonelere kişiye özel bülten")
    alt.add_parser("bakim", help="süresi dolan kayıtları temizle")
    p = alt.add_parser("degerlendir", help="sınıflandırıcının doğruluğunu etiketli sette ölç (~0,002 $)")
    p.add_argument("--set", type=Path, default=VERI / "degerlendirme" / "siniflandirma.jsonl")
    p = alt.add_parser("goc-uret", help="model değişikliğinden veritabanı göçü üret")
    p.add_argument("aciklama")
    p = alt.add_parser("api", help="abonelik API'sini başlat (geliştirme)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)

    arg = ayristirici.parse_args(argv)
    kayit_kur("DEBUG" if arg.ayrinti else "INFO")
    ayar = ayarlari_oku()
    if getattr(arg, "yz_tavani", None) is not None:
        ayar = dataclasses.replace(ayar, calisma_basina_yz_tavani_usd=arg.yz_tavani)
    if arg.komut == "goc-uret":
        return _goc_uret(ayar.veritabani_url, arg.aciklama)
    oturum = oturum_fabrikasi(ayar.veritabani_url)

    if arg.komut == "ice-aktar":
        firmalari_ice_aktar(oturum, arg.csv, arg.kaynak)
        if arg.eski_onbellek:
            eski_onbellegi_ice_aktar(oturum, arg.eski_onbellek)
    elif arg.komut == "kesif":
        kesfet(ayar, oturum, arg.sinir, arg.yokla, arg.kaynak)
    elif arg.komut == "arama-kesif":
        rapor = {"arama": arama_kesfi(ayar, oturum, arg.sorgu_siniri, arg.kuru)}
        if arg.web_bul:
            rapor["web_bul"] = web_adresi_bul(ayar, oturum, arg.web_bul, kuru=arg.kuru)
        print(json.dumps(rapor, ensure_ascii=False, indent=1))
    elif arg.komut == "firma-kapat":
        with oturum.begin() as o:
            sayi = depo.firmayi_kapat(o, arg.firma)
        print(f"{sayi} firma kapatıldı." if sayi else f'"{arg.firma}" bulunamadı (ad ya da alan adını kontrol edin).')
        if sayi:
            boru.yayinla(oturum)  # README/JSON hemen güncellensin; site sabah derlemesinde güncellenir
        return 0 if sayi else 1
    elif arg.komut in ("tara", "calistir"):
        yz = boru.yz_olustur(ayar, oturum)  # tarama ve ayrıntılar aynı bütçeyi paylaşır
        rapor = boru.tara(ayar, oturum, yz=yz)
        if rapor.hatalar:
            kayit.warning("Ulaşılamayan ilan sistemleri: %s", "; ".join(rapor.hatalar))
        if arg.komut == "calistir":
            boru.ayrintilari_zenginlestir(ayar, oturum, yz=yz)
            boru.yayinla(oturum)
            bultenleri_gonder(oturum, gonderici_olustur(ayar), ayar)
            bakim_yap(oturum)
    elif arg.komut == "bulten-gonder":
        print(json.dumps(bultenleri_gonder(oturum, gonderici_olustur(ayar), ayar), ensure_ascii=False, indent=1))
    elif arg.komut == "degerlendir":
        yz = boru.yz_olustur(ayar, oturum)
        sonuc = degerlendir(yz, seti_oku(arg.set))
        with oturum.begin() as o:
            depo.kullanim_yaz(o, yz.kullanimlar)
        metin = json.dumps(sonuc, ensure_ascii=False, indent=1)
        CIKTI.mkdir(exist_ok=True)
        (CIKTI / f"degerlendirme_{date.today().isoformat()}.json").write_text(metin, encoding="utf-8", newline="\n")
        print(metin)
    elif arg.komut == "bakim":
        print(json.dumps(bakim_yap(oturum), ensure_ascii=False, indent=1))
    elif arg.komut == "yayinla":
        print(json.dumps(boru.yayinla(oturum, tam_liste_linki=arg.liste_linki), ensure_ascii=False, indent=1))
    elif arg.komut == "api":
        import uvicorn  # yalnızca bu komutta gerekir

        uvicorn.run("internreader.api:uygulama", factory=True, host=arg.host, port=arg.port, proxy_headers=True)
    elif arg.komut == "durum":
        with oturum() as o:
            print(json.dumps(depo.istatistik(o), ensure_ascii=False, indent=1))
    return 0


def _goc_uret(veritabani_url: str, aciklama: str) -> int:
    """Modelleri veritabanının güncel şemasıyla karşılaştırıp yeni bir göç dosyası üretir. Dosya mutlaka gözden
    geçirilmeli: ör. boş olamayan yeni kolon için server_default gerekir (dolu tabloda göç yoksa patlar)."""
    from alembic import command

    from internreader.db import motor_olustur
    from internreader.sema import alembic_ayari, semayi_hazirla

    motor = motor_olustur(veritabani_url)
    semayi_hazirla(motor)  # önce mevcut göçler uygulanmış olmalı
    with motor.begin() as baglanti:
        command.revision(alembic_ayari(baglanti), message=aciklama, autogenerate=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
