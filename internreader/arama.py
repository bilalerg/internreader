"""Arama motoru keşfi: listemizde olmayan, Türkiye'de ilan açan firmaları arama API'siyle bulur.

Neden: firma listesi elle derlenen kaynaklardan geliyor; staj/junior ilanı açan pek çok firma (ör. 28.10.2026'da
LinkedIn'de görülen Kaizen Loyalty, Playable Factory) listede yoktu. İki tür sorgu atılır:
1. ATS sorguları: "site:jobs.lever.co Istanbul" gibi. Sonuç adresinden ilan sistemi + kısa ad çıkar; pano
   doğrulanır (en az bir ilanı Türkiye'de olmalı) ve firma doğrudan taranabilir hâlde eklenir.
2. Genel sorgular: "yazılım stajyeri İstanbul kariyer" gibi. İlan sitelerinin (LinkedIn, Kariyer.net, Youthall...)
   sonuçları atılır; kalan şirket alan adları web adresiyle eklenir, ardından mevcut keşif kariyer sayfasını bulur.

İlan sitelerinin sayfaları hiç açılmaz; yalnızca arama sonucundaki adres okunur (CLAUDE.md kuralı).
Arama sağlayıcısı API anahtarıyla çalışır (Serper ya da Brave); anahtar yoksa keşif atlanır, sistem çalışmaya devam eder.
"""

import datetime
import json
import logging
import re
import urllib.parse
from collections import Counter
from dataclasses import dataclass
from datetime import timedelta

import requests
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from internreader import depo
from internreader.ag import HttpIstemci, RobotsEngeli
from internreader.ayar import Ayarlar
from internreader.db import Firma, simdi
from internreader.isleme.filtre import TURKIYE
from internreader.kaynaklar.ats import TOPLAYICILAR
from internreader.kesif import KARIYER_LINKI, YANLIS_SAYFA, kesfet, sayfadan_ats_bul

kayit = logging.getLogger(__name__)

YERLER = ("Istanbul", "Türkiye")
ATS_ALANLARI = (
    "jobs.lever.co",
    "boards.greenhouse.io",
    "job-boards.greenhouse.io",
    "jobs.ashbyhq.com",
    "apply.workable.com",
    "jobs.smartrecruiters.com",
    "recruitee.com",
    "breezy.hr",
    "myworkdayjobs.com",
    "bamboohr.com",
    "teamtailor.com",
    "jobs.personio.de",
)
GENEL_SORGULAR = (
    "yazılım stajyeri ilanı İstanbul kariyer",
    "software engineer intern Istanbul careers",
    "junior software developer İstanbul açık pozisyonlar",
    "yarı zamanlı yazılım geliştirici öğrenci İstanbul",
    "yapay zeka stajyer İstanbul kariyer",
    "uzun dönem stajyer yazılım İstanbul",
    "working student software Istanbul",
    "yeni mezun yazılım mühendisi İstanbul kariyer",
)


def sorgular() -> list[str]:
    return [f"site:{alan} {yer}" for alan in ATS_ALANLARI for yer in YERLER] + list(GENEL_SORGULAR)


