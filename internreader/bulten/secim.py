"""Bir ilan abonenin tercihlerine uyuyor mu?

Sitedeki "Bülteni dene" önizlemesiyle (web/src/components/Bulten.tsx → eslesir) AYNI kural: kullanıcı önizlemede ne
gördüyse e-postada onu alır. Kural değişirse ikisi birlikte değişir.

Boş ya da hiç olmayan tercih "hepsi" demektir: yeni tercihler (çalışma modeli, yalnızca girişimler) eklenmeden önce
kaydolan aboneler eskisi gibi her şeyi alır. İlanın kategorileri (alanlar, calisma_modeli, girisim) depoda kurallarla
eklenir (internreader/isleme/kategori.py).

Aynı ilan bir kez gider: kimlik (URL) ya da firma + başlık anahtarı (isleme/tekillestirme.py → ilan_anahtari) daha önce
gittiyse ya da aynı e-postada zaten seçildiyse ilan atlanır. Firma bir ilanı iki şehir için iki adresle yayınlasa da
öğrenci onu bir kez görür.
"""

from collections import Counter
from collections.abc import Set

from internreader.isleme.tekillestirme import ilan_anahtari

FIRMA_BASINA_AZAMI = 2  # bir e-postada aynı firmadan en fazla; kalanlar sonraki bültene kalır
YAKIN_ILAN_SAYISI = 5  # tam uyan ilan yokken gösterilen "yakın ilan" sayısı
# Tam uyan ilan yoksa önce en az önemli tercih gevşetilir; alan en son: yapay zekâ isteyene önce yapay zekâ gösterilir
GEVSETME_SIRASI = ("sadece_girisim", "calisma_modelleri", "sehirler", "seviyeler", "alanlar")


def eslesir(ilan: dict, tercihler: dict) -> bool:
    alanlar = set(tercihler.get("alanlar") or [])
    seviyeler = set(tercihler.get("seviyeler") or [])
    modeller = set(tercihler.get("calisma_modelleri") or [])
    sehirler = set(tercihler.get("sehirler") or [])
    if alanlar and not alanlar & set(ilan.get("alanlar") or [ilan["rol"]]):  # bir ilan birden çok alana girebilir
        return False
    if seviyeler and ilan["seviye"] not in seviyeler:
        return False
    if modeller and ilan.get("calisma_modeli", "belirsiz") not in modeller:  # belirtilmemiş model yalnızca "hepsi"de
        return False
    if tercihler.get("sadece_girisim") and not ilan.get("girisim"):
        return False
    if not sehirler:  # şehir seçilmemiş = fark etmez
        return True
    ilan_sehirleri = set(ilan.get("sehirler") or [])
    # Uzaktan ilan her şehirden yapılabilir. Konumunu yazmayan ilan (çoğu Türk şirketinin kendi sayfası) de dahil,
    # "konum belirtilmemiş" etiketiyle. Eski aboneliklerdeki "uzaktan" şehri bu yüzden ayrıca bir şey eklemez.
    uzak = ilan.get("uzaktan") or ilan.get("calisma_modeli") == "uzaktan"
    return bool(ilan_sehirleri & sehirler) or uzak or not ilan_sehirleri


def bulten_sec(ilanlar: list[dict], tercihler: dict, gonderilmis: Set[str], azami: int) -> list[dict]:
    """Abonenin bu bültende alacağı ilanlar. Sıra depodan gelir (isleme/guncellik.py → siralama_anahtari). Seçilmeyen
    ilan "gönderildi" sayılmaz: sınır ya da firma kotası yüzünden kalan ilan sonraki bültende gider.
    `gonderilmis`: aboneye daha önce giden ilanların kimlikleri ve firma + başlık anahtarları (depo.gonderilen_kimlikler).
    Anahtar yalnızca seçilen ilan için ayrılır: İstanbul'daki kopyası uymayan aboneye Ankara'daki kopyası gider."""
    secilen: list[dict] = []
    alinan = set(gonderilmis)
    firmalar: Counter[str] = Counter()
    for ilan in ilanlar:
        anahtar = ilan_anahtari(ilan["firma"], ilan["baslik"])
        if ilan["kimlik"] in alinan or anahtar in alinan or firmalar[ilan["firma"]] >= FIRMA_BASINA_AZAMI:
            continue
        if eslesir(ilan, tercihler):
            secilen.append(ilan)
            alinan.add(anahtar)
            firmalar[ilan["firma"]] += 1
            if len(secilen) >= azami:
                break
    return secilen


def yakin_ilanlar(
    ilanlar: list[dict], tercihler: dict, azami: int = YAKIN_ILAN_SAYISI, gonderilmis: Set[str] = frozenset()
) -> list[dict]:
    """Tam uyan ilan yokken: tercihler teker teker gevşetilir, ilk sonuç veren adımın ilanları döner. Daha önce
    gönderilenler (`gonderilmis`) yeniden önerilmez."""
    gevsek = dict(tercihler)
    for anahtar in GEVSETME_SIRASI:
        if gevsek.pop(anahtar, None) and (secilen := bulten_sec(ilanlar, gevsek, gonderilmis, azami)):
            return secilen
    return []
