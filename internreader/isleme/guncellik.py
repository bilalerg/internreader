"""İlan güncelliği: bayat ilanı yayından düşürmek ve kartta doğru tarih bilgisini göstermek.

Sorun (29.10): kariyer sayfası ilanlarının çoğunda tarih alanı yok; Yeditek'in 08 Mayıs 2023 tarihli ilanı "açık"
diye yayındaydı. Sayfa hâlâ duruyor diye ilan açık değildir.

Sinyaller (hepsi ya kodla bulunur ya da kodla doğrulanır):
- son_basvuru: ayrıntı çıkarıcının bulduğu son başvuru tarihi.
- ilan_tarihi: metinde açıkça yazan yayın tarihi. Çıkarıcı bulur; tarih metinde gerçekten geçmiyorsa atılır
  (metindeki_tarihler).
- yayin_tarihi: ilan sisteminin (ATS) verdiği tarih.
- dönem yılları: başlıktaki yıllar ve metinde "2025 Yaz Stajı", "2024-2025 dönemi", "Summer Internship 2024" gibi
  dönem bildiren yıllar. "2015'te kurulduk" gibi şirket tanıtımı yılları sayılmaz; "2026 mezunları" da sayılmaz
  (geçen yılın mezunlarını arayan ilan hâlâ açık olabilir).

Kurallar:
1. Son başvuru geçmişte → yayından kalkar (her kaynak).
2. Kariyer sayfası ilanı: ilan_tarihi 180 günden eski ve ileri bir son başvuru yok → kalkar.
3. Kariyer sayfası ilanı: dönem yılları var ve hepsi geçmiş yıllar; bu yıl ya da sonrası bir tarih (son başvuru,
   ilan tarihi) yok → kalkar.
4. Genel CV toplama sayfası (ilan_turu == "genel_basvuru", Hitit "New Talent") → kalkar (her kaynak).
ATS ilanları 2 ve 3'le kalkmaz: pano kapanınca zaten düşerler. Yayın tarihi 365 günden eskiyse "sürekli açık başvuru"
sayılır (Dream Games'in 2022'den beri açık ilanı gibi); kartta eski yıl yazılmaz.

Sıralama (siralama_anahtari; bülten, site ve özet aynı sırayı kullanır): önce yeni tarihli ilanlar, aynı tazelikte
işler eğitim ve yarışmadan, girişimler diğerlerinden, ücretliler ücreti yazmayanlardan önce; tarihsizler ve sürekli
açık ilanlar geride.
"""

import re
from datetime import date, timedelta

ILAN_TARIHI_OMRU = timedelta(days=180)
SUREKLI_ACIK_ESIGI = timedelta(days=365)

_AYLAR = {
    **dict.fromkeys(["ocak", "january", "jan"], 1),
    **dict.fromkeys(["şubat", "subat", "february", "feb"], 2),
    **dict.fromkeys(["mart", "march", "mar"], 3),
    **dict.fromkeys(["nisan", "april", "apr"], 4),
    **dict.fromkeys(["mayıs", "mayis", "may"], 5),
    **dict.fromkeys(["haziran", "june", "jun"], 6),
    **dict.fromkeys(["temmuz", "july", "jul"], 7),
    **dict.fromkeys(["ağustos", "agustos", "august", "aug"], 8),
    **dict.fromkeys(["eylül", "eylul", "september", "sept", "sep"], 9),
    **dict.fromkeys(["ekim", "october", "oct"], 10),
    **dict.fromkeys(["kasım", "kasim", "november", "nov"], 11),
    **dict.fromkeys(["aralık", "aralik", "december", "dec"], 12),
}
_AY = "|".join(sorted(_AYLAR, key=len, reverse=True))
_SAYISAL = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](20\d\d)\b")
_ISO = re.compile(r"\b(20\d\d)-(\d{1,2})-(\d{1,2})\b")
_GUN_AY_YIL = re.compile(rf"\b(\d{{1,2}})\.?[\s-]+({_AY})\.?,?[\s-]+(20\d\d)\b")  # "27-Oct-2026" de olur
_AY_GUN_YIL = re.compile(rf"\b({_AY})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(20\d\d)\b")

_DONEM_KELIMESI = (
    r"yaz|kış|kis|güz|guz|bahar|dönem|donem|summer|winter|fall|spring|autumn|staj|intern|program|akademik|academic|"
    r"eğitim|egitim|sezon|season|term"
)
_DONEM = re.compile(
    rf"\b(20\d\d)(?:\s*[-–/]\s*(20\d\d))?\s*(?:yılı\s+|year\s+)?(?:{_DONEM_KELIMESI})"
    r"|\b(?:yaz|kış|güz|bahar|summer|winter|fall|spring|autumn|internship|staj[ıi]?|program[ıi]?)\s+(20\d\d)\b"
)
_YIL = re.compile(r"\b(20\d\d)\b")


