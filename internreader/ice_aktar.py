"""Dışarıdan veri alma: firma listeleri (CSV) ve eski sayfa önbelleği (JSON) veritabanına aktarılır."""

import csv
import hashlib
import json
import logging
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from internreader import depo

kayit = logging.getLogger(__name__)


def firmalari_ice_aktar(oturum: sessionmaker, yol: Path, kaynak: str = "") -> dict:
    """CSV sütunları: ad, web, ats, slug, kariyer, etiket (virgülle), kaynak. Olmayan sütunlar boş sayılır."""
    csv.field_size_limit(10**8)
    yeni = guncellenen = 0
    with open(yol, encoding="utf-8-sig") as f, oturum.begin() as o:
        for r in csv.DictReader(f):
            ad = (r.get("ad") or "").strip()
            if not ad:
                continue
            eklendi = depo.firma_ekle_veya_guncelle(
                o,
                ad=ad,
                web=(r.get("web") or "").strip(),
                ats=(r.get("ats") or "").strip(),
                slug=(r.get("slug") or "").strip(),
                kariyer=(r.get("kariyer") or "").strip(),
                etiket=[e.strip() for e in (r.get("etiket") or "").split(",")],
                kaynak=kaynak or (r.get("kaynak") or "").strip(),
            )
            yeni += eklendi
            guncellenen += not eklendi
            o.flush()  # aynı dosyada tekrar eden firma bir sonraki satırda bulunabilsin
    kayit.info("%s: %d yeni firma, %d mevcut firma güncellendi", yol.name, yeni, guncellenen)
    return {"yeni": yeni, "guncellenen": guncellenen}


def firma_listesini_esitle(oturum: sessionmaker, yol: Path) -> bool:
    """firmalar.csv değiştiyse (elle eklenen "girisim", "kurumsal", "savunma_dogrulandi" etiketleri) veritabanına aktarır.
    Sabah işinin başında çalışır; dosya aynıysa hiçbir şey yapmaz. Etiket eklenir, silinmez."""
    if not yol.exists():
        return False
    ozet = hashlib.sha256(yol.read_bytes()).hexdigest()
    with oturum() as o:
        if depo.durum_al(o, "firmalar_csv_ozeti") == ozet:
            return False
    firmalari_ice_aktar(oturum, yol)
    with oturum.begin() as o:
        depo.durum_yaz(o, "firmalar_csv_ozeti", ozet)
    return True


def eski_onbellegi_ice_aktar(oturum: sessionmaker, yol: Path) -> int:
    """Eski okuyucunun sayfa_onbellek.json dosyasını aktarır; aynı sayfalar için tekrar para harcanmaz."""
    if not yol.exists():
        return 0
    eski = json.loads(yol.read_text(encoding="utf-8"))
    kayitlar = {}
    for url, v in eski.items():
        if "hash" not in v:
            continue
        pozisyonlar = [
            {
                "baslik": p["baslik"],
                "link": p.get("link"),
                "konum": p.get("konum"),
                "seviye": p.get("seviye") or p.get("tur") or "belirsiz",
            }
            for p in v.get("pozisyonlar", [])
        ]
        kayitlar[url] = (depo.url_ozeti(url), v["hash"], {"pozisyonlar": pozisyonlar, "atilan": v.get("atilan", [])})
    with oturum.begin() as o:
        depo.onbellek_yaz(o, kayitlar)
    kayit.info("Eski önbellekten %d sayfa aktarıldı", len(kayitlar))
    return len(kayitlar)
