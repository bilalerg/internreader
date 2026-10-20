"""Keşif: firmaların hangi ilan sistemini (ATS) kullandığını ve kariyer sayfasının nerede olduğunu bulur.

İki yöntem:
1. Sayfa taraması: ana sayfayı ve en fazla 3 kariyer bağlantısını açıp ATS bağlantılarını arar (her firma için).
2. Yoklama (isteğe bağlı): firma adından/alan adından kısa ad tahmin edip ATS API'lerine doğrudan sorar.
   Firma başına ~15 istek attığı için yalnızca seçili firmalarda kullanılır (--yokla).
Keşif günlük değil, ayda bir çalıştırılır; her firmanın keşif tarihi veritabanında tutulur.
"""

import logging
import re
import urllib.parse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from sqlalchemy.orm import sessionmaker

from internreader import depo
from internreader.ag import HttpIstemci, RobotsEngeli
from internreader.ayar import Ayarlar
from internreader.isleme.filtre import TURKIYE
from internreader.kaynaklar.ats import TOPLAYICILAR
from internreader.kaynaklar.kariyer_sayfasi import mutlak_adres
from internreader.model import FirmaBilgisi

kayit = logging.getLogger(__name__)

ATS_DESENLERI = [
    ("ashby", r"jobs\.ashbyhq\.com/([A-Za-z0-9\-_.]+)"),
    ("lever", r"jobs\.(?:eu\.)?lever\.co/([A-Za-z0-9\-_.]+)"),
    ("greenhouse", r"(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/(?:embed/job_board\?for=)?([A-Za-z0-9\-_.]+)"),
    ("workable", r"apply\.workable\.com/([A-Za-z0-9\-_.]+)"),
    ("recruitee", r"([A-Za-z0-9\-]+)\.recruitee\.com"),
    ("breezy", r"([A-Za-z0-9\-]+)\.breezy\.hr"),
    ("smartrecruiters", r"(?:jobs|careers)\.smartrecruiters\.com/([A-Za-z0-9\-_.]+)"),
    ("workday", r"([a-z0-9\-]+\.wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([A-Za-z0-9_\-]+)"),
]
GECERSIZ_SLUG = {"www", "api", "jobs", "embed", "careers", "app", "static", "assets"}
# Yol parçası olarak eşleşir ("/kariyer", "/careers/"). Eski sürüm "gizlilik" sayfalarını kariyer sanıyordu.
KARIYER_LINKI = re.compile(
    r"(?i)/(careers?|kariyer|jobs|join-?us|hiring|open-?positions|work-with-us|insan-?kaynaklari|"
    r"acik-?pozisyonlar?|is-?ilanlari)(?:[/?#.-]|$)"
)
YANLIS_SAYFA = re.compile(
    r"(?i)gizlilik|privacy|politika|policy|cerez|cookie|kvkk|aydinlatma|surdurulebilirlik|"
    r"sustainab|urun|product|cozum|solution|blog|haber|news|kategori|category|cv-hazirlama|insan-kaynaklari-yonetimi"
)
SOSYAL = re.compile(r"(?i)linkedin|twitter|facebook|instagram|youtube|x\.com")
# "kariyer.firma.com/storage/logo.png" gibi dosyalar sayfa değildir (eski sürüm TUSAŞ için bir PNG kaydetmişti)
DOSYA = re.compile(r"(?i)\.(png|jpe?g|gif|svg|webp|ico|pdf|docx?|xlsx?|zip|css|js|woff2?|mp4)(?:[?#]|$)")

# Yoklamada denenecek uç noktalar (yalnızca ilanı olan sonuç kabul edilir)
YOKLAMA_SIRASI = ["lever", "greenhouse", "ashby", "workable", "smartrecruiters", "recruitee", "breezy"]


def sayfadan_ats_bul(metin: str) -> tuple[str, str]:
    for ats, desen in ATS_DESENLERI:
        bulunan = re.findall(desen, metin, re.I)
        if ats == "workday":  # (kiracı.wdN, site) → "kiracı|wdN|site"
            bulunan = ["|".join(t[0].split(".") + [t[1]]) for t in bulunan]
        bulunan = [s for s in bulunan if s.lower() not in GECERSIZ_SLUG]
        if bulunan:
            return ats, max(set(bulunan), key=bulunan.count)
    return "", ""


def kariyer_baglantilari(asil_url: str, html: str) -> list[str]:
    adaylar = [mutlak_adres(asil_url, h) for h in re.findall(r'href="([^"#]{1,300})"', html)]
    return list(
        dict.fromkeys(
            a
            for a in adaylar
            if a
            and a.startswith("http")
            and KARIYER_LINKI.search(a)
            and not (SOSYAL.search(a) or YANLIS_SAYFA.search(a) or DOSYA.search(a))
        )
    )[:3]


def slug_tahminleri(ad: str, web: str) -> list[str]:
    tahmin = []
    if web:
        host = urllib.parse.urlparse(web if web.startswith("http") else f"https://{web}").netloc.lower()
        etiket = host.removeprefix("www.").split(".")[0]
        tahmin += [etiket, etiket.replace("-", "")]
    sade = re.sub(
        r"[^a-z0-9 ]",
        "",
        ad.lower()
        .replace("ı", "i")
        .replace("ş", "s")
        .replace("ğ", "g")
        .replace("ü", "u")
        .replace("ö", "o")
        .replace("ç", "c"),
    )
    kelimeler = [k for k in sade.split() if k not in {"as", "a", "ltd", "sti", "teknoloji", "yazilim", "bilisim"}]
    if kelimeler:
        tahmin += [kelimeler[0], "".join(kelimeler[:2])]
    return list(dict.fromkeys(t for t in tahmin if len(t) >= 3))[:4]


