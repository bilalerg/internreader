"""Bülten kategorileri: bir ilan hangi alanlara girer, çalışma modeli ne, girişim ilanı mı?

Hepsi belirleyici kurallarla çıkarılır; yapay zekâya ek istek gitmez (maliyet değişmez). Girdiler zaten elimizde:
sınıflandırıcının kararı (rol, yapay_zeka), firma etiketleri ve firmanın geldiği listeler (firmalar.etiket,
firmalar.kaynak), ilan başlığı, konumu ve ayrıntı çıkarıcının bulduğu çalışma modeli.
Sitedeki önizleme bu alanları ilanlar.json'dan hazır okur; kural yalnızca burada yaşar.

Alanlar (bir ilan birden çok alana girebilir: savunma firmasında yazılım stajı hem "yazilim" hem "savunma"):
- yazilim / yapay_zeka / veri: sınıflandırıcının rolü. Rolü yazılım olsa da yapay zekâ işin özündeyse
  (yapay_zeka == "ozunde") ilan "yapay_zeka" alanına da girer. "arti" (AI bilgisi artı) girmez.
- oyun: firma etiketi "oyun", firma adında "games/gaming/oyun" ya da başlıkta "game/oyun/unity/unreal".
- savunma (savunma, siber güvenlik, havacılık): firma etiketi "savunma/siber/havacilik" (savunmakariyer listesinden
  gelen firmalar "savunma" etiketlidir) ya da başlıkta savunma/siber/havacılık kelimeleri.

Çalışma modeli: konum metni "remote/uzaktan" diyorsa uzaktan, "hybrid/hibrit" diyorsa hibrit (ilan sisteminin
yapılandırılmış alanı, en güvenilir kaynak); konum bir şey söylemiyorsa ayrıntı çıkarıcının kararı (ofis → yerinde).
Hiçbiri yoksa "belirsiz". Başlığa bakılmaz: "Hybrid App Developer", "Remote Sensing" yanıltır.

Girişim (startup) kuralı, sırayla:
1. Elle işaret önce gelir: firma etiketi "girisim" → evet.
2. Büyük kurum → hayır: etiket "kurumsal", "banka" ya da "telekom"; ilan kurumsal bir ilan sisteminden geliyor
   (Workday, SuccessFactors, Avature, Oracle, Taleo); ya da firma herkesin zaten bildiği büyük şirketlerden
   (BUYUK_KURUMLAR: Aselsan, Turkcell, Trendyol, bankalar, üniversiteler...). Öğrenciyi bunlara yönlendirmek fark yaratmıyor.
3. Girişim ekosisteminden gelen firma → evet: turkiye.ai (yapay zekâ girişimleri haritası), teknopark ve kuluçka
   listeleri (teknopark_istanbul, budotek, dijitalpark, tpi; "teknopark" etiketi) ya da ats_genis listesinden gelip
   ilanını girişimlerin kullandığı bir ilan sisteminden (Lever, Ashby, Greenhouse, Workable, Recruitee...) yayınlayan
   firma. ats_genis tek başına yetmez: listede Uber, Mercedes-Benz Türk gibi büyük şirketler de var.
4. Geri kalan her şey → hayır (savunmakariyer, tohum listesi, AI kullanan şirket listeleri, arama keşfi...).
Yanlış sınıflanan firma firmalar.csv'de "girisim" ya da "kurumsal" etiketiyle düzeltilir.
"""

import re

from internreader.isleme.sehir import uzaktan_mi

ALANLAR = ("yazilim", "yapay_zeka", "veri", "oyun", "savunma")
CALISMA_MODELLERI = ("uzaktan", "hibrit", "yerinde")

SAVUNMA_ETIKETLERI = frozenset({"savunma", "siber", "havacilik"})
_OYUN_FIRMA = re.compile(r"(?i)\b(games?|gaming|oyun)")
_OYUN_BASLIK = re.compile(r"(?i)\b(games?|gameplay|oyun|unity|unreal)\b")
_SAVUNMA_BASLIK = re.compile(
    r"(?i)savunma|\bdefen[cs]e\b|\bsiber|\bcyber|bilgi güvenliği|information security|sızma testi|penetration test|"
    r"havac[ıi]l[ıi]k|aerospace|aviation|avionics|aviyonik|\buydu|satellite|\buav\b|insansız hava|\bradar|füze|missile"
)
_HIBRIT = re.compile(r"(?i)hybrid|hibrit")
AYRINTI_MODELI = {"uzaktan": "uzaktan", "hibrit": "hibrit", "ofis": "yerinde"}

GIRISIM_KAYNAKLARI = frozenset({"turkiye.ai", "teknopark_istanbul", "budotek", "dijitalpark", "tpi"})
GIRISIM_ETIKETLERI = frozenset({"teknopark"})
GIRISIM_ILAN_SISTEMLERI = frozenset({"lever", "ashby", "greenhouse", "workable", "recruitee", "breezy", "teamtailor"})
KURUMSAL_ETIKETLER = frozenset({"kurumsal", "banka", "telekom"})
KURUMSAL_ILAN_SISTEMLERI = frozenset({"workday", "successfactors", "avature", "oracle", "taleo"})
BUYUK_KURUMLAR = re.compile(
    r"(?i)\b(aselsan\w*|roketsan|tusa[sş]|türk havac[ıi]l[ıi]k|havelsan|baykar|stm|fnss|otokar|mke|turkcell|vodafone|"
    r"t[üu]rk telekom|trendyol|hepsiburada|getir|koç|koçsistem|sabanc[ıi]|garanti|akbank|yap[ıi] kredi|ziraat|"
    r"i[şs] bankas[ıi]|arçelik|vestel|ford otosan|tofa[şs]|siemens|bosch|huawei|ericsson|nokia|microsoft|google|"
    r"amazon|analog devices|basf|mercedes|coca-cola|uber|delivery hero|binance|udemy|acronis|üniversite\w*|university)\b"
)


def alanlari_bul(rol: str, yapay_zeka: str, baslik: str, firma: str, firma_etiketi: set[str]) -> list[str]:
    alanlar = {rol}
    if yapay_zeka == "ozunde":
        alanlar.add("yapay_zeka")
    if "oyun" in firma_etiketi or _OYUN_FIRMA.search(firma) or _OYUN_BASLIK.search(baslik):
        alanlar.add("oyun")
    if firma_etiketi & SAVUNMA_ETIKETLERI or _SAVUNMA_BASLIK.search(baslik):
        alanlar.add("savunma")
    return [a for a in ALANLAR if a in alanlar]


def calisma_modeli(konum: str, ayrinti_modeli: str | None) -> str:
    if uzaktan_mi(konum):
        return "uzaktan"
    if _HIBRIT.search(konum or ""):
        return "hibrit"
    return AYRINTI_MODELI.get(ayrinti_modeli or "", "belirsiz")


def girisim_mi(firma: str, firma_etiketi: set[str], firma_kaynaklari: set[str], ilan_kaynagi: str) -> bool:
    if "girisim" in firma_etiketi:
        return True
    if firma_etiketi & KURUMSAL_ETIKETLER or ilan_kaynagi in KURUMSAL_ILAN_SISTEMLERI or BUYUK_KURUMLAR.search(firma):
        return False
    if firma_kaynaklari & GIRISIM_KAYNAKLARI or firma_etiketi & GIRISIM_ETIKETLERI:
        return True
    return "ats_genis" in firma_kaynaklari and ilan_kaynagi in GIRISIM_ILAN_SISTEMLERI
