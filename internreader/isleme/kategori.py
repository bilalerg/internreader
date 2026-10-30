"""Bülten kategorileri: bir ilan hangi alanlara girer, çalışma modeli ne, girişim ilanı mı?

Hepsi belirleyici kurallarla çıkarılır; yapay zekâya ek istek gitmez (maliyet değişmez). Girdiler zaten elimizde:
sınıflandırıcının kararı (rol, yapay_zeka), firma etiketleri ve firmanın geldiği listeler (firmalar.etiket,
firmalar.kaynak), ilan başlığı, konumu ve ayrıntı çıkarıcının bulduğu çalışma modeli.
Sitedeki önizleme bu alanları ilanlar.json'dan hazır okur; kural yalnızca burada yaşar.

Alanlar (bir ilan birden çok alana girebilir: savunma firmasında yazılım stajı hem "yazilim" hem "savunma"):
- yazilim / yapay_zeka / veri: sınıflandırıcının rolü. Rolü yazılım olsa da yapay zekâ işin özündeyse
  (yapay_zeka == "ozunde") ilan "yapay_zeka" alanına da girer. "arti" (AI bilgisi artı) girmez.
- oyun: firma etiketi "oyun", firma adında "games/gaming/oyun" ya da başlıkta "game/oyun/unity/unreal".
- savunma (savunma, siber güvenlik, havacılık): başlıkta savunma/siber/havacılık kelimeleri; elle doğrulanmış firma
  etiketi ("savunma_dogrulandi", "siber", "havacilik"); ya da "savunma" etiketli firma ve ilan metninde kanıt.
  savunmakariyer listesinden gelmek tek başına yetmez: listede savunmaya tedarikçi ama ilanı başka işe ait firmalar var
  (Mavvo ERP, Türk SEM otel yazılımı).

Çalışma modeli: konum metni "remote/uzaktan" diyorsa uzaktan, "hybrid/hibrit" diyorsa hibrit (ilan sisteminin
yapılandırılmış alanı, en güvenilir kaynak); konum bir şey söylemiyorsa ayrıntı çıkarıcının kararı (ofis → yerinde).
Hiçbiri yoksa "belirsiz". Başlığa bakılmaz: "Hybrid App Developer", "Remote Sensing" yanıltır.

Girişim (startup) kuralı, sırayla. Vizyonun merkezi bu ("öğrenciyi yeni girişimlere yönlendirmek"); kural bilerek dar:
1. Elle işaret önce gelir: firma etiketi "girisim" → evet.
2. Büyük kurum → hayır: etiket "kurumsal", "banka" ya da "telekom"; ilan kurumsal bir ilan sisteminden geliyor
   (Workday, SuccessFactors, Avature, Oracle, Taleo); ya da firma herkesin zaten bildiği büyük şirketlerden
   (BUYUK_KURUMLAR: Aselsan, Turkcell, Trendyol, bankalar, üniversiteler...). Öğrenciyi bunlara yönlendirmek fark yaratmıyor.
3. turkiye.ai (yapay zekâ girişimleri haritası) listesinden gelen firma → evet.
4. Geri kalan her şey → hayır. Teknopark kiracısı olmak ya da Lever/Greenhouse kullanmak girişim kanıtı DEĞİL: o
   listelerde 20 yıllık KOBİ'ler ve küresel şirketler var (Commencis, Obilet, Wise, BASF). Bunlar "aday" sayılır
   (girisim_gerekcesi); Bilal gözden geçirip gerçek girişimleri firmalar.csv'de "girisim" etiketiyle ekler.
Liste: python -m internreader girisim-listesi
"""

import re

from internreader.isleme.sehir import uzaktan_mi
from internreader.yayin import SEVIYE_ADI

ALANLAR = ("yazilim", "yapay_zeka", "veri", "oyun", "savunma")
CALISMA_MODELLERI = ("uzaktan", "hibrit", "yerinde")

DOGRULANMIS_SAVUNMA_ETIKETLERI = frozenset({"savunma_dogrulandi", "siber", "havacilik"})
_OYUN_FIRMA = re.compile(r"(?i)\b(games?|gaming|oyun)")
_OYUN_BASLIK = re.compile(r"(?i)\b(games?|gameplay|oyun|unity|unreal)\b")
_SAVUNMA_BASLIK = re.compile(
    r"(?i)savunma|\bdefen[cs]e\b|\bsiber|\bcyber|bilgi güvenliği|information security|sızma testi|penetration test|"
    r"havac[ıi]l[ıi]k|aerospace|aviation|avionics|aviyonik|\buydu|satellite|\buav\b|insansız hava|\bradar|füze|missile"
)
_HIBRIT = re.compile(r"(?i)hybrid|hibrit")
_YERINDE = re.compile(r"(?i)\bofiste\b|on-?site|office only|yerinde")
AYRINTI_MODELI = {"uzaktan": "uzaktan", "hibrit": "hibrit", "ofis": "yerinde"}

