"""Hazır ilan sistemlerinin (ATS) herkese açık API'lerinden ilan çeker.

Bu sistemler şirketlerin kendi sitelerinde ilan göstermesi için açık uç noktalar sunar; buradaki istekler bir
tarayıcının o şirketin kariyer sayfasını açarken yaptığı isteklerle aynıdır.

Her toplayıcı: (http istemcisi, firma adı, sistemdeki kısa ad) → list[Ilan]
Ayrıştırma (JSON → Ilan) fonksiyonları ağdan ayrıdır; böylece testlerde örnek JSON ile denenebilir.
"""

import datetime
import html
import re

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


TOPLAYICILAR = {
    "lever": lever,
    "greenhouse": greenhouse,
    "ashby": ashby,
    "workable": workable,
    "recruitee": recruitee,
    "smartrecruiters": smartrecruiters,
    "breezy": breezy,
    "workday": workday,
}
