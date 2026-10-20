"""Değerlendirme: sınıflandırıcının doğruluğunu elle etiketlenmiş bir sette ölçer.

Prompt ya da model her değiştiğinde çalıştırılır; sonuçlar karşılaştırılır ("API bağlamak" ile "yapay zekâ
mühendisliği" arasındaki fark burada). Set: veri/degerlendirme/siniflandirma.jsonl — her satır bir ilan ve beklenen
seviye/rol. Beklenen alan null ise o örnekte o alan puanlanmaz (insanın da emin olamadığı durumlar).

Ölçülenler:
- seviye ve rol doğruluğu
- asıl karar "öğrenciye uygun mu": isabet (precision: uygun dediklerinin ne kadarı gerçekten uygun) ve kapsama
  (recall: gerçekten uygun olanların ne kadarını yakaladı). Kapsama düşükse öğrenci ilan kaçırır; isabet düşükse
  bülten çöple dolar.
"""

import json
from pathlib import Path

from internreader.model import HEDEF_ROLLER, OGRENCI_SEVIYELERI, Ilan
from internreader.yz.istemci import YzIstemci
from internreader.yz.siniflandirici import siniflandir


def seti_oku(yol: Path) -> list[dict]:
    return [json.loads(satir) for satir in yol.read_text(encoding="utf-8").splitlines() if satir.strip()]


def _uygun_mu(seviye: str | None, rol: str | None) -> bool | None:
    if seviye is None or rol is None:
        return None
    return seviye in OGRENCI_SEVIYELERI and rol in HEDEF_ROLLER


def _oran(pay: int, payda: int) -> float | None:
    return round(pay / payda, 3) if payda else None


def puanla(ornekler: list[dict], tahminler: list[dict | None]) -> dict:
    """ornekler[i] beklenenleri, tahminler[i] modelin kararını (ya da None: karar yok) içerir."""
    seviye = [
        o["beklenen_seviye"] == t["seviye"]
        for o, t in zip(ornekler, tahminler, strict=True)
        if t and o["beklenen_seviye"]
    ]
    rol = [o["beklenen_rol"] == t["rol"] for o, t in zip(ornekler, tahminler, strict=True) if t and o["beklenen_rol"]]
    dp = yp = yn = 0  # doğru pozitif, yanlış pozitif, yanlış negatif ("öğrenciye uygun" kararı)
    hatalar = []
    for o, t in zip(ornekler, tahminler, strict=True):
        if t is None:
            hatalar.append({"baslik": o["baslik"], "hata": "karar yok"})
            continue
        beklenen, tahmin = _uygun_mu(o["beklenen_seviye"], o["beklenen_rol"]), _uygun_mu(t["seviye"], t["rol"])
        if beklenen is not None:
            dp += beklenen and tahmin
            yp += (not beklenen) and tahmin
            yn += beklenen and not tahmin
        yanlis = [
            f"{alan}: beklenen {o['beklenen_' + alan]}, model {t[alan]}"
            for alan in ("seviye", "rol")
            if o[f"beklenen_{alan}"] and o[f"beklenen_{alan}"] != t[alan]
        ]
        if yanlis:
            hatalar.append(
                {"baslik": o["baslik"], "firma": o["firma"], "hata": "; ".join(yanlis), "gerekce": t.get("gerekce")}
            )
    return {
        "ornek": len(ornekler),
        "seviye_dogruluk": _oran(sum(seviye), len(seviye)),
        "rol_dogruluk": _oran(sum(rol), len(rol)),
        "ogrenciye_uygun_isabet": _oran(dp, dp + yp),
        "ogrenciye_uygun_kapsama": _oran(dp, dp + yn),
        "hatalar": hatalar,
    }


def degerlendir(yz: YzIstemci, ornekler: list[dict]) -> dict:
    ilanlar = [
        Ilan(
            firma=o["firma"],
            baslik=o["baslik"],
            url=f"degerlendirme://{n}",  # her örneğe ayrı kimlik
            kaynak=o.get("kaynak", ""),
            konum=o.get("konum", ""),
            calisma_tipi=o.get("calisma_tipi", ""),
            aciklama=o.get("aciklama", ""),
        )
        for n, o in enumerate(ornekler)
    ]
    kararlar = siniflandir(yz, ilanlar)
    sonuc = puanla(ornekler, [kararlar.get(i.kimlik) for i in ilanlar])
    sonuc |= {"model": yz.model, "maliyet_usd": round(yz.harcanan_usd, 5)}
    return sonuc