def ats_yokla(http: HttpIstemci, ad: str, web: str) -> tuple[str, str]:
    """Kısa ad tahminleriyle ATS API'lerine sorar. "param", "innova" gibi genel adlar dünyada başka şirketlere de
    ait olabileceği için pano ancak en az bir ilanı Türkiye'deyse kabul edilir (yanlış firma eşleşmesine karşı)."""
    for slug in slug_tahminleri(ad, web):
        for ats in YOKLAMA_SIRASI:
            try:
                ilanlar = TOPLAYICILAR[ats](http, ad, slug)
            except Exception:  # 404 vb. → bu ATS'de böyle bir firma yok
                continue
            if any(TURKIYE.search(i.konum) for i in ilanlar):
                return ats, slug
    return "", ""


def ats_calisiyor_mu(http: HttpIstemci, ad: str, ats: str, slug: str) -> bool:
    try:
        TOPLAYICILAR[ats](http, ad, slug)
        return True
    except Exception:
        return False


def firmayi_kesfet(http: HttpIstemci, firma: FirmaBilgisi, yokla: bool) -> tuple[str, str, str, str]:
    """(ats, slug, kariyer sayfası, durum) döndürür. Ana sayfa açılmasa bile (bot koruması vb.) yoklama yapılır:
    büyük firmaların sitesi botları engellese de ilanları çoğu zaman açık bir ATS panosundadır."""
    durum, kariyer, metin = "tamam", [], ""
    try:
        asil_url, metin = http.sayfa(firma.web)
        kariyer = kariyer_baglantilari(asil_url, metin)
    except RobotsEngeli:
        durum = "robots-engeli"
    except requests.RequestException:
        durum = "erisilemedi"
    for k in kariyer:
        try:
            metin += http.sayfa(k)[1]
        except (requests.RequestException, RobotsEngeli):
            pass
    ats, slug = sayfadan_ats_bul(metin)
    if ats and not ats_calisiyor_mu(http, firma.ad, ats, slug):
        # Sitede bağlantı duruyor ama pano kapalı (ör. Complizen/Breezy 404): kaydedilirse tarama her gün 404 alır,
        # sıfırlanır, keşif bağlantıyı yine bulur → sonsuz döngü. Doğrulanmayan pano kaydedilmez.
        ats, slug = "", ""
    if not ats and yokla:
        ats, slug = ats_yokla(http, firma.ad, firma.web)
    if ats:
        durum = "tamam"
    return ats, slug, (kariyer[0] if kariyer else ""), durum


def _guvenli_kesfet(http: HttpIstemci, firma: FirmaBilgisi, yokla: bool) -> tuple[str, str, str, str]:
    try:
        return firmayi_kesfet(http, firma, yokla)
    except Exception as hata:  # tek firmanın beklenmedik hatası keşfin tamamını durdurmaz
        kayit.warning("%s: keşif hatası (%s: %s)", firma.ad, type(hata).__name__, str(hata)[:100])
        return "", "", "", "hata"


def _sonuclari_yaz(oturum: sessionmaker, sonuclar: list, sayac: Counter) -> None:
    with oturum.begin() as o:
        for f, (ats, slug, kariyer, durum) in sonuclar:
            if durum != "tamam":  # site bugün cevap vermedi: bilinenleri silme, bir sonraki keşifte yeniden dene
                sayac[durum] += 1
                continue
            depo.kesif_sonucu_yaz(o, f.id, ats, slug, kariyer)
            sayac["ats_bulunan"] += bool(ats)
            sayac["kariyer_bulunan"] += bool(kariyer)


def kesfet(
    ayar: Ayarlar,
    oturum: sessionmaker,
    sinir: int | None = None,
    yokla: bool = False,
    kaynak: str | None = None,
    http: HttpIstemci | None = None,
) -> dict:
    """Sonuçlar 100 firmada bir veritabanına yazılır: uzun keşif yarıda kesilse bile yapılan iş kaybolmaz."""
    http = http or HttpIstemci(ayar.kullanici_ajani, ayar.http_zaman_asimi)
    with oturum() as o:
        bekleyen = depo.kesif_bekleyenler(o, sinir=sinir, kaynak=kaynak)
    kayit.info("Keşif bekleyen firma: %d (yoklama: %s)", len(bekleyen), "açık" if yokla else "kapalı")
    sayac: Counter = Counter()
    tampon: list = []
    with ThreadPoolExecutor(max_workers=ayar.is_parcacigi) as havuz:
        gorevler = {havuz.submit(_guvenli_kesfet, http, f, yokla): f for f in bekleyen}
        for n, gorev in enumerate(as_completed(gorevler), start=1):
            tampon.append((gorevler[gorev], gorev.result()))
            if len(tampon) >= 100 or n == len(gorevler):
                _sonuclari_yaz(oturum, tampon, sayac)
                tampon = []
                kayit.info("Keşif: %d/%d firma | %s", n, len(gorevler), dict(sayac))
    return dict(sayac)