# Şirket sitesi olmayan alan adları: ilan siteleri/toplayıcılar, sosyal ağlar, haber ve bilgi siteleri.
# Bunlar firma olarak eklenmez; sayfaları da açılmaz.
SIRKET_DEGIL = re.compile(
    r"(?i)(^|\.)("
    r"linkedin|kariyer\.net|youthall|indeed|glassdoor|secretcv|eleman\.net|yenibiris|isbul|iskur|jooble|careerjet|"
    r"talent\.com|bebee|ziprecruiter|monster|wellfound|angel\.co|otta|remoteok|weworkremotely|builtin|"
    r"techcareer|coderspace|toptalent|anbean|stajim|stajyeri|kampusum|stajimvar|startupjobs|kariyerim\.com|"
    r"hiring\.cafe|jobs\.com|simplyhired|adzuna|whatjobs|jobrapido|jora|neuvoo|trovit|"
    r"google|youtube|facebook|instagram|twitter|x\.com|tiktok|reddit|medium|github|wikipedia|eksisozluk|"
    r"quora|stackoverflow|teknoloji|webtekno|shiftdelete|haberturk|hurriyet|milliyet|sozcu|ntv|cnnturk|"
    r"gov\.tr|edu\.tr|bel\.tr"
    r")(\.|$)"
)
# Arama sonucu başlığında firma adı olmayan, genel parçalar ("Kariyer | ACME" → "ACME")
GENEL_BASLIK = re.compile(
    r"(?i)^(kariyer|careers?|jobs?|iş ilanları|açık pozisyonlar|open positions|join us|bize katılın|insan kaynakları|"
    r"stajyer|intern(ship)?|home|anasayfa|ana sayfa|.*\b(ilan|pozisyon|position|vacanc)\w*)$"
)


@dataclass
class Sonuc:
    url: str
    baslik: str


# ---------- sağlayıcılar (ayrıştırma ağdan ayrı; testlerde örnek JSON'la denenir) ----------
def serper_ayristir(veri: dict) -> list[Sonuc]:
    return [Sonuc(r.get("link", ""), r.get("title", "")) for r in veri.get("organic", []) if r.get("link")]


def brave_ayristir(veri: dict) -> list[Sonuc]:
    return [
        Sonuc(r.get("url", ""), r.get("title", "")) for r in (veri.get("web") or {}).get("results", []) if r.get("url")
    ]


def ara(http: HttpIstemci, saglayici: str, anahtar: str, sorgu: str, adet: int = 20) -> list[Sonuc]:
    if saglayici == "serper":
        veri = http.json_gonder(
            "https://google.serper.dev/search",
            {"q": sorgu, "gl": "tr", "hl": "tr", "num": adet},
            basliklar={"X-API-KEY": anahtar},
        )
        return serper_ayristir(veri)
    if saglayici == "brave":
        adres = "https://api.search.brave.com/res/v1/web/search?" + urllib.parse.urlencode(
            {"q": sorgu, "count": adet, "country": "TR", "search_lang": "tr"}
        )
        return brave_ayristir(http.json_al(adres, basliklar={"X-Subscription-Token": anahtar}))
    raise ValueError(f"bilinmeyen arama sağlayıcısı: {saglayici}")


# ---------- sonuçlardan aday çıkarma (saf fonksiyonlar) ----------
def alan_adi(url: str) -> str:
    return urllib.parse.urlparse(url).netloc.lower().split(":")[0].removeprefix("www.")


def basliktan_ad(baslik: str, alan: str) -> str:
    """ "Kariyer | ACME Teknoloji" → "ACME Teknoloji". Başlıktan çıkmazsa alan adının ilk etiketi kullanılır."""
    parcalar = [p.strip() for p in re.split(r"\s+[|–—\-:·]\s+", baslik or "") if p.strip()]
    adaylar = [p for p in parcalar if not GENEL_BASLIK.match(p) and 2 <= len(p) <= 60]
    if adaylar:
        return adaylar[-1] if len(adaylar) > 1 else adaylar[0]
    return alan.split(".")[0].replace("-", " ").title()


GENEL_ETIKET = {"jobs", "job", "careers", "career", "kariyer", "www", "apply", "com", "co", "net", "org", "gen"}


def pano_etiketleri(slug: str) -> list[str]:
    """Panonun firmayı ele veren etiketleri. Kısa ad ("playable-factory") ya da Avature'da alan adının ayırt edici
    parçası ("jobs.siemens.com" → "siemens")."""
    ilk = slug.split("|")[0].lower()
    if "." in ilk:
        return [p for p in ilk.split(".")[:-1] if p not in GENEL_ETIKET]
    return [ilk]


