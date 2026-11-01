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

Kurallar (ileri tarihli son başvuru 2, 3 ve 5'i durdurur):
1. Son başvuru geçmişte → yayından kalkar (her kaynak).
2. Hayalet ilan: en yeni tarih (yayın, sayfa kodu ya da metin) 180 günden eski → kalkar (her kaynak; 2022'den beri açık
   duran ATS ilanı da).
3. Dönem geçmiş: başlıkta geçmiş yıl (her kaynak), Eylül'den sonra bu yılın yaz dönemi; kariyer sayfası ve Jooble'da metinde
   geçmiş dönem yılı → kalkar.
4. Genel CV toplama sayfası (ilan_turu == "genel_basvuru", Hitit "New Talent") → kalkar (her kaynak).
5. Hiç tarihi olmayan ilan: ilk görüldüğünden 120 gün sonra kalkar.
Kartta tarihi olmayan ilan "Tarih belirtilmemiş" yazar ve sıralamada geride kalır. Yeniden yayınlanan ilanın eski tarihi
korunur (depo.ilanlari_kaydet): tarih yenilemek ilanı yeni yapmaz. Şüpheli kalıplar için: supheli_ilan.

Sıralama (siralama_anahtari; bülten, site ve özet aynı sırayı kullanır): önce yeni tarihli ilanlar, aynı tazelikte
işler eğitim ve yarışmadan, girişimler diğerlerinden, ücretliler ücreti yazmayanlardan önce; tarihsizler ve sürekli
açık ilanlar geride.
"""

import re
from datetime import date, timedelta

HAYALET_ESIGI = timedelta(days=180)  # bundan eski tarihli ilan, ileri bir son başvuru yoksa yayına girmez
TARIHSIZ_OMRU = timedelta(days=120)  # tarihi hiç bulunamayan ilan, ilk görüldüğünden bu kadar sonra düşer
_YAZ_DONEMI = re.compile(r"(?i)\byaz\b|summer")

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
    baslik: str = "",
    ilk_gorulme: date | None = None,
) -> dict:
    """{"bayat": neden ya da None, "yayin": kartta gösterilecek yayın tarihi ya da None, "surekli_acik": bool}.
    `surekli_acik` artık hep False: 180 günden eski ilan yayına girmez (site ve bülten alanı okumaya devam ediyor)."""
    son, ilan_gunu, yayin = _gun(son_basvuru), _gun(ilan_tarihi), _gun(yayin_tarihi)
    sayfa_gibi = kaynak in ("kariyer_sayfasi", "jooble")
    gosterilen = yayin or ilan_gunu
    en_yeni = max((t for t in (yayin, ilan_gunu) if t), default=None)
    sonuc = {"bayat": None, "yayin": gosterilen.isoformat() if gosterilen else None, "surekli_acik": False}
    ileri_son_basvuru = son is not None and son >= bugun
    bu_yil_tarihi = any(t and t.year >= bugun.year for t in (son, ilan_gunu))
    baslik_yili = baslik_yillari(baslik)
    if ilan_turu == "genel_basvuru":
        sonuc["bayat"] = "genel_basvuru"
    elif son is not None and not ileri_son_basvuru:
        sonuc["bayat"] = "son_basvuru_gecti"
    elif ileri_son_basvuru:
        pass
    elif en_yeni and en_yeni < bugun - HAYALET_ESIGI:
        sonuc["bayat"] = "eski_ilan_tarihi" if en_yeni == ilan_gunu else "hayalet"
    elif baslik_yili and max(baslik_yili) < bugun.year and not bu_yil_tarihi:
        sonuc["bayat"] = "gecmis_donem"
    elif bugun.year in baslik_yili and bugun.month >= 9 and _YAZ_DONEMI.search(baslik) and not bu_yil_tarihi:
        sonuc["bayat"] = "gecmis_donem"  # Kasım'da "2026 Yaz Stajı"
    elif sayfa_gibi and yillar and max(yillar) < bugun.year and not bu_yil_tarihi:
        sonuc["bayat"] = "gecmis_donem"
    elif not en_yeni and ilk_gorulme and ilk_gorulme < bugun - TARIHSIZ_OMRU:
        sonuc["bayat"] = "tarihsiz_eski"
    return sonuc


_SAYFA_TARIHI = re.compile(
    r"""(?i)(datePosted|datePublished|dateModified|article:published_time|article:modified_time|validThrough)"""
    r"""[^0-9]{0,40}(20\d\d-\d{2}-\d{2})"""
)


def sayfa_tarihleri(html: str, bugun: date) -> tuple[date | None, date | None]:
    """Sayfa kodundaki yapılandırılmış tarihler: (en son yayın ya da güncelleme, son başvuru). Sayfa bu tarihten sonra
    değişmediyse ilan da daha yeni olamaz. Heetsoft'un "yeni" görünen ilanları böyle Mart 2025 çıktı (01.11.2026)."""
    yayinlar, son_basvurular = [], []
    for alan, metin in _SAYFA_TARIHI.findall(html or ""):
        tarih = _gun(metin)
        if tarih is None:
            continue
        if alan.lower() == "validthrough":
            son_basvurular.append(tarih)
        elif tarih <= bugun:
            yayinlar.append(tarih)
    return max(yayinlar, default=None), max(son_basvurular, default=None)


_SUPHELI_BASLIK = re.compile(
    r"(?i)no experience required|deneyim gerekmez|tecrübe gerekmez|data entry|veri girişi|evden ek gelir|anket doldur|"
    r"bakıcı|oyun ablası"
)
_SUPHELI_FIRMA = re.compile(
    r"(?i)jobgether|jobleads|crossover|lensa\b|bakıcı|\bkolej|\beğitim kurumları|\bokulları\b|\bdershane"
)


def supheli_ilan(firma: str, baslik: str) -> bool:
    """Gerçek bir staj ya da junior işi olmayan kalıplar: toplu mikro görev ilanları, işe alım aracıları, okullar."""
    return bool(_SUPHELI_BASLIK.search(baslik or "") or _SUPHELI_FIRMA.search(firma or ""))


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
