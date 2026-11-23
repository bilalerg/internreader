"""Resmî teknokent dizinlerinden aday çıkar; 50 firmalık kanıtlı, yazmasız pilot.

CSV'deki faal tarama kaydını değiştirmez. Dizinde görünmeyi faaliyet veya açık ilan kanıtı saymaz.
"""

import csv
import html
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import requests

from internreader.ag import HttpIstemci
from internreader.firma_faaliyeti import _adres_uygun, sayfa_kaniti
from internreader.kesif import kariyer_baglantilari, sayfadan_ats_bul

KOK = Path(__file__).resolve().parents[1]
CIKTI = KOK / "docs"
AJAN = "InternReaderBot/1.0 (+https://internreader.me)"
ITU = "https://firmalar.ariteknokent.com.tr"
YTU = "https://www.yildizteknopark.com.tr/firmalarimiz"
ALANLAR = {
    "oyun": ("game", "oyun"),
    "siber_guvenlik": ("cyber", "siber", "security", "güvenlik"),
    "savunma_robotik": ("defense", "defence", "savunma", "robot", "otonom", "havacılık"),
    "bulut_devops": ("cloud", "bulut", "devops", "kubernetes"),
    "veri_yapay_zeka": ("data", "veri", "artificial intelligence", "yapay zeka", "machine learning"),
    "yazilim": ("software", "yazılım", "saas", "api", "mobil uygulama"),
    "gomulu_iot": ("embedded", "gömülü", "iot", "fpga", "elektronik"),
}


def alan(url: str) -> str:
    try:
        return (urlsplit(url if "://" in url else f"https://{url}").hostname or "").lower().removeprefix("www.")
    except ValueError:
        return ""


def ad_anahtari(ad: str) -> str:
    ad = ad.replace("İ", "I").replace("ı", "i")
    ad = unicodedata.normalize("NFKD", ad).casefold()
    return "".join(c for c in ad if c.isalnum() and not unicodedata.combining(c))


def itu_kayitlari(metin: str) -> list[dict]:
    return [
        {"dizin": "itu_ari", "ad": html.unescape(ad.strip()), "web": "", "profil": url}
        for url, ad in re.findall(
            rf'<a href="({re.escape(ITU)}/companies/[^"/]+)"[^>]*>\s*'
            r'<span class="sr-only">(.*?) detaylarını görüntüle',
            metin,
            re.S,
        )
    ]


def ytu_kayitlari(metin: str) -> list[dict]:
    return [
        {"dizin": "ytu", "ad": html.unescape(re.sub(r"<[^>]+>", "", ad).strip()), "web": web, "profil": YTU}
        for web, ad in re.findall(
            r'<a href="([^"]*)"[^>]*>\s*<div class="service-block_six-inner">.*?'
            r'<div class="service-block_six-text">(.*?)</div>',
            metin,
            re.S,
        )
    ]


def indir(url: str) -> str:
    yanit = requests.get(url, headers={"User-Agent": AJAN}, timeout=20)
    yanit.raise_for_status()
    return yanit.content.decode("utf-8")


def itu_web(profil: str) -> str:
    try:
        metin = indir(profil)
        eslesme = re.search(r'Web Sitesi:</p>\s*<p><a href="([^"]+)"', metin)
        web = html.unescape(eslesme.group(1)) if eslesme else ""
        return web if not web or "://" in web else f"https://{web}"
    except requests.RequestException:
        return ""


def dizinleri_oku() -> tuple[list[dict], list[str]]:
    adresler = [("itu_ari", f"{ITU}/?page={s}") for s in range(1, 16)]
    adresler += [("ytu", YTU + (f"?per_page={s * 36}" if s else "")) for s in range(19)]
    hatalar = []

    def sayfa(oge):
        kaynak, url = oge
        try:
            metin = indir(url)
            kayitlar = itu_kayitlari(metin) if kaynak == "itu_ari" else ytu_kayitlari(metin)
            if not kayitlar:
                raise ValueError("firma kaydı okunamadı")
            return kayitlar, ""
        except (requests.RequestException, ValueError) as hata:
            return [], f"{url}: {type(hata).__name__}"

    with ThreadPoolExecutor(max_workers=5) as havuz:
        sonuc = list(havuz.map(sayfa, adresler))
    kayitlar = [kayit for liste, _ in sonuc for kayit in liste]
    hatalar = [hata for _, hata in sonuc if hata]
    for kayit in kayitlar:
        if kayit["web"] and "://" not in kayit["web"]:
            kayit["web"] = f"https://{kayit['web']}"
    itu = [kayit for kayit in kayitlar if kayit["dizin"] == "itu_ari"]
    with ThreadPoolExecutor(max_workers=5) as havuz:
        for kayit, web in zip(itu, havuz.map(itu_web, [k["profil"] for k in itu]), strict=True):
            kayit["web"] = web
    return kayitlar, hatalar


def eslestir(kayitlar: list[dict], firmalar: list[dict]) -> list[dict]:
    webden = {alan(f["web"]): f for f in firmalar if alan(f["web"])}
    addan = {ad_anahtari(f["ad"]): f for f in firmalar}
    for kayit in kayitlar:
        web = alan(kayit["web"])
        firma = (webden.get(web) if web else None) or addan.get(ad_anahtari(kayit["ad"]))
        kayit["csv_adi"] = firma["ad"] if firma else ""
        kayit["eslesme"] = "alan_adi" if firma and web and alan(firma["web"]) == web else "ad" if firma else "aday"
        kayit["ilan_kaynagi"] = (firma["ats"] or firma["kariyer"]) if firma else ""
    return kayitlar


