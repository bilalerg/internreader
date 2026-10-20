"""Konum metninden şehir çıkarma ("Sarıyer, Istanbul" → istanbul).

Sitedeki şehir filtresi ve Türkiye haritası bu anahtarları kullanır. Anahtarlar sabittir (sitenin veri sözleşmesi);
yeni şehir eklemek serbest, var olanın adını değiştirmek değil.
"""

import re

# anahtar → (görünen ad, konum metninde arama deseni)
SEHIRLER: dict[str, tuple[str, re.Pattern]] = {
    anahtar: (ad, re.compile(desen, re.I))
    for anahtar, ad, desen in [
        (
            "istanbul",
            "İstanbul",
            r"[iİı]stanbul|sar[ıi]yer|maslak|levent|kad[ıi]k[öo]y|[üu]sk[üu]dar|ata[sş]ehir|be[sş]ikta[sş]",
        ),
        ("ankara", "Ankara", r"ankara|odt[üu]|bilkent|teknokent ankara"),
        ("izmir", "İzmir", r"[iİı]zmir"),
        ("kocaeli", "Kocaeli", r"kocaeli|gebze|[iİı]zmit"),
        ("bursa", "Bursa", r"bursa"),
        ("eskisehir", "Eskişehir", r"eski[sş]ehir"),
        ("antalya", "Antalya", r"antalya"),
        ("konya", "Konya", r"konya"),
        ("kayseri", "Kayseri", r"kayseri"),
        ("adana", "Adana", r"adana"),
        ("gaziantep", "Gaziantep", r"gaziantep"),
        ("sakarya", "Sakarya", r"sakarya"),
        ("tekirdag", "Tekirdağ", r"tekirda[gğ]|[çc]orlu"),
        ("trabzon", "Trabzon", r"trabzon"),
        ("samsun", "Samsun", r"samsun"),
    ]
}
UZAKTAN = re.compile(r"(?i)remote|uzaktan|anywhere|her yerden")


def sehirleri_bul(konum: str) -> list[str]:
    """Konum metnindeki şehir anahtarları (sıralı, tekrarsız). Şehir yoksa boş liste."""
    return [anahtar for anahtar, (_, desen) in SEHIRLER.items() if desen.search(konum or "")]


def uzaktan_mi(konum: str) -> bool:
    return bool(UZAKTAN.search(konum or ""))
