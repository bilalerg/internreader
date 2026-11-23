"""Mevcut ve keşfedilmiş kariyer adreslerinin erişilebilirliğini denetle."""

import csv
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

from internreader.ag import HttpIstemci, RobotsEngeli, hata_ozeti
from internreader.firma_faaliyeti import _adres_uygun

KOK = Path(__file__).resolve().parents[1]
GIRDI = KOK / "docs/firma_deneti_tam_2026-11-23.csv"
CIKTI = KOK / "docs/kariyer_baglantisi_kontrol_2026-11-23.csv"
ALANLAR = ["firma", "kaynak_tipi", "adres", "durum", "son_url", "neden"]


def kontrol(kayit: dict, http: HttpIstemci) -> dict:
    adres = kayit["kariyer"] or kayit["kariyer_adayi"]
    sonuc = {
        "firma": kayit["ad"],
        "kaynak_tipi": "csv" if kayit["kariyer"] else "aday",
        "adres": adres,
        "durum": "",
        "son_url": "",
        "neden": "",
    }
    if not _adres_uygun(adres):
        sonuc.update(durum="gecersiz_veya_yasak", neden="adres_politikasi")
        return sonuc
    try:
        son_url, _ = http.sayfa(adres, adres_izinli=_adres_uygun)
        sonuc.update(durum="acildi", son_url=son_url)
    except RobotsEngeli:
        sonuc.update(durum="robots_veya_adres_engeli", neden="robots_veya_adres_engeli")
    except requests.RequestException as hata:
        sonuc.update(durum="erisilemedi", neden=hata_ozeti(hata))
    except (ValueError, UnicodeError):
        sonuc.update(durum="okunamadi", neden="sayfa_okunamadi")
    return sonuc


def main() -> None:
    with GIRDI.open(encoding="utf-8-sig", newline="") as dosya:
        kaynaklar = [x for x in csv.DictReader(dosya) if x["kariyer"] or x["kariyer_adayi"]]
    http = HttpIstemci("InternReaderBot/1.0 (+https://internreader.me)", zaman_asimi=10, havuz_boyutu=24)
    with ThreadPoolExecutor(max_workers=24) as havuz:
        isler = [havuz.submit(kontrol, x, http) for x in kaynaklar]
        with CIKTI.open("w", encoding="utf-8-sig", newline="") as dosya:
            yazici = csv.DictWriter(dosya, fieldnames=ALANLAR)
            yazici.writeheader()
            for islem in as_completed(isler):
                yazici.writerow(islem.result())
                dosya.flush()
    with CIKTI.open(encoding="utf-8-sig", newline="") as dosya:
        sonuc = list(csv.DictReader(dosya))
    print({"kaynak": len(sonuc), "durum": dict(Counter(x["durum"] for x in sonuc))})


if __name__ == "__main__":
    main()
