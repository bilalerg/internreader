"""Şirket listesini kanıtla denetle; erişim başarısını faaliyet kanıtı sayma."""

import ipaddress
import re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import requests
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from internreader.ag import HttpIstemci, RobotsEngeli, hata_ozeti
from internreader.db import Firma, IlanDogrulama, IlanKaydi, simdi
from internreader.isleme.basvuru import alan_yasak

SON_KANIT_GUNU = 365
ACIK_ILAN_GUNU = 3
PARK = re.compile(r"domain (?:is |may be )?for sale|buy this domain|alan adı satılık|domain parking", re.I)


@dataclass(frozen=True)
class Sonuc:
    durum: str
    neden: str
    kanit_url: str | None = None
    kanit_tarihi: datetime | None = None


class Haberler(HTMLParser):
    """Yalnızca tarihli makale kartı: alt bilgideki yıl veya meta etiket kanıt değildir."""

    def __init__(self):
        super().__init__()
        self.derinlik = 0
        self.haberler: list[tuple[str, str, str]] = []
        self.tarih = self.href = ""
        self.baslik: list[str] = []
        self.baslik_derinligi = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "article":
            if self.derinlik == 0:
                self.tarih, self.href, self.baslik = "", "", []
            self.derinlik += 1
        elif self.derinlik:
            if tag == "time":
                self.tarih = a.get("datetime", "")
            elif tag == "a" and a.get("href") and not self.href:
                self.href = a["href"]
            elif tag in {"h1", "h2", "h3", "h4"}:
                self.baslik_derinligi += 1

    def handle_data(self, data):
        if self.derinlik and self.baslik_derinligi:
            self.baslik.append(data)

    def handle_endtag(self, tag):
        if tag in {"h1", "h2", "h3", "h4"} and self.baslik_derinligi:
            self.baslik_derinligi -= 1
        elif tag == "article" and self.derinlik:
            self.derinlik -= 1
            if not self.derinlik and self.tarih and self.href and "".join(self.baslik).strip():
                self.haberler.append((self.tarih, self.href, "".join(self.baslik).strip()))


def _yakin_tarih(metin: str, an: datetime) -> datetime | None:
    try:
        gun = date.fromisoformat(metin[:10])
    except ValueError:
        return None
    if an.date() - timedelta(days=SON_KANIT_GUNU) <= gun <= an.date():
        return datetime(gun.year, gun.month, gun.day, tzinfo=UTC)
    return None


def _adres_uygun(url: str) -> bool:
    try:
        p = urlsplit(url)
        host = p.hostname or ""
    except ValueError:
        return False
    try:
        ip = ipaddress.ip_address(host)
        herkese_acik = ip.is_global
    except ValueError:
        herkese_acik = bool(host and "." in host and not host.endswith((".local", ".internal")))
    return p.scheme in {"http", "https"} and herkese_acik and not alan_yasak(url)


def sayfa_kaniti(url: str, son_url: str, html: str, an: datetime) -> Sonuc:
    if PARK.search(re.sub(r"<[^>]+>", " ", html)[:5000]):
        return Sonuc("adres_sorunlu", "alan_adi_satis_veya_park")
    once, sonra = urlsplit(url).hostname or "", urlsplit(son_url).hostname or ""
    if once.removeprefix("www.") != sonra.removeprefix("www."):
        return Sonuc("belirsiz", "baska_alana_yonlendi")
    okur = Haberler()
    okur.feed(html)
    for tarih, href, _ in okur.haberler:
        kanit_tarihi = _yakin_tarih(tarih, an)
        kanit_url = urljoin(son_url, href)
        if (
            kanit_tarihi
            and _adres_uygun(kanit_url)
            and (urlsplit(kanit_url).hostname or "").removeprefix("www.") == sonra.removeprefix("www.")
        ):
            return Sonuc("faal", "tarihli_sirket_haberi", kanit_url, kanit_tarihi)
    return Sonuc("belirsiz", "guncel_faaliyet_kaniti_yok")


