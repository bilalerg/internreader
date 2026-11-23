"""CSV'deki tüm firmalara kanıtlı, kaldığı yerden süren site denetimi uygula.

Çıktı üretim listesini değiştirmez. Açılmayan site, şirketin kapandığını kanıtlamaz.
"""

import argparse
import csv
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

import requests

from internreader.ag import HttpIstemci, RobotsEngeli, hata_ozeti
from internreader.firma_faaliyeti import _adres_uygun, sayfa_kaniti
from internreader.kesif import kariyer_baglantilari, sayfadan_ats_bul

KOK = Path(__file__).resolve().parents[1]
GIRDI = KOK / "veri/firmalar.csv"
CIKTI = KOK / "docs/firma_deneti_tam_2026-11-23.csv"
AJAN = "InternReaderBot/1.0 (+https://internreader.me)"
ALANLAR = [
    "sira",
    "ad",
    "web",
    "ats",
    "slug",
    "kariyer",
    "etiket",
    "kaynak",
    "kontrol_zamani",
    "site_durumu",
    "son_url",
    "faaliyet_durumu",
    "neden",
    "kanit_url",
    "kanit_tarihi",
    "kariyer_adayi",
    "ats_adayi",
]


def denetle(sira: int, firma: dict, http: HttpIstemci) -> dict:
    sonuc = {
        **firma,
        "sira": sira,
        "kontrol_zamani": datetime.now(UTC).isoformat(),
        "site_durumu": "",
        "son_url": "",
        "faaliyet_durumu": "belirsiz",
        "neden": "",
        "kanit_url": "",
        "kanit_tarihi": "",
        "kariyer_adayi": "",
        "ats_adayi": "",
    }
    url = firma["web"].strip()
    if not url or not _adres_uygun(url):
        sonuc.update(site_durumu="web_yok_veya_gecersiz", neden="gecerli_web_adresi_yok")
        return sonuc
    try:
        son_url, html = http.sayfa(url, adres_izinli=_adres_uygun)
        kanit = sayfa_kaniti(url, son_url, html, datetime.now(UTC))
        kariyer = kariyer_baglantilari(son_url, html)
        ats, slug = sayfadan_ats_bul(html)
        sonuc.update(
            site_durumu="acildi",
            son_url=son_url,
            faaliyet_durumu=kanit.durum,
            neden=kanit.neden,
            kanit_url=kanit.kanit_url or "",
            kanit_tarihi=kanit.kanit_tarihi.isoformat() if kanit.kanit_tarihi else "",
            kariyer_adayi=kariyer[0] if kariyer else "",
            ats_adayi=f"{ats}:{slug}" if ats else "",
        )
    except RobotsEngeli:
        sonuc.update(site_durumu="robots_veya_adres_engeli", neden="robots_veya_adres_engeli")
    except requests.RequestException as hata:
        sonuc.update(site_durumu="erisilemedi", neden=hata_ozeti(hata))
    except (ValueError, UnicodeError):
        sonuc.update(site_durumu="okunamadi", neden="sayfa_okunamadi")
    return sonuc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--is-parcacigi", type=int, default=16)
    parser.add_argument("--sinir", type=int, default=0, help="0: tüm şirketler")
    args = parser.parse_args()
    if not 1 <= args.is_parcacigi <= 32 or args.sinir < 0:
        parser.error("geçersiz iş parçacığı veya sınır")
    with GIRDI.open(encoding="utf-8-sig", newline="") as dosya:
        firmalar = list(csv.DictReader(dosya))
    if args.sinir:
        firmalar = firmalar[: args.sinir]
    CIKTI.parent.mkdir(exist_ok=True)
    var_olan = {}
    if CIKTI.exists():
        with CIKTI.open(encoding="utf-8-sig", newline="") as dosya:
            var_olan = {int(satir["sira"]): satir for satir in csv.DictReader(dosya)}
    # Girdi değiştiyse eski sonucu sessizce kullanma.
    var_olan = {
        sira: satir
        for sira, satir in var_olan.items()
        if sira <= len(firmalar)
        and satir["ad"] == firmalar[sira - 1]["ad"]
        and satir["web"] == firmalar[sira - 1]["web"]
    }
    kilit = threading.Lock()
    http = HttpIstemci(AJAN, zaman_asimi=12, havuz_boyutu=args.is_parcacigi)
    with CIKTI.open("w", encoding="utf-8-sig", newline="") as dosya:
        yazici = csv.DictWriter(dosya, fieldnames=ALANLAR, extrasaction="ignore")
        yazici.writeheader()
        for satir in var_olan.values():
            yazici.writerow(satir)
        dosya.flush()
        with ThreadPoolExecutor(max_workers=args.is_parcacigi) as havuz:
            isler = [
                havuz.submit(denetle, sira, firma, http)
                for sira, firma in enumerate(firmalar, 1)
                if sira not in var_olan
            ]
            for tamamlanan in as_completed(isler):
                sonuc = tamamlanan.result()
                with kilit:
                    yazici.writerow(sonuc)
                    dosya.flush()
    with CIKTI.open(encoding="utf-8-sig", newline="") as dosya:
        satirlar = list(csv.DictReader(dosya))
    print(
        {
            "toplam": len(firmalar),
            "denetlenen": len(satirlar),
            "site": dict(Counter(s["site_durumu"] for s in satirlar)),
            "faaliyet": dict(Counter(s["faaliyet_durumu"] for s in satirlar)),
        }
    )


if __name__ == "__main__":
    main()
