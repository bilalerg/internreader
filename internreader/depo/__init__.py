"""Depo katmanı: veritabanına yazan/okuyan bütün işlemler burada.

Geri kalan kod SQL bilmez; "ilanları kaydet", "yayınlanacak ilanları getir" gibi işlevleri çağırır.
Böylece veritabanı (SQLite → Postgres) değişse bile yalnızca bu paket ve db.py etkilenir.
Konulara bölünmüştür; dışarıya tek bir ad alanı olarak açılır: from internreader import depo; depo.aktif_firmalar(...)
"""

from internreader.depo._ortak import (
    utc,
)
from internreader.depo.aboneler import (
    abone_ekle,
    abone_eposta_ile,
    abone_id_ile,
    abone_onay_ozeti_ile,
    abone_sayilari,
    abone_sil,
    onaylanmamislari_sil,
)
from internreader.depo.ayrintilar import (
    ayrinti_bekleyenler,
    ayrinti_kaydet,
    ayrinti_sayisi,
)
from internreader.depo.bulten import (
    HAFTALIK_ARALIK,
    bulten_istatistigi,
    bulten_kaydet,
    eski_gonderimleri_sil,
    gonderilen_kimlikler,
    gonderim_kaydet,
    gonderime_hazir_aboneler,
)
from internreader.depo.durum import (
    durum_al,
    durum_yaz,
)
from internreader.depo.firmalar import (
    aktif_firmalar,
    ats_kaydini_sifirla,
    firma_anahtari,
    firma_ekle_veya_guncelle,
    firmayi_kapat,
    kesif_bekleyenler,
    kesif_sonucu_yaz,
)
from internreader.depo.ilanlar import (
    ilanlari_kaydet,
    imzayla_kararlar,
    kapali_ilan_metinlerini_temizle,
    siniflandirilmamislar,
    siniflandirma_kaydet,
    yayinlanacak_ilanlar,
)
from internreader.depo.kullanim import (
    bu_ay_harcanan,
    kullanim_yaz,
)
from internreader.depo.onbellek import (
    onbellek_hepsi,
    onbellek_yaz,
    url_ozeti,
)
from internreader.depo.ozet import (
    aktif_konumlar,
    istatistik,
    ornek_firma_adlari,
    ornek_kararlar,
    takip_edilen_firma_sayisi,
    taranan_firma_sayisi,
)

__all__ = [
    "kapali_ilan_metinlerini_temizle",
    "ayrinti_bekleyenler",
    "ayrinti_kaydet",
    "ayrinti_sayisi",
    "HAFTALIK_ARALIK",
    "bulten_istatistigi",
    "bulten_kaydet",
    "eski_gonderimleri_sil",
    "gonderilen_kimlikler",
    "gonderim_kaydet",
    "gonderime_hazir_aboneler",
    "imzayla_kararlar",
    "utc",
    "firma_anahtari",
    "firma_ekle_veya_guncelle",
    "firmayi_kapat",
    "aktif_firmalar",
    "kesif_bekleyenler",
    "kesif_sonucu_yaz",
    "ats_kaydini_sifirla",
    "ilanlari_kaydet",
    "siniflandirilmamislar",
    "siniflandirma_kaydet",
    "yayinlanacak_ilanlar",
    "url_ozeti",
    "onbellek_hepsi",
    "onbellek_yaz",
    "kullanim_yaz",
    "bu_ay_harcanan",
    "durum_al",
    "durum_yaz",
    "taranan_firma_sayisi",
    "takip_edilen_firma_sayisi",
    "aktif_konumlar",
    "ornek_firma_adlari",
    "ornek_kararlar",
    "istatistik",
    "abone_eposta_ile",
    "abone_id_ile",
    "abone_onay_ozeti_ile",
    "abone_ekle",
    "abone_sil",
    "onaylanmamislari_sil",
    "abone_sayilari",
]
