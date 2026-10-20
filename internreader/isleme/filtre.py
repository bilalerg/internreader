"""Kural tabanlı filtreler.

- konum_uygun: yapay zekâya gitmeden ÖNCE ucuz bir ön seçim (Türkiye'deki ya da genel uzaktan ilanlar).
- yedek_siniflandirma: yapay zekâ bütçesi biterse ya da çağrı başarısız olursa kullanılan kaba kurallar.
  Yapay zekâ sınıflandırması her zaman önceliklidir; bu yalnızca bir emniyet ağıdır.
"""

import re

from internreader.model import Ilan

TURKIYE = re.compile(
    r"(?i)t[üu]rk[iı]ye|turkey|[iİı]stanbul|ankara|[iİı]zmir|bursa|kocaeli|gebze|antalya|eski[sş]ehir|"
    r"konya|kayseri|sakarya|adana|trabzon|samsun|gaziantep|tekirdağ|tekirdag"
)
UZAKTAN = re.compile(r"(?i)remote|uzaktan|anywhere|worldwide|emea|europe|global|hybrid|hibrit")

STAJ = re.compile(r"(?i)\bintern|stajyer|\bstaj|working student|trainee")
JUNIOR = re.compile(r"(?i)\bjunior\b|\bjr\.?\b|entry[- ]level")
YENI_MEZUN = re.compile(r"(?i)new grad|graduate|yeni mezun|aday mühendis|genç yetenek")
YARI_ZAMANLI = re.compile(r"(?i)part[- ]?time|yar[ıi] zamanl[ıi]")
YAPAY_ZEKA = re.compile(
    r"(?i)machine learning|\bml\b|\bllm\b|yapay zeka|yapay zekâ|computer vision|\bnlp\b|\bai engineer"
)
VERI = re.compile(r"(?i)\bdata (analyst|engineer|scientist)|veri (analisti|mühendisi|bilimci)|\bbi\b")
YAZILIM = re.compile(
    r"(?i)software|developer|yaz[ıi]l[ıi]m|backend|back-end|frontend|front-end|full[- ]?stack|mobile|"
    r"android|\bios\b|devops|\bqa\b|test (automation|engineer)|game developer|sre\b"
)


def konum_uygun(ilan: Ilan) -> bool:
    # Kariyer sayfası listemizdeki firmalar Türkiye'deki firmalar; sayfa konum yazmıyorsa Türkiye sayılır.
    if ilan.kaynak == "kariyer_sayfasi" and not ilan.konum:
        return True
    if TURKIYE.search(ilan.konum):
        return True
    # "Remote", "Remote - EMEA" gibi genel uzaktan ilanlar kabul; "Chile, Remote" gibi başka ülkeye bağlı olanlar değil.
    kalan = re.sub(r"[^a-zçğıöşü]", "", UZAKTAN.sub("", ilan.konum.lower()))
    return bool(UZAKTAN.search(ilan.konum)) and not kalan


def yedek_siniflandirma(ilan: Ilan) -> dict:
    """Yapay zekâ yokken kaba karar. Bilinçli olarak temkinli: emin olamadığı ilanı 'belirsiz' bırakır."""
    metin = f"{ilan.baslik} {ilan.calisma_tipi}"
    if STAJ.search(metin):
        seviye = "staj"
    elif YENI_MEZUN.search(metin):
        seviye = "yeni_mezun"
    elif JUNIOR.search(metin):
        seviye = "junior"
    elif YARI_ZAMANLI.search(metin):
        seviye = "yari_zamanli"
    else:
        seviye = "belirsiz"
    if YAPAY_ZEKA.search(ilan.baslik):
        rol = "yapay_zeka"
    elif VERI.search(ilan.baslik):
        rol = "veri"
    elif YAZILIM.search(ilan.baslik):
        rol = "yazilim"
    else:
        rol = "diger_teknik"
    return {
        "seviye": seviye,
        "rol": rol,
        "yapay_zeka": "ozunde" if rol == "yapay_zeka" else "yok",
        "gerekce": "kural tabanlı yedek karar",
    }