def _kucuk(metin: str) -> str:
    """Türkçe "İ" küçülünce iki karaktere dönüşür; önce "I" yapılır ki uzunluk ve ay adları bozulmasın."""
    return (metin or "").replace("İ", "I").lower()


def _tarih(yil: int, ay: int, gun: int) -> date | None:
    try:
        return date(yil, ay, gun)
    except ValueError:
        return None


def metindeki_tarihler(metin: str) -> set[date]:
    """Metinde gün, ay ve yılıyla açıkça yazan tarihler: 08.05.2023, 2023-05-08, 08 Mayıs 2023, May 8, 2023...
    Sayısal biçimde gün/ay sırası belirsiz olduğundan (05/08/2023) iki okuma da eklenir."""
    kucuk = _kucuk(metin)
    tarihler = set()
    for g, a, y in _SAYISAL.findall(kucuk):
        tarihler |= {_tarih(int(y), int(a), int(g)), _tarih(int(y), int(g), int(a))}
    for y, a, g in _ISO.findall(kucuk):
        tarihler.add(_tarih(int(y), int(a), int(g)))
    for g, ay, y in _GUN_AY_YIL.findall(kucuk):
        tarihler.add(_tarih(int(y), _AYLAR[ay], int(g)))
    for ay, g, y in _AY_GUN_YIL.findall(kucuk):
        tarihler.add(_tarih(int(y), _AYLAR[ay], int(g)))
    return tarihler - {None}


def donem_yillari(metin: str) -> set[int]:
    """Metinde dönem bildiren yıllar ("2025 Yaz Stajı" → 2025; "2024-2025 dönemi" → 2024, 2025)."""
    yillar = set()
    for bas, son, sonra in _DONEM.findall(_kucuk(metin)):
        yillar |= {int(y) for y in (bas, son, sonra) if y}
    return yillar


def baslik_yillari(baslik: str) -> set[int]:
    return {int(y) for y in _YIL.findall(baslik or "")}


def _gun(metin: str | None) -> date | None:
    try:
        return date.fromisoformat(metin) if metin else None
    except ValueError:
        return None


def guncellik(
    kaynak: str,
    yayin_tarihi: str,
    son_basvuru: str | None,
    ilan_tarihi: str | None,
    yillar: set[int],
    bugun: date,
    ilan_turu: str = "is",
) -> dict:
    """{"bayat": neden ya da None, "yayin": kartta gösterilecek yayın tarihi ya da None, "surekli_acik": bool}"""
    son, ilan_gunu, yayin = _gun(son_basvuru), _gun(ilan_tarihi), _gun(yayin_tarihi)
    ats = kaynak != "kariyer_sayfasi"
    surekli_acik = ats and yayin is not None and yayin < bugun - SUREKLI_ACIK_ESIGI
    gosterilen = None if surekli_acik else (yayin or ilan_gunu)
    sonuc = {"bayat": None, "yayin": gosterilen.isoformat() if gosterilen else None, "surekli_acik": surekli_acik}
    ileri_son_basvuru = son is not None and son >= bugun
    if ilan_turu == "genel_basvuru":
        sonuc["bayat"] = "genel_basvuru"
    elif son is not None and not ileri_son_basvuru:
        sonuc["bayat"] = "son_basvuru_gecti"
    elif not ats and not ileri_son_basvuru and ilan_gunu and ilan_gunu < bugun - ILAN_TARIHI_OMRU:
        sonuc["bayat"] = "eski_ilan_tarihi"
    elif not ats and yillar and max(yillar) < bugun.year:
        bu_yil_tarihi = any(t and t.year >= bugun.year for t in (son, ilan_gunu))
        if not bu_yil_tarihi:
            sonuc["bayat"] = "gecmis_donem"
    return sonuc


YENI_GUN, TAZE_GUN = 14, 45  # yayın tarihi bu kadar gün içindeyse "yeni", "taze" sayılır


def siralama_anahtari(ilan: dict, bugun: date) -> tuple:
    yayin = _gun(ilan.get("yayin"))
    if ilan.get("surekli_acik"):
        kova = 4
    elif yayin is None:
        kova = 3
    else:
        yas = (bugun - yayin).days
        kova = 0 if yas <= YENI_GUN else 1 if yas <= TAZE_GUN else 2
    ucretli = (ilan.get("ayrinti") or {}).get("ucretli") == "evet"
    return (
        kova,
        ilan.get("ilan_turu", "is") != "is",
        not ilan.get("girisim"),
        not ucretli,
        -(yayin.toordinal() if yayin else 0),
        -date.fromisoformat(ilan["ilk_gorulme"][:10]).toordinal(),
        ilan["firma"],
        ilan["baslik"],
    )
