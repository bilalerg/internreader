"""Jooble API'sinden Türkiye ilanları (haftada bir; boru.py).

Öğrenci ilanlarının bir kısmı firmanın kendi sitesinde değil, ilan sitelerinde duruyor (yenibiris, secretcv...).
Jooble, API sonuçlarının başka sitede gösterilmesine izin veriyor (jooble.org/api/about).

- Anahtar ülkeye özel: tr.jooble.org/api/about formundan alınır, yalnız tr.jooble.org'da çalışır. Adreste gittiği için
  hata metni kayda yazılmaz (ag.hata_ozeti).
- Sınır: anahtar başına varsayılan 500 istek (toplam mı dönemlik mi yazmıyor). Bir tarama SORGULAR kadar istek harcar.
- İlan sayfaları (/desc/) robots.txt'te kapalı: okunmaz, yalnızca öğrenci tıklar. Metin olarak API'nin özeti kullanılır.
- Ölçüm (31.10.2026, 15 sorgu x 100 sonuç): 845 tekil ilan, başlığına göre 18'i teknik öğrenci ilanı. Arama gevşek
  eşleşiyor; yapay zekâ maliyeti için ön eleme şart.
"""

import re
from datetime import date, timedelta

from internreader.ag import HttpIstemci
from internreader.isleme.filtre import JUNIOR, STAJ, YARI_ZAMANLI, YENI_MEZUN
from internreader.isleme.tekillestirme import ilan_anahtari
from internreader.kaynaklar.ats import duz_metin
from internreader.model import Ilan

ADRES = "https://tr.jooble.org/api/"
PENCERE = timedelta(days=60)
SORGULAR = (
    "yazılım stajyeri",
    "stajyer yazılım geliştirici",
    "software engineering intern",
    "software intern",
    "data intern",
    "machine learning intern",
    "yapay zeka stajyeri",
    "game developer intern",
    "junior software developer",
    "junior developer",
    "yeni mezun yazılım mühendisi",
    "yarı zamanlı yazılım",
    "uzun dönem stajyer yazılım",
    "bilgisayar mühendisliği stajyer",
    "veri analisti stajyer",
)

_YASAK_KAYNAK = re.compile(r"(?i)linkedin|kariyer\.net|youthall|indeed")
_TEKNIK = re.compile(
    r"(?i)yazılım|software|developer|geliştirici|programc|\bveri\b|\bdata\b|yapay zeka|\bai\b|machine learning|"
    r"makine öğren|oyun (geliştir|program|yazılım)|\bgame\b|backend|back-end|frontend|front-end|full ?stack|devops|siber|cyber|"
    r"bilgisayar mühendis|\bqa\b|mobil|\bios\b|android|gömülü|embedded|robot|bilişim|\bit\b"
)


def jooble_ayristir(veri: dict) -> list[Ilan]:
    """Arama adresleri (`link`) sorguya göre değişir; kimlik Jooble'ın değişmeyen ilan numarasından türetilir."""
    ilanlar = []
    for j in veri.get("jobs", []):
        firma, baslik, link = (j.get("company") or "").strip(), duz_metin(j.get("title")), j.get("link") or ""
        if not (firma and baslik and link) or _YASAK_KAYNAK.search(j.get("source") or ""):
            continue
        ilanlar.append(
            Ilan(
                firma=firma,
                baslik=baslik,
                url=link,
                kalici_url=f"jooble:{j.get('id') or link}",
                kaynak="jooble",
                konum=j.get("location") or "",
                calisma_tipi=j.get("type") or "",
                tarih=(j.get("updated") or "")[:10],
                aciklama=duz_metin(j.get("snippet")),
            )
        )
    return ilanlar


def on_elemeden_gecer_mi(ilan: Ilan) -> bool:
    """Başlıkta ya da iş türünde öğrenci işareti, başlıkta ya da özette teknik iş. Asıl kararı yapay zekâ verir."""
    seviye = f"{ilan.baslik} {ilan.calisma_tipi}"
    return any(d.search(seviye) for d in (STAJ, JUNIOR, YENI_MEZUN, YARI_ZAMANLI)) and bool(
        _TEKNIK.search(f"{ilan.baslik} {ilan.aciklama}")
    )


def jooble_tara(http: HttpIstemci, anahtar: str, bugun: date, sorgular: tuple[str, ...] = SORGULAR) -> list[Ilan]:
    """İlk hatada durur (anahtar geçersizse ya da sınır dolduysa istek hakkı boşa gitmez); hatayı çağıran yakalar."""
    tekil: dict[str, Ilan] = {}
    for sorgu in sorgular:
        veri = http.json_gonder(
            ADRES + anahtar,
            {
                "keywords": sorgu,
                "location": "Türkiye",
                "ResultOnPage": "100",
                "datecreatedfrom": (bugun - PENCERE).isoformat(),
            },
        )
        for ilan in jooble_ayristir(veri):
            if on_elemeden_gecer_mi(ilan):
                tekil.setdefault(ilan_anahtari(ilan.firma, ilan.baslik), ilan)
    return list(tekil.values())
