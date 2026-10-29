"""Hazır ilan sistemlerinin (ATS) herkese açık API'lerinden ilan çeker.

Bu sistemler şirketlerin kendi sitelerinde ilan göstermesi için açık uç noktalar sunar; buradaki istekler bir
tarayıcının o şirketin kariyer sayfasını açarken yaptığı isteklerle aynıdır.

Her toplayıcı: (http istemcisi, firma adı, sistemdeki kısa ad) → list[Ilan]
Ayrıştırma (JSON → Ilan) fonksiyonları ağdan ayrıdır; böylece testlerde örnek JSON ile denenebilir.
"""

import datetime
import email.utils
import html
import re
import urllib.parse
import xml.etree.ElementTree as ET

from internreader.ag import HttpIstemci
from internreader.model import Ilan


def duz_metin(icerik: str | None) -> str:
    """HTML'i düz metne çevirir."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", icerik or ""))).strip()


# ---------- ayrıştırıcılar (saf fonksiyonlar) ----------
def lever_ayristir(firma: str, veri: list) -> list[Ilan]:
    return [
        Ilan(
            firma=firma,
            baslik=j["text"],
            url=j["hostedUrl"],
            kaynak="lever",
            konum=(j.get("categories") or {}).get("location", "") or "",
            calisma_tipi=(j.get("categories") or {}).get("commitment", "") or "",
            tarih=datetime.date.fromtimestamp(j.get("createdAt", 0) / 1000).isoformat() if j.get("createdAt") else "",
            aciklama=j.get("descriptionPlain", "") or "",
        )
        for j in veri
    ]


def greenhouse_ayristir(firma: str, veri: dict) -> list[Ilan]:
    return [
        Ilan(
            firma=firma,
            baslik=j["title"],
            url=j["absolute_url"],
            kaynak="greenhouse",
            konum=(j.get("location") or {}).get("name", "") or "",
            tarih=(j.get("updated_at") or "")[:10],
            aciklama=duz_metin(html.unescape(j.get("content", "") or "")),
        )
        for j in veri.get("jobs", [])
    ]


def ashby_ayristir(firma: str, veri: dict) -> list[Ilan]:
    return [
        Ilan(
            firma=firma,
            baslik=j["title"],
            url=j["jobUrl"],
            kaynak="ashby",
            konum=(j.get("location", "") or "") + (" (uzaktan)" if j.get("isRemote") else ""),
            calisma_tipi=j.get("employmentType", "") or "",
            tarih=(j.get("publishedAt") or "")[:10],
            aciklama=j.get("descriptionPlain", "") or "",
        )
        for j in veri.get("jobs", [])
    ]


def workable_ayristir(firma: str, veri: dict) -> list[Ilan]:
    return [
        Ilan(
            firma=firma,
            baslik=j["title"],
            url=j["url"],
            kaynak="workable",
            konum=", ".join(x for x in (j.get("city"), j.get("country")) if x)
            + (" (uzaktan)" if j.get("telecommuting") else ""),
            calisma_tipi=j.get("employment_type", "") or "",
            tarih=(j.get("published_on") or "")[:10],
        )
        for j in veri.get("jobs", [])
    ]


def recruitee_ayristir(firma: str, veri: dict) -> list[Ilan]:
    return [
        Ilan(
            firma=firma,
            baslik=j["title"],
            url=j["careers_url"],
            kaynak="recruitee",
            konum=j.get("location", "") or "",
            calisma_tipi=j.get("employment_type_code", "") or "",
            tarih=(j.get("published_at") or "")[:10],
            aciklama=duz_metin(j.get("description")),
        )
        for j in veri.get("offers", [])
    ]


def smartrecruiters_ayristir(firma: str, slug: str, veri: dict) -> list[Ilan]:
    return [
        Ilan(
            firma=firma,
            baslik=j["name"],
            url=f"https://jobs.smartrecruiters.com/{slug}/{j['id']}",
            kaynak="smartrecruiters",
            konum=", ".join(
                x for x in ((j.get("location") or {}).get("city"), (j.get("location") or {}).get("country")) if x
            ),
            calisma_tipi=(j.get("typeOfEmployment") or {}).get("label", "") or "",
            tarih=(j.get("releasedDate") or "")[:10],
        )
        for j in veri.get("content", [])
    ]


def breezy_ayristir(firma: str, veri: list) -> list[Ilan]:
    return [
        Ilan(
            firma=firma,
            baslik=j["name"],
            url=j["url"],
            kaynak="breezy",
            konum=(j.get("location") or {}).get("name", "") or "",
            calisma_tipi=(j.get("type") or {}).get("name", "") or "",
            tarih=(j.get("published_date") or "")[:10],
        )
        for j in veri
    ]


def bamboohr_ayristir(firma: str, slug: str, veri: dict) -> list[Ilan]:
    def konum(j: dict) -> str:
        yer = j.get("location") or {}
        ats_yeri = j.get("atsLocation") or {}
        parcalar = (
            [yer.get("city"), yer.get("state")] if yer.get("city") else [ats_yeri.get("city"), ats_yeri.get("country")]
        )
        return ", ".join(x for x in parcalar if x) + (" (uzaktan)" if j.get("isRemote") else "")

    return [
        Ilan(
            firma=firma,
            baslik=j["jobOpeningName"],
            url=f"https://{slug}.bamboohr.com/careers/{j['id']}",
            kaynak="bamboohr",
            konum=konum(j),
            calisma_tipi=j.get("employmentStatusLabel", "") or "",
        )
        for j in veri.get("result", [])
    ]


def _rss_tarihi(yazi: str | None) -> str:
    try:
        return email.utils.parsedate_to_datetime(yazi).date().isoformat() if yazi else ""
    except (TypeError, ValueError):
        return ""


def teamtailor_ayristir(firma: str, xml_metin: str) -> list[Ilan]:
    """Teamtailor kariyer sitelerinin herkese açık RSS akışı (https://firma.teamtailor.com/jobs.rss)."""
    ilanlar = []
    for item in ET.fromstring(xml_metin).iter("item"):
        # Konumlar "tt:" ad alanındaki alt etiketlerde; şehir/ülke adlarını sırasıyla toplamak yeterli.
        yerler = [
            (e.text or "").strip()
            for e in item.iter()
            if e.tag.startswith("{https://teamtailor.com/locations}") and (e.text or "").strip()
        ]
        uzaktan = (item.findtext("remoteStatus") or "").strip().lower()
        ilanlar.append(
            Ilan(
                firma=firma,
                baslik=(item.findtext("title") or "").strip(),
                url=(item.findtext("link") or "").strip(),
                kaynak="teamtailor",
                konum=", ".join(dict.fromkeys(yerler))
                + {"fully": " (uzaktan)", "hybrid": " (hibrit)"}.get(uzaktan, ""),
                tarih=_rss_tarihi(item.findtext("pubDate")),
                aciklama=duz_metin(item.findtext("description")),
            )
        )
    return [i for i in ilanlar if i.baslik and i.url]


def personio_ayristir(firma: str, slug: str, xml_metin: str) -> list[Ilan]:
    """Personio'nun herkese açık XML akışı (https://firma.jobs.personio.de/xml)."""
    ilanlar = []
    for p in ET.fromstring(xml_metin).iter("position"):
        aciklama = " ".join(duz_metin(d.findtext("value")) for d in p.iter("jobDescription"))
        ilanlar.append(
            Ilan(
                firma=firma,
                baslik=(p.findtext("name") or "").strip(),
                url=f"https://{slug}.jobs.personio.de/job/{(p.findtext('id') or '').strip()}",
                kaynak="personio",
                konum=(p.findtext("office") or "").strip(),
                calisma_tipi=", ".join(
                    x
                    for x in ((p.findtext("employmentType") or "").strip(), (p.findtext("schedule") or "").strip())
                    if x
                ),
                tarih=(p.findtext("createdAt") or "")[:10],
                aciklama=aciklama.strip(),
            )
        )
    return [i for i in ilanlar if i.baslik and not i.url.endswith("/job/")]


def avature_ayristir(firma: str, xml_metin: str, konum: str) -> list[Ilan]:
    """Avature arama sonucu RSS'i. Akış konum vermediği için arama yapılan yer (ör. "Istanbul") konum yazılır.
    Akıştaki pubDate güvenilmez (27.10.2026'da açılan Siemens ilanında 2023 yazıyordu); tarih boş bırakılır."""
    return [
        Ilan(
            firma=firma,
            baslik=(item.findtext("title") or "").strip(),
            url=(item.findtext("link") or "").strip(),
            kaynak="avature",
            konum=konum,
            aciklama=duz_metin(item.findtext("description")),
        )
        for item in ET.fromstring(xml_metin).iter("item")
        if (item.findtext("title") or "").strip() and (item.findtext("link") or "").strip()
    ]


# ---------- toplayıcılar (ağ + ayrıştırma) ----------
def lever(http: HttpIstemci, firma: str, slug: str) -> list[Ilan]:
    return lever_ayristir(firma, http.json_al(f"https://api.lever.co/v0/postings/{slug}?mode=json"))


def greenhouse(http: HttpIstemci, firma: str, slug: str) -> list[Ilan]:
    return greenhouse_ayristir(
        firma, http.json_al(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true")
    )


def ashby(http: HttpIstemci, firma: str, slug: str) -> list[Ilan]:
    return ashby_ayristir(firma, http.json_al(f"https://api.ashbyhq.com/posting-api/job-board/{slug}"))


def workable(http: HttpIstemci, firma: str, slug: str) -> list[Ilan]:
    return workable_ayristir(firma, http.json_al(f"https://apply.workable.com/api/v1/widget/accounts/{slug}"))


def recruitee(http: HttpIstemci, firma: str, slug: str) -> list[Ilan]:
    return recruitee_ayristir(firma, http.json_al(f"https://{slug}.recruitee.com/api/offers/"))


def smartrecruiters(http: HttpIstemci, firma: str, slug: str) -> list[Ilan]:
    return smartrecruiters_ayristir(
        firma, slug, http.json_al(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100")
    )


def breezy(http: HttpIstemci, firma: str, slug: str) -> list[Ilan]:
    return breezy_ayristir(firma, http.json_al(f"https://{slug}.breezy.hr/json"))


def workday_tarihi(yazi: str, bugun: datetime.date | None = None) -> str:
    """Workday "Posted Today / Yesterday / 5 Days Ago / 30+ Days Ago" yazısını yaklaşık tarihe çevirir."""
    bugun = bugun or datetime.date.today()
    yazi = (yazi or "").lower()
    if "today" in yazi:
        gun = 0
    elif "yesterday" in yazi:
        gun = 1
    elif sayi := re.search(r"(\d+)\+?\s*days?", yazi):
        gun = int(sayi.group(1))
    else:
        return ""
    return (bugun - datetime.timedelta(days=gun)).isoformat()


def workday(http: HttpIstemci, firma: str, slug: str) -> list[Ilan]:
    """slug biçimi "kiracı|wdN|site" (ör. "analogdevices|wd1|External"). Workday şirket başına binlerce ilan tutabildiği
    için tüm liste yerine Türkiye ile ilgili aramalar yapılır ve birleştirilir."""
    kiraci, sunucu, site = slug.split("|")
    taban = f"https://{kiraci}.{sunucu}.myworkdayjobs.com"
    gorulen, ilanlar = set(), []
    for arama in ("Turkey", "Türkiye", "Istanbul"):
        for kaydirma in range(0, 200, 20):
            isler = http.json_gonder(
                f"{taban}/wday/cxs/{kiraci}/{site}/jobs",
                {"appliedFacets": {}, "limit": 20, "offset": kaydirma, "searchText": arama},
            ).get("jobPostings", [])
            for j in isler:
                yol = j.get("externalPath", "")
                if yol and yol not in gorulen:
                    gorulen.add(yol)
                    ilanlar.append(
                        Ilan(
                            firma=firma,
                            baslik=j.get("title", ""),
                            url=f"{taban}/{site}{yol}",
                            kaynak="workday",
                            konum=j.get("locationsText", "") or "",
                            tarih=workday_tarihi(j.get("postedOn", "")),
                        )
                    )
            if len(isler) < 20:
                break
    return ilanlar


def bamboohr(http: HttpIstemci, firma: str, slug: str) -> list[Ilan]:
    return bamboohr_ayristir(firma, slug, http.json_al(f"https://{slug}.bamboohr.com/careers/list"))


def teamtailor(http: HttpIstemci, firma: str, slug: str) -> list[Ilan]:
    return teamtailor_ayristir(firma, http.sayfa(f"https://{slug}.teamtailor.com/jobs.rss")[1])


def personio(http: HttpIstemci, firma: str, slug: str) -> list[Ilan]:
    return personio_ayristir(firma, slug, http.sayfa(f"https://{slug}.jobs.personio.de/xml")[1])


# Avature akışı arama başına en fazla 20 ilan döndürüyor ve sayfalama parametresini yok sayıyor (ölçüldü, 29.10.2026).
# Bu yüzden birkaç yer + seviye araması yapılıp birleştirilir.
AVATURE_ARAMALARI = (
    ("Istanbul", "Istanbul"),
    ("Turkey", "Turkey"),
    ("Türkiye", "Türkiye"),
    ("Istanbul student", "Istanbul"),
    ("Istanbul intern", "Istanbul"),
)


def avature(http: HttpIstemci, firma: str, slug: str) -> list[Ilan]:
    """slug biçimi "alan-adı|portal" (ör. "jobs.siemens.com|en_US/externaljobs"). Avature şirkete özel alan adlarında
    çalıştığı için kısa ad yerine sitenin kendisi tutulur. İstekler robots.txt denetiminden geçer."""
    alan, portal = slug.split("|")
    gorulen, ilanlar = set(), []
    for arama, konum in AVATURE_ARAMALARI:
        adres = f"https://{alan}/{portal}/SearchJobs/feed/?search={urllib.parse.quote(arama)}"
        for i in avature_ayristir(firma, http.sayfa(adres)[1], konum):
            kimlik = i.url.rstrip("/").rsplit("/", 1)[-1]  # aynı ilan yerelleştirilmiş farklı yollarla gelebilir
            if kimlik not in gorulen:
                gorulen.add(kimlik)
                ilanlar.append(i)
    return ilanlar


TOPLAYICILAR = {
    "lever": lever,
    "greenhouse": greenhouse,
    "ashby": ashby,
    "workable": workable,
    "recruitee": recruitee,
    "smartrecruiters": smartrecruiters,
    "breezy": breezy,
    "workday": workday,
    "bamboohr": bamboohr,
    "teamtailor": teamtailor,
    "personio": personio,
    "avature": avature,
}