def ats_adi(slug: str) -> str:
    """Pano kısa adından okunur bir firma adı: "playable-factory" → "Playable Factory"."""
    etiketler = pano_etiketleri(slug)
    ilk = etiketler[-1] if etiketler else slug.split("|")[0]
    return re.sub(r"[-_.]+", " ", ilk).strip().title() or slug


def adaylari_ayir(sonuclar: list[Sonuc]) -> tuple[dict[tuple[str, str], str], dict[str, str], int]:
    """(ATS adayları {(ats, slug): ad}, web adayları {alan adı: ad}, elenen sonuç sayısı)."""
    ats_adaylari: dict[tuple[str, str], str] = {}
    web_adaylari: dict[str, str] = {}
    elenen = 0
    for s in sonuclar:
        alan = alan_adi(s.url)
        if not alan or SIRKET_DEGIL.search(alan):  # ilan siteleri en başta elenir: adresleri hiç açılmaz
            elenen += 1
            continue
        ats, slug = sayfadan_ats_bul(s.url)
        if ats:
            ats_adaylari.setdefault((ats, slug), ats_adi(slug))
        else:
            web_adaylari.setdefault(alan, basliktan_ad(s.baslik, alan))
    return ats_adaylari, web_adaylari, elenen


def turkiye_panosu_mu(http: HttpIstemci, ats: str, slug: str, ad: str) -> bool:
    """Pano açılıyor ve en az bir ilanı Türkiye'de mi? (Dünyada aynı kısa adı kullanan başka firmaya karşı.)"""
    try:
        ilanlar = TOPLAYICILAR[ats](http, ad, slug)
    except Exception as hata:  # 404, bozuk akış vb. → aday elenir, diğerleri sürer
        kayit.debug("%s/%s doğrulanamadı: %s", ats, slug, hata)
        return False
    return any(TURKIYE.search(i.konum) for i in ilanlar)