GIRISIM_KAYNAKLARI = frozenset({"turkiye.ai"})
ADAY_KAYNAKLARI = frozenset({"teknopark_istanbul", "budotek", "dijitalpark", "tpi", "ats_genis"})
KURUMSAL_ETIKETLER = frozenset({"kurumsal", "banka", "telekom"})
KURUMSAL_ILAN_SISTEMLERI = frozenset({"workday", "successfactors", "avature", "oracle", "taleo"})
BUYUK_KURUMLAR = re.compile(
    r"(?i)\b(aselsan\w*|roketsan|tusa[sş]|türk havac[ıi]l[ıi]k|havelsan|baykar|stm|fnss|otokar|mke|turkcell|vodafone|"
    r"t[üu]rk telekom|trendyol|hepsiburada|getir|koç|koçsistem|sabanc[ıi]|garanti|akbank|yap[ıi] kredi|ziraat|"
    r"i[şs] bankas[ıi]|arçelik|vestel|ford otosan|tofa[şs]|siemens|bosch|huawei|ericsson|nokia|microsoft|google|"
    r"amazon|analog devices|basf|mercedes|coca-cola|uber|delivery hero|binance|udemy|acronis|üniversite\w*|university)\b"
)


def savunma_metinde(metin: str) -> bool:
    return bool(_SAVUNMA_BASLIK.search(metin or ""))


def alanlari_bul(
    rol: str, yapay_zeka: str, baslik: str, firma: str, firma_etiketi: set[str], savunma_kaniti: bool = False
) -> list[str]:
    alanlar = {rol}
    if yapay_zeka == "ozunde":
        alanlar.add("yapay_zeka")
    if "oyun" in firma_etiketi or _OYUN_FIRMA.search(firma) or _OYUN_BASLIK.search(baslik):
        alanlar.add("oyun")
    if (
        firma_etiketi & DOGRULANMIS_SAVUNMA_ETIKETLERI
        or _SAVUNMA_BASLIK.search(baslik)
        or ("savunma" in firma_etiketi and savunma_kaniti)
    ):
        alanlar.add("savunma")
    return [a for a in ALANLAR if a in alanlar]


def calisma_modeli(konum: str, ayrinti_modeli: str | None) -> str:
    if uzaktan_mi(konum):
        return "uzaktan"
    if _HIBRIT.search(konum or ""):
        return "hibrit"
    if _YERINDE.search(konum or ""):
        return "yerinde"
    return AYRINTI_MODELI.get(ayrinti_modeli or "", "belirsiz")


def girisim_mi(firma: str, firma_etiketi: set[str], firma_kaynaklari: set[str], ilan_kaynagi: str) -> bool:
    if "girisim" in firma_etiketi:
        return True
    if firma_etiketi & KURUMSAL_ETIKETLER or ilan_kaynagi in KURUMSAL_ILAN_SISTEMLERI or BUYUK_KURUMLAR.search(firma):
        return False
    return bool(firma_kaynaklari & GIRISIM_KAYNAKLARI)


def girisim_gerekcesi(firma: str, firma_etiketi: set[str], firma_kaynaklari: set[str], ilan_kaynagi: str = "") -> str:
    """Gözden geçirme listesi için: firma neden girişim sayılıyor ya da neden aday."""
    if "girisim" in firma_etiketi:
        return "evet: elle doğrulandı (girisim etiketi)"
    if girisim_mi(firma, firma_etiketi, firma_kaynaklari, ilan_kaynagi):
        return "evet: turkiye.ai listesinde"
    if firma_etiketi & KURUMSAL_ETIKETLER or ilan_kaynagi in KURUMSAL_ILAN_SISTEMLERI or BUYUK_KURUMLAR.search(firma):
        return "hayır: büyük kurum"
    if adaylar := sorted(firma_kaynaklari & ADAY_KAYNAKLARI):
        return "aday: " + ", ".join(adaylar)
    return "hayır: girişim listesinde değil"


# ---------------- ilan türü ve kart etiketi ----------------
_YARISMA = re.compile(r"(?i)\bleague\b|hackathon|ideathon|yarışma|competition|\bchallenge\b|codefest")
_EGITIM = re.compile(r"(?i)\bboot ?camp|\bcamp\b|\bkamp[ıi]?\b|eğitim programı|training program")
_GENEL_BASVURU_BASLIK = re.compile(
    r"(?i)genel başvuru|general application|open application|spontaneous application|talent pool|yetenek havuzu|"
    r"cv havuzu"
)
_GENEL_BASVURU_METIN = re.compile(
    r"(?i)haven.?t found|have not found|uygun (bir )?(pozisyon|ilan) bulamad|genel başvuru|general application|"
    r"talent pool|yetenek havuzu"
)
_TUM_SEVIYELER = re.compile(r"(?i)all (experience )?levels|tüm seviyeler|her seviyeden")
TUR_ETIKETI = {"egitim": "Eğitim programı", "yarisma": "Yarışma"}


def ilan_turu_bul(baslik: str, metin: str, model_turu: str = "is") -> str:
    """Önce belirleyici kural, emin değilse çıkarıcının kararı. CV havuzu cümlesi metnin BAŞINDA aranır: gerçek ilanların
    altında da "aradığını bulamadın mı?" kutusu olabilir."""
    if _GENEL_BASVURU_BASLIK.search(baslik) or _GENEL_BASVURU_METIN.search((metin or "")[:600]):
        return "genel_basvuru"
    if _YARISMA.search(baslik):
        return "yarisma"
    if _EGITIM.search(baslik):
        return "egitim"
    return model_turu


def seviye_etiketi(seviye: str, baslik: str, ilan_turu: str = "is") -> str:
    """Kartta dürüst etiket: eğitim programına "Staj", "All Levels" ilanına "Junior" yazılmaz. Sınıflandırma
    (seviye, abone eşleşmesi) değişmez; yalnızca görünen ad."""
    if ilan_turu in TUR_ETIKETI:
        return TUR_ETIKETI[ilan_turu]
    if _TUM_SEVIYELER.search(baslik or ""):
        return "Tüm seviyeler"
    return SEVIYE_ADI.get(seviye, seviye)
