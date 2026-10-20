"""Günlük WhatsApp özeti: son özetten bu yana İLK KEZ görülen öğrenci ilanlarını kopyala-yapıştır metnine çevirir.

WhatsApp kanallarına otomatik paylaşımın resmî bir yolu yok; resmî olmayan araçlar hesap kapatma riski taşır.
Bu yüzden sistem metni hazırlar, paylaşımı bir insan yapar (günde ~1 dakika).
"""

from datetime import datetime, timedelta

from internreader.yayin import ROL_ADI, SEVIYE_ADI, tarih_yazisi

AZAMI_ILAN = 15  # tek mesaj okunabilir kalsın; fazlası için tam listeye yönlendir
TAZELIK_GUNU = 45  # kaynağın verdiği yayın tarihi bundan eskiyse "yeni ilan" diye duyurulmaz


def taze_mi(ilan: dict, an: datetime) -> bool:
    """Bizim için ilk kez görülen ama kaynakta aylardır açık olan ilan (ör. yeni eklenen firmanın 2 yıllık ilanı)
    günlük özete girmez; tabloda kalır. Yayın tarihi bilinmiyorsa taze sayılır."""
    tarih = ilan.get("yayin_tarihi") or ""
    return not tarih or tarih >= (an - timedelta(days=TAZELIK_GUNU)).date().isoformat()


def ozet_metni(ilanlar: list[dict], an: datetime, tam_liste_linki: str = "") -> str | None:
    """Yeni ilan yoksa None döner (o gün paylaşım yapılmaz)."""
    if not ilanlar:
        return None
    satirlar = [f"🎯 InternReader · {tarih_yazisi(an)}", f"{len(ilanlar)} yeni staj / junior ilanı", ""]
    for no, i in enumerate(ilanlar[:AZAMI_ILAN], start=1):
        etiketler = [SEVIYE_ADI.get(i["seviye"], i["seviye"]), ROL_ADI.get(i["rol"], i["rol"])]
        if i["yapay_zeka"] == "ozunde":
            etiketler.append("🤖 yapay zekâ işi")
        elif i["yapay_zeka"] == "arti":
            etiketler.append("🤖 AI artı")
        konum = i["konum"] or "Türkiye"
        satirlar += [
            f"{no}) *{i.get('firma_gorunen') or i['firma']}* — {i['baslik']}",
            f"   📍 {konum} · {' · '.join(etiketler)}",
            f"   🔗 {i['url']}",
            "",
        ]
    if len(ilanlar) > AZAMI_ILAN:
        satirlar.append(f"+{len(ilanlar) - AZAMI_ILAN} ilan daha" + (f": {tam_liste_linki}" if tam_liste_linki else ""))
    elif tam_liste_linki:
        satirlar.append(f"Tüm açık ilanlar: {tam_liste_linki}")
    satirlar.append("Bir arkadaşına lazım olabilir, paylaş 🙌")
    return "\n".join(satirlar).strip()