# ---------- akış ----------
def arama_kesfi(
    ayar: Ayarlar,
    oturum: sessionmaker,
    sorgu_siniri: int | None = None,
    kuru: bool = False,
    http: HttpIstemci | None = None,
    kesif_yap: bool = True,
) -> dict:
    """Sorguları atar, adayları doğrular ve yeni firmaları ekler. Rapor sözlüğü döndürür.

    kuru=True: hiçbir şey yazılmaz; yalnızca bulunacak adaylar raporlanır (deneme için).
    kesif_yap: yeni eklenen web adaylarının kariyer sayfası/ATS keşfi hemen yapılır (yapay zekâ kullanmaz).
    """
    if not ayar.arama_saglayici:
        kayit.warning("Arama keşfi atlandı: SERPER_API_KEY ya da BRAVE_API_KEY tanımlı değil (.env.example).")
        return {"durum": "anahtar-yok"}
    http = http or HttpIstemci(ayar.kullanici_ajani, ayar.http_zaman_asimi)
    sayac: Counter = Counter()
    hatalar: list[str] = []
    sonuclar: list[Sonuc] = []
    for sorgu in sorgular()[:sorgu_siniri]:
        try:
            sonuclar += ara(http, ayar.arama_saglayici, ayar.arama_anahtari, sorgu)
            sayac["sorgu"] += 1
        except Exception as hata:  # tek sorgunun hatası (kota, ağ) keşfi durdurmaz
            hatalar.append(f"{sorgu}: {type(hata).__name__}")
            if "401" in str(hata) or "403" in str(hata):
                break  # anahtar geçersiz: kalan sorgular da başarısız olur, kota harcamayalım
    ats_adaylari, web_adaylari, elenen = adaylari_ayir(sonuclar)
    sayac.update(sonuc=len(sonuclar), elenen_ilan_sitesi=elenen)

    with oturum() as o:
        bilinen_panolar = {(f.ats, f.slug) for f in o.scalars(select(Firma).where(Firma.ats.is_not(None)))}
        webli = [(alan_adi(f.web), f.ad) for f in o.scalars(select(Firma).where(Firma.web.is_not(None))) if f.web]
        bilinen_alanlar = {alan for alan, _ in webli} | {a for (a,) in o.execute(select(Firma.anahtar))}
    # Listede web adresiyle duran firmanın panosu bulunursa yeni firma açılmaz, panosu o firmaya yazılır
    # (ör. "P.I. Works" / piworks.net ↔ piworks.bamboohr.com).
    etiketten_ad = {alan.split(".")[0].replace("-", ""): ad for alan, ad in webli}

    etiket = "arama_" + datetime.date.today().strftime("%Y%m%d")
    yeni_ats, yeni_web = [], []
    for (ats, slug), ad in ats_adaylari.items():
        mevcut = next(
            (etiketten_ad[e.replace("-", "")] for e in pano_etiketleri(slug) if e.replace("-", "") in etiketten_ad),
            None,
        )
        if (ats, slug) in bilinen_panolar:
            sayac["zaten_bilinen"] += 1
        elif turkiye_panosu_mu(http, ats, slug, mevcut or ad):
            yeni_ats.append((mevcut or ad, ats, slug))
        else:
            sayac["turkiye_disi_ya_da_kapali"] += 1
    for alan, ad in web_adaylari.items():
        if alan in bilinen_alanlar:
            sayac["zaten_bilinen"] += 1
        else:
            yeni_web.append((ad, f"https://{alan}"))

    sayac.update(yeni_ats=len(yeni_ats), yeni_web=len(yeni_web))
    rapor = {"durum": "kuru" if kuru else "tamam", **sayac, "hatalar": hatalar[:10]}
    rapor["ornekler"] = [f"{ad} ({ats})" for ad, ats, _ in yeni_ats[:10]] + [w for _, w in yeni_web[:10]]
    if kuru:
        return rapor
    with oturum.begin() as o:
        for ad, ats, slug in yeni_ats:
            depo.firma_ekle_veya_guncelle(o, ad, ats=ats, slug=slug, kaynak=etiket)
        for ad, web in yeni_web:
            depo.firma_ekle_veya_guncelle(o, ad, web=web, kaynak=etiket)
    if kesif_yap and yeni_web:
        kesfet(ayar, oturum, kaynak=etiket, http=http)
    kayit.info("Arama keşfi: %s", {k: v for k, v in rapor.items() if k not in ("hatalar", "ornekler")})
    return rapor


# ---------- adresi olmayan firmalara web adresi bulma ----------
def _sade(metin: str) -> str:
    tablo = str.maketrans("ıışğüöçİŞĞÜÖÇ", "iisguocisguoc")
    return re.sub(r"[^a-z0-9 ]", " ", metin.lower().translate(tablo))


ANLAMSIZ = {"teknoloji", "yazilim", "bilisim", "sanayi", "ticaret", "anonim", "sirketi", "ltd", "sti", "turkiye"}


def ad_alanla_uyusuyor_mu(ad: str, alan: str) -> bool:
    """Firma adının ayırt edici bir kelimesi (≥4 harf) alan adının ilk etiketinde geçiyor mu?
    "Siemens" ↔ "siemens.com.tr" evet; "Nova Spark X Teknoloji" ↔ "patika.dev" hayır (yanlış site eklenmesin)."""
    etiket = alan.split(".")[0].replace("-", "")
    kelimeler = [k for k in _sade(ad).split() if len(k) >= 4 and k not in ANLAMSIZ]
    return any(k in etiket for k in kelimeler)


YENIDEN_DENEME_GUNU = 90  # web adresi bulunamayan firma bu kadar gün yeniden aranmaz (kota boşa gitmesin)