def _dogrulanmis_ilan(oturum, firma: Firma, an: datetime) -> Sonuc | None:
    sorgu = (
        select(IlanKaydi.url, IlanDogrulama.acik_dogrulama_zamani)
        .join(IlanDogrulama, IlanDogrulama.kimlik == IlanKaydi.kimlik)
        .where(
            IlanKaydi.firma == firma.ad,
            IlanKaydi.aktif.is_(True),
            IlanKaydi.gizli.is_(False),
            IlanDogrulama.durum == "acik",
            IlanDogrulama.acik_dogrulama_zamani >= an - timedelta(days=ACIK_ILAN_GUNU),
        )
        .order_by(IlanDogrulama.acik_dogrulama_zamani.desc())
        .limit(1)
    )
    kayit = oturum.execute(sorgu).first()
    if kayit:
        return Sonuc("faal", "basvurusu_dogrulanmis_ilan", kayit[0], kayit[1])
    return None


def _orneklem(firmalar: list[Firma], sinir: int) -> list[Firma]:
    # Kaynak ve ATS/kariyer/web varlığına göre dönüşümlü seçim: ilk 100 ID'ye bağlı yanlılığı önler.
    bekleyen = [f for f in firmalar if f.faaliyet_kontrol_zamani is None]
    if bekleyen:
        firmalar = bekleyen
    gruplar = defaultdict(list)
    for f in firmalar:
        kaynak = (f.kaynak or "belirsiz").split(",")[0]
        gruplar[(kaynak, bool(f.ats), bool(f.kariyer), bool(f.web))].append(f)
    gruplar = {
        k: sorted(v, key=lambda f: (f.faaliyet_kontrol_zamani.isoformat() if f.faaliyet_kontrol_zamani else "", f.id))
        for k, v in gruplar.items()
    }
    sonuc = []
    while len(sonuc) < sinir and any(gruplar.values()):
        for k in sorted(gruplar):
            if gruplar[k] and len(sonuc) < sinir:
                sonuc.append(gruplar[k].pop(0))
    return sonuc


def firmalari_denetle(
    oturum: sessionmaker, kullanici_ajani: str, sinir: int = 100, kuru: bool = True, http: HttpIstemci | None = None
) -> dict:
    if sinir < 1 or sinir > 500:
        raise ValueError("--sinir 1 ile 500 arasında olmalı")
    an = simdi()
    http = http or HttpIstemci(kullanici_ajani, zaman_asimi=15)
    with oturum() as o:
        firmalar = _orneklem(list(o.scalars(select(Firma).where(Firma.aktif.is_(True)).order_by(Firma.id))), sinir)
        adaylar = [(f.id, f.ad, f.web, f.kariyer, _dogrulanmis_ilan(o, f, an)) for f in firmalar]
    sayac = Counter()
    ornekler = []

    def kontrol(aday):
        firma_id, ad, web, kariyer, ilan_kaniti = aday
        if ilan_kaniti:
            sonuc = ilan_kaniti
        elif not web or not _adres_uygun(web):
            sonuc = Sonuc("belirsiz", "gecerli_web_adresi_yok")
        else:
            try:
                son_url, html = http.sayfa(web, adres_izinli=_adres_uygun)
                sonuc = sayfa_kaniti(web, son_url, html, an)
            except RobotsEngeli:
                sonuc = Sonuc("belirsiz", "robots_veya_adres_engeli")
            except requests.RequestException as hata:
                sonuc = Sonuc("belirsiz", hata_ozeti(hata))
            except (ValueError, UnicodeError):
                sonuc = Sonuc("belirsiz", "sayfa_okunamadi")
        return firma_id, ad, kariyer, sonuc

    with ThreadPoolExecutor(max_workers=6) as havuz:
        sonuclar = havuz.map(kontrol, adaylar)
        for firma_id, ad, kariyer, sonuc in sonuclar:
            sayac[sonuc.durum] += 1
            ornekler.append(
                {"firma": ad, "durum": sonuc.durum, "neden": sonuc.neden, "kanit": sonuc.kanit_url, "kariyer": kariyer}
            )
            if not kuru:
                with oturum.begin() as o:
                    f = o.get(Firma, firma_id)
                    f.faaliyet_durumu = sonuc.durum
                    f.faaliyet_neden = sonuc.neden
                    f.faaliyet_kontrol_zamani = an
                    f.faaliyet_kanit_url = sonuc.kanit_url
                    f.faaliyet_kanit_tarihi = sonuc.kanit_tarihi
    return {"denetlenen": len(adaylar), "kuru": kuru, "durumlar": dict(sayac), "sonuclar": ornekler}
