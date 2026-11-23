"""Tam site denetimini, kanıt düzeyine göre inceleme sırasına çevir."""

import csv
from collections import Counter, defaultdict
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
GIRDI = KOK / "docs/firma_deneti_tam_2026-11-23.csv"
DIZIN = KOK / "docs/teknokent_dizinleri_2026-11-23.csv"
TEKRAR = KOK / "docs/firma_erisim_ikinci_kontrol_2026-11-23.csv"
KARIYER = KOK / "docs/kariyer_baglantisi_kontrol_2026-11-23.csv"
GUNCEL = KOK / "veri/firmalar.csv"
CIKTI = KOK / "docs/firma_temizlik_oncelikleri_2026-11-23.csv"


def karar(satir: dict) -> tuple[int, str]:
    if satir["faaliyet_durumu"] == "adres_sorunlu":
        return 1, "alan_adini_elle_dogrula"
    if satir["site_durumu"] == "web_yok_veya_gecersiz":
        return (2, "ats_veya_kariyeri_dogrula") if satir["ats"] or satir["kariyer"] else (2, "kaynak_bul")
    if satir["site_durumu"] in {"erisilemedi", "robots_veya_adres_engeli", "okunamadi"}:
        return 3, "tekrar_ve_elle_kontrol"
    if satir["faaliyet_durumu"] == "faal":
        return 6, "tarihli_faaliyet_kaniti_var"
    if satir["ats"] or satir["kariyer"] or satir["kariyer_adayi"] or satir["ats_adayi"]:
        return 4, "ilan_kaynagini_dogrula"
    return 5, "faaliyet_ve_ilan_kaynagi_ara"


def main() -> None:
    with GIRDI.open(encoding="utf-8-sig", newline="") as dosya:
        firmalar = list(csv.DictReader(dosya))
    with DIZIN.open(encoding="utf-8-sig", newline="") as dosya:
        dizinler = list(csv.DictReader(dosya))
    with TEKRAR.open(encoding="utf-8-sig", newline="") as dosya:
        tekrar = {x["sira"]: x for x in csv.DictReader(dosya)}
    with KARIYER.open(encoding="utf-8-sig", newline="") as dosya:
        kariyer = {x["firma"]: x for x in csv.DictReader(dosya)}
    with GUNCEL.open(encoding="utf-8-sig", newline="") as dosya:
        guncel = {x["ad"]: x for x in csv.DictReader(dosya)}
    eslesmeler = defaultdict(set)
    for kayit in dizinler:
        if kayit["csv_adi"]:
            eslesmeler[kayit["csv_adi"]].add(kayit["dizin"])
    for satir in firmalar:
        satir["ilk_site_durumu"] = satir["site_durumu"]
        satir["ilk_neden"] = satir["neden"]
        satir["ikinci_kontrol_url"] = ""
        if (sonuc := tekrar.get(satir["sira"])) and sonuc["durum"] == "acildi":
            satir.update(
                site_durumu="acildi",
                son_url=sonuc["son_url"],
                faaliyet_durumu=sonuc["faaliyet_durumu"],
                neden=sonuc["faaliyet_neden"],
                kanit_url=sonuc["kanit_url"],
                ikinci_kontrol_url=sonuc["son_url"],
            )
        satir["guncel_web"] = guncel[satir["ad"]]["web"]
        satir["guncel_kariyer"] = guncel[satir["ad"]]["kariyer"]
        satir["kariyer_kontrol"] = kariyer.get(satir["ad"], {}).get("durum", "")
        oncelik, eylem = karar(satir)
        if satir["kariyer"] and satir["kariyer_kontrol"] not in {"", "acildi"}:
            oncelik, eylem = (
                (7, "kariyer_adresi_duzeltildi")
                if satir["guncel_kariyer"] != satir["kariyer"]
                else (1, "kariyer_adresini_incele")
            )
        if satir["ilk_neden"] == "alan_adi_satis_veya_park" and satir["guncel_web"] != satir["web"]:
            oncelik, eylem = 7, "eski_adres_duzeltildi"
        satir.update(oncelik=oncelik, eylem=eylem, guncel_dizin_eslesmesi=";".join(sorted(eslesmeler[satir["ad"]])))
    firmalar.sort(key=lambda x: (x["oncelik"], x["ad"].casefold()))
    with CIKTI.open("w", encoding="utf-8-sig", newline="") as dosya:
        yazici = csv.DictWriter(
            dosya,
            fieldnames=[
                "oncelik",
                "eylem",
                "guncel_dizin_eslesmesi",
                *[x for x in firmalar[0] if x not in {"oncelik", "eylem", "guncel_dizin_eslesmesi"}],
            ],
        )
        yazici.writeheader()
        yazici.writerows(firmalar)
    print(
        {
            "firma": len(firmalar),
            "eylem": dict(Counter(x["eylem"] for x in firmalar)),
            "guncel_dizinde": sum(bool(x["guncel_dizin_eslesmesi"]) for x in firmalar),
        }
    )


if __name__ == "__main__":
    main()