def web_adresi_bul(
    ayar: Ayarlar,
    oturum: sessionmaker,
    sinir: int = 50,
    http: HttpIstemci | None = None,
    kuru: bool = False,
    kesif_yap: bool = True,
) -> dict:
    """Listede yalnızca adı olan (web adresi ve ilan sistemi bilinmeyen) firmalar için "<ad> kariyer" araması yapar;
    adla uyuşan ilk şirket alan adını web adresi olarak yazar ve o firmaların kariyer sayfası/ATS keşfini hemen yapar.

    Bulunamayan firmanın keşif tarihi işaretlenir; `YENIDEN_DENEME_GUNU` boyunca tekrar sorgulanmaz. Bulunanların keşif
    tarihi boş bırakılır ki normal keşif onları sıraya alsın."""
    if not ayar.arama_saglayici:
        return {"durum": "anahtar-yok"}
    http = http or HttpIstemci(ayar.kullanici_ajani, ayar.http_zaman_asimi)
    esik = simdi() - timedelta(days=YENIDEN_DENEME_GUNU)
    with oturum() as o:
        adsizlar = [
            (f.id, f.ad)
            for f in o.scalars(
                select(Firma)
                .where(Firma.web.is_(None), Firma.ats.is_(None), Firma.aktif.is_(True))
                .where((Firma.kesif_tarihi.is_(None)) | (Firma.kesif_tarihi < esik))
                .order_by(Firma.id)
                .limit(sinir)
            )
        ]
    bulunan: dict[str, str] = {}
    denenen: list[int] = []
    sayac: Counter = Counter()
    for firma_id, ad in adsizlar:
        try:
            sonuclar = ara(http, ayar.arama_saglayici, ayar.arama_anahtari, f'"{ad}" kariyer')
        except Exception as hata:
            sayac["hata"] += 1
            if "401" in str(hata) or "403" in str(hata):
                break
            continue
        sayac["sorgu"] += 1
        denenen.append(firma_id)
        for s in sonuclar:
            alan = alan_adi(s.url)
            if not alan or SIRKET_DEGIL.search(alan) or sayfadan_ats_bul(s.url)[0]:
                continue  # ilan sitesi ya da ATS panosu web adresi değildir (panolar arama keşfinde ayrıca bulunur)
            if ad_alanla_uyusuyor_mu(ad, alan):
                bulunan[ad] = f"https://{alan}"
                break
    sayac["bulunan"] = len(bulunan)
    rapor = {"durum": "kuru" if kuru else "tamam", **sayac, "ornekler": list(bulunan.items())[:10]}
    if kuru:
        return rapor
    etiket = "webbul_" + datetime.date.today().strftime("%Y%m%d")
    with oturum.begin() as o:
        for ad, web in bulunan.items():
            depo.firma_ekle_veya_guncelle(o, ad, web=web, kaynak=etiket)
        bulunan_adlar = set(bulunan)
        for f in o.scalars(select(Firma).where(Firma.id.in_(denenen))):
            if f.ad not in bulunan_adlar:
                f.kesif_tarihi = simdi()
    if kesif_yap and bulunan:
        kesfet(ayar, oturum, kaynak=etiket, http=http)
    return rapor


# ---------- web adresi olan ama kaynağı bulunamayan firmalara kariyer sayfası arama ----------
ONCELIK = ("girisim", "savunma_dogrulandi", "ai", "savunma")  # önce en çok işimize yarayacak firmalar
DENENEN_ANAHTARI = "kariyer_arama_denenen"  # denenen firma kimlikleri: kota aynı firmaya iki kez harcanmaz
KARIYER_ALT_ALANI = {"kariyer", "career", "careers", "jobs"}


def kariyer_adresi_mi(url: str, firma_alani: str) -> bool:
    """Arama sonucu, firmanın kendi sitesindeki bir kariyer sayfası mı? ("kariyer.firma.com" ya da "firma.com/careers")"""
    alan = alan_adi(url)
    if alan != firma_alani and not alan.endswith("." + firma_alani):
        return False
    yol = urllib.parse.urlparse(url).path
    if YANLIS_SAYFA.search(yol):
        return False
    return bool(KARIYER_LINKI.search(yol)) or alan.split(".")[0] in KARIYER_ALT_ALANI