def pilot_secenekleri(kayitlar: list[dict], sinir: int) -> list[dict]:
    # Mevcut kaynaksızları ve yeni adayları örnekle; küçük firmaları yalnızca adından dolayı eleme.
    secilen, gorulen = [], set()
    gruplar = [("itu_ari", True, 15), ("itu_ari", False, 15), ("ytu", False, 20)]
    for dizin, yeni, hedef in gruplar:
        adaylar = [
            k
            for k in kayitlar
            if k["dizin"] == dizin and bool(k["csv_adi"]) != yeni and k["web"] and not k["ilan_kaynagi"]
        ]
        adaylar.sort(key=lambda k: ad_anahtari(k["ad"]))
        alinan = 0
        for kayit in adaylar:
            web = alan(kayit["web"])
            if not web or web in gorulen or not _adres_uygun(kayit["web"]):
                continue
            gorulen.add(web)
            secilen.append(kayit)
            alinan += 1
            if alinan >= hedef:
                break
    return secilen[:sinir]


def firmayi_kontrol_et(kayit: dict) -> dict:
    sonuc = {
        **kayit,
        "site_durumu": "",
        "alan_sinyali": "",
        "faaliyet": "belirsiz",
        "neden": "",
        "kanit": "",
        "kariyer_adayi": "",
        "ats_adayi": "",
    }
    try:
        http = HttpIstemci(AJAN, zaman_asimi=10)
        son_url, metin = http.sayfa(kayit["web"])
        kanit = sayfa_kaniti(kayit["web"], son_url, metin, datetime.now(UTC))
        kariyer = kariyer_baglantilari(son_url, metin)
        ats, slug = sayfadan_ats_bul(metin)
        tanitim = " ".join(
            " ".join(eslesme)
            for eslesme in re.findall(
                r"(?is)<title[^>]*>(.*?)</title>|<meta[^>]+name=[\"']description[\"'][^>]+content=[\"']([^\"']+)",
                metin,
            )
        )
        sinyaller = [ad for ad, kelimeler in ALANLAR.items() if any(k in tanitim.casefold() for k in kelimeler)]
        sonuc.update(
            site_durumu="acildi",
            alan_sinyali=",".join(sinyaller),
            faaliyet=kanit.durum,
            neden=kanit.neden,
            kanit=kanit.kanit_url or "",
            kariyer_adayi=kariyer[0] if kariyer else "",
            ats_adayi=f"{ats}:{slug}" if ats else "",
        )
    except Exception as hata:
        sonuc.update(site_durumu="erisilemedi", neden=type(hata).__name__)
    return sonuc


def csv_yaz(yol: Path, kayitlar: list[dict], alanlar: list[str]) -> None:
    with yol.open("w", encoding="utf-8-sig", newline="") as dosya:
        yazici = csv.DictWriter(dosya, fieldnames=alanlar, extrasaction="ignore")
        yazici.writeheader()
        yazici.writerows(kayitlar)


def main() -> None:
    dizinler, hatalar = dizinleri_oku()
    with (CIKTI / "teknopark_istanbul_dizini_2026-11-23.csv").open(encoding="utf-8", newline="") as dosya:
        dizinler.extend(
            {
                "dizin": "teknopark_istanbul",
                "ad": satir["ad"],
                "web": "",
                "profil": "https://www.teknoparkistanbul.com.tr/firma-katalogu",
                "kategoriler": satir["kategoriler"],
            }
            for satir in csv.DictReader(dosya)
        )
    with (KOK / "veri/firmalar.csv").open(encoding="utf-8-sig", newline="") as dosya:
        firmalar = list(csv.DictReader(dosya))
    kayitlar = eslestir(dizinler, firmalar)
    csv_yaz(
        CIKTI / "teknokent_dizinleri_2026-11-23.csv",
        kayitlar,
        ["dizin", "ad", "web", "profil", "kategoriler", "csv_adi", "eslesme", "ilan_kaynagi"],
    )
    secilen = pilot_secenekleri(kayitlar, 50)
    with ThreadPoolExecutor(max_workers=8) as havuz:
        pilot = list(havuz.map(firmayi_kontrol_et, secilen))
    csv_yaz(
        CIKTI / "teknokent_pilotu_2026-11-23.csv",
        pilot,
        [
            "dizin",
            "ad",
            "web",
            "profil",
            "csv_adi",
            "eslesme",
            "site_durumu",
            "alan_sinyali",
            "faaliyet",
            "neden",
            "kanit",
            "kariyer_adayi",
            "ats_adayi",
        ],
    )
    print(
        {
            "dizin_kaydi": len(dizinler),
            "itu": sum(k["dizin"] == "itu_ari" for k in dizinler),
            "ytu": sum(k["dizin"] == "ytu" for k in dizinler),
            "teknopark_istanbul": sum(k["dizin"] == "teknopark_istanbul" for k in dizinler),
            "eslesen": sum(bool(k["csv_adi"]) for k in kayitlar),
            "pilot": len(pilot),
            "acilan": sum(k["site_durumu"] == "acildi" for k in pilot),
            "kariyer_adayi": sum(bool(k["kariyer_adayi"]) for k in pilot),
            "ats_adayi": sum(bool(k["ats_adayi"]) for k in pilot),
            "hatalar": hatalar,
        }
    )


if __name__ == "__main__":
    main()
