"""Bir ilan abonenin tercihlerine uyuyor mu?

Sitedeki "Bülteni dene" önizlemesiyle (web/src/components/Bulten.tsx → eslesir) AYNI kural: kullanıcı önizlemede ne
gördüyse e-postada onu alır. Kural değişirse ikisi birlikte değişir.
"""


def eslesir(ilan: dict, tercihler: dict) -> bool:
    alanlar = set(tercihler.get("alanlar") or [])
    seviyeler = set(tercihler.get("seviyeler") or [])
    sehirler = set(tercihler.get("sehirler") or [])
    if alanlar and ilan["rol"] not in alanlar:
        return False
    if seviyeler and ilan["seviye"] not in seviyeler:
        return False
    if not sehirler:  # şehir seçilmemiş = fark etmez
        return True
    ilan_sehirleri = set(ilan.get("sehirler") or [])
    if ilan_sehirleri & sehirler or ("uzaktan" in sehirler and ilan.get("uzaktan")):
        return True
    # Konumunu yazmayan ilan (çoğu Türk şirketinin kendi sayfası): dahil, "konum belirtilmemiş" etiketiyle
    return not ilan_sehirleri and not ilan.get("uzaktan")
