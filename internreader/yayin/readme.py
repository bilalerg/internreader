"""GitHub README tablosu: aktif bütün öğrenci ilanları, en yeni en üstte (SimplifyJobs listesi tarzında)."""

from datetime import datetime

from internreader.yayin import ROL_ADI, SEVIYE_ADI, guvenli_url, tarih_yazisi, turkiye_tarihi


def _hucre(metin: str) -> str:
    return (metin or "").replace("|", "/").replace("\n", " ").strip()


def tablo_metni(ilanlar: list[dict], an: datetime) -> str:
    satirlar = [
        "# InternReader — Türkiye yazılım ve yapay zekâ stajları",
        "",
        f"Son güncelleme: **{tarih_yazisi(an)}** · Açık ilan: **{len(ilanlar)}**",
        "",
        "İlanlar şirketlerin kendi kariyer sayfalarından ve ilan sistemlerinden her gün otomatik toplanır; "
        "yapay zekâ öğrenciye uygun olanları ayıklar. Başvuru, şirketin kendi sayfasında yapılır.",
        "",
        "| Firma | Pozisyon | Seviye | Alan | Konum | Eklenme | Başvuru |",
        "|---|---|---|---|---|---|---|",
    ]
    for i in ilanlar:
        alan = ROL_ADI.get(i["rol"], i["rol"]) + (" 🤖" if i["yapay_zeka"] in ("ozunde", "arti") else "")
        satirlar.append(
            f"| {_hucre(i.get('firma_gorunen') or i['firma'])} | {_hucre(i['baslik'])} | {SEVIYE_ADI.get(i['seviye'], i['seviye'])} | {alan} | "
            f"{_hucre(i['konum']) or 'Türkiye'} | {turkiye_tarihi(i['ilk_gorulme'])} | [Başvur]({guvenli_url(i['url'])}) |"
        )
    satirlar += ["", "🤖 = ilanda yapay zekâ işin özünde ya da tercih sebebi.", ""]
    return "\n".join(satirlar)