def _oncelik(etiketler: list[str]) -> int:
    return next((n for n, e in enumerate(ONCELIK) if e in etiketler), len(ONCELIK))


def kariyer_sayfasi_ara(
    ayar: Ayarlar, oturum: sessionmaker, sinir: int = 40, http: HttpIstemci | None = None, kuru: bool = False
) -> dict:
    """Keşfin ana sayfadan bulamadığı kariyer sayfalarını "site:firma.com kariyer" aramasıyla bulur.
    Sayfada bir ilan sistemi bağlantısı varsa o da yazılır: ilanlar yapay zekâsız okunur. Sorgu başına bir arama kredisi."""
    if not ayar.arama_saglayici:
        return {"durum": "anahtar-yok"}
    http = http or HttpIstemci(ayar.kullanici_ajani, ayar.http_zaman_asimi)
    with oturum() as o:
        denenen = set(json.loads(depo.durum_al(o, DENENEN_ANAHTARI) or "[]"))
        adaylar = [
            (f.id, f.ad, f.anahtar, f.etiket or [])
            for f in o.scalars(
                select(Firma).where(
                    Firma.web.is_not(None), Firma.ats.is_(None), Firma.kariyer.is_(None), Firma.aktif.is_(True)
                )
            )
            if f.id not in denenen and not f.anahtar.startswith("ad:")
        ]
    adaylar.sort(key=lambda a: (_oncelik(a[3]), a[0]))
    sayac: Counter = Counter()
    bulunan: list[tuple[int, str, str, str, str]] = []
    for firma_id, ad, alan, _ in adaylar[:sinir]:
        sorgu = f'site:{alan} kariyer OR career OR jobs OR "açık pozisyon"'
        try:
            sonuclar = ara(http, ayar.arama_saglayici, ayar.arama_anahtari, sorgu, adet=10)
        except Exception as hata:  # tek sorgunun hatası taramayı durdurmaz; anahtar geçersizse kota harcanmaz
            sayac["hata"] += 1
            if "401" in str(hata) or "403" in str(hata):
                break
            continue
        sayac["sorgu"] += 1
        denenen.add(firma_id)
        adres = next((s.url for s in sonuclar if kariyer_adresi_mi(s.url, alan)), None)
        if not adres:
            continue
        try:
            ats, slug = sayfadan_ats_bul(http.sayfa(adres)[1])
        except RobotsEngeli:  # robots.txt izin vermiyorsa sayfa hiç kaydedilmez
            sayac["robots"] += 1
            continue
        except (requests.RequestException, ValueError):
            ats, slug = "", ""  # bugün açılmadı: sabah taraması yeniden dener
        bulunan.append((firma_id, ad, adres, ats, slug))
    sayac.update(bulunan=len(bulunan), ilan_sistemi=sum(1 for b in bulunan if b[3]))
    rapor = {
        "durum": "kuru" if kuru else "tamam",
        **sayac,
        "kalan": max(len(adaylar) - sinir, 0),
        "ornekler": [f"{ad}: {adres}" for _, ad, adres, _, _ in bulunan[:15]],
    }
    if kuru:
        return rapor
    with oturum.begin() as o:
        for firma_id, _, adres, ats, slug in bulunan:
            firma = o.get(Firma, firma_id)
            firma.kariyer = adres
            if ats:
                firma.ats, firma.slug = ats, slug
        depo.durum_yaz(o, DENENEN_ANAHTARI, json.dumps(sorted(denenen)))
    kayit.info("Kariyer sayfası araması: %s", {k: v for k, v in rapor.items() if k != "ornekler"})
    return rapor
