"""Kural tabanlı filtreler.

- konum_uygun: yapay zekâya gitmeden ÖNCE ucuz bir ön seçim (Türkiye'deki yerinde/hibrit ve dünyadaki uzaktan ilanlar).
- yedek_siniflandirma: yapay zekâ bütçesi biterse ya da çağrı başarısız olursa kullanılan kaba kurallar.
  Yapay zekâ sınıflandırması her zaman önceliklidir; bu yalnızca bir emniyet ağıdır.
"""

import re

from internreader.model import Ilan

ILLER = (
    "adana adıyaman afyonkarahisar ağrı aksaray amasya ankara antalya ardahan artvin aydın balıkesir bartın "
    "batman bayburt bilecik bingöl bitlis bolu burdur bursa çanakkale çankırı çorum denizli diyarbakır düzce "
    "edirne elazığ erzincan erzurum eskişehir gaziantep giresun gümüşhane hakkari hatay ığdır isparta istanbul "
    "izmir kahramanmaraş karabük karaman kars kastamonu kayseri kırıkkale kırklareli kırşehir kilis kocaeli konya "
    "kütahya malatya manisa mardin mersin muğla muş nevşehir niğde ordu osmaniye rize sakarya samsun siirt sinop "
    "sivas şanlıurfa şırnak tekirdağ tokat trabzon tunceli uşak van yalova yozgat zonguldak"
).split()
_HARFLER = str.maketrans("çğıöşü", "cgiosu")
_YERLER = {"türkiye", "turkiye", "turkey", "gebze", *ILLER, *(il.translate(_HARFLER) for il in ILLER)}
TURKIYE = re.compile(r"(?i)\b(?:" + "|".join(re.escape(yer) for yer in sorted(_YERLER, key=len, reverse=True)) + r")\b")
UZAKTAN = re.compile(r"(?i)remote|uzaktan|anywhere|worldwide|her yerden")

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
# Eski "diğer teknik" kararlarında yazılım ağırlığı kaçmış olabilecek başlıklar. Kararı yine model verir.
YAZILIM_YENIDEN_BAK = re.compile(
    r"(?i)software|developer|yaz[ıi]l[ıi]m|backend|frontend|full[- ]?stack|devops|sre\b|"
    r"robotik|robotics|otomasyon|automation|\bROS\b|\bPLC\b|firmware|g[öo]m[üu]l[üu]"
)


def konum_uygun(ilan: Ilan) -> bool:
    # Kariyer sayfası listemizdeki firmalar Türkiye'deki firmalar; sayfa konum yazmıyorsa Türkiye sayılır.
    if ilan.kaynak == "kariyer_sayfasi" and not ilan.konum:
        return True
    if ilan.kaynak == "jooble":  # tr.jooble.org yalnız Türkiye ilanı verir; "Manisa" gibi şehirler listede yok
        return True
    if TURKIYE.search(ilan.konum):
        return True
    # Uzaktan işler başka bir ülkeyle etiketlense de adaydır; hibrit/yüz yüze işler Türkiye'de olmalı.
    return bool(UZAKTAN.search(ilan.konum))


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
