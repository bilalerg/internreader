"""İlk taramada erişilemeyen şirket sitelerini alternatif kök adreslerle tekrar dene."""

import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import requests

from internreader.ag import HttpIstemci, RobotsEngeli, hata_ozeti
from internreader.firma_faaliyeti import _adres_uygun, sayfa_kaniti

KOK = Path(__file__).resolve().parents[1]
GIRDI = KOK / "docs/firma_deneti_tam_2026-11-23.csv"
CIKTI = KOK / "docs/firma_erisim_ikinci_kontrol_2026-11-23.csv"
ALANLAR = [
    "sira",
    "ad",
    "eski_web",
    "eski_neden",
    "denenen",
    "durum",
    "son_url",
    "faaliyet_durumu",
    "faaliyet_neden",
    "kanit_url",
]


def alternatifler(url: str) -> list[str]:
    p = urlsplit(url)
    host = p.hostname or ""
    hosts = [host.removeprefix("www.") if host.startswith("www.") else f"www.{host}", host]
    semalar = [p.scheme, "http" if p.scheme == "https" else "https"]
    sonuc = []
    for sema, alan in zip(semalar, hosts, strict=True):
        yeni = urlunsplit((sema, alan, "/", "", ""))
        if yeni != url and _adres_uygun(yeni) and yeni not in sonuc:
            sonuc.append(yeni)
    return sonuc


def denetle(satir: dict, http: HttpIstemci) -> dict:
    sonuc = {
        "sira": satir["sira"],
        "ad": satir["ad"],
        "eski_web": satir["web"],
        "eski_neden": satir["neden"],
        "denenen": "",
        "durum": "erisilemedi",
        "son_url": "",
        "faaliyet_durumu": "belirsiz",
        "faaliyet_neden": "",
        "kanit_url": "",
    }
    for url in alternatifler(satir["web"]):
        sonuc["denenen"] += (";" if sonuc["denenen"] else "") + url
        try:
            son_url, html = http.sayfa(url, adres_izinli=_adres_uygun)
            kanit = sayfa_kaniti(url, son_url, html, datetime.now(UTC))
            sonuc.update(
                durum="acildi",
                son_url=son_url,
                faaliyet_durumu=kanit.durum,
                faaliyet_neden=kanit.neden,
                kanit_url=kanit.kanit_url or "",
            )
            break
        except (requests.RequestException, RobotsEngeli, ValueError, UnicodeError) as hata:
            sonuc["faaliyet_neden"] = hata_ozeti(hata)
    return sonuc


def main() -> None:
    with GIRDI.open(encoding="utf-8-sig", newline="") as dosya:
        satirlar = [
            x
            for x in csv.DictReader(dosya)
            if x["site_durumu"] == "erisilemedi"
            and x["neden"] in {"SSLError", "ConnectionError", "RetryError", "HTTPError 404"}
        ]
    http = HttpIstemci("InternReaderBot/1.0 (+https://internreader.me)", zaman_asimi=8, havuz_boyutu=24)
    with ThreadPoolExecutor(max_workers=24) as havuz:
        isler = [havuz.submit(denetle, x, http) for x in satirlar]
        with CIKTI.open("w", encoding="utf-8-sig", newline="") as dosya:
            yazici = csv.DictWriter(dosya, fieldnames=ALANLAR)
            yazici.writeheader()
            for islem in as_completed(isler):
                yazici.writerow(islem.result())
                dosya.flush()
    with CIKTI.open(encoding="utf-8-sig", newline="") as dosya:
        sonuclar = list(csv.DictReader(dosya))
    print({"tekrar_bakilan": len(sonuclar), "acilan": sum(x["durum"] == "acildi" for x in sonuclar)})


if __name__ == "__main__":
    main()
