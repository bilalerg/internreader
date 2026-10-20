"""Site için özet veri (istatistik.json): gerçek sayılar, şehir dağılımı ve simülasyonların kullandığı örnekler.

Site bu dosyayı hem derlenirken (ilk görüntü, arama motorları) hem de tarayıcıda (her sabahki güncel veri) okur.
ilanlar.json gibi herkese açık bir sözleşmedir: alan kaldırmak SURUM'ü artırır, eklemek artırmaz.
"""

import json
from collections import Counter
from datetime import datetime

from internreader.isleme.sehir import sehirleri_bul, uzaktan_mi
from internreader.yayin import gorunen_ad

SURUM = 1


def sehir_dagilimi(konumlar: list[str]) -> dict[str, int]:
    sayac: Counter = Counter()
    for konum in konumlar:
        for sehir in sehirleri_bul(konum):
            sayac[sehir] += 1
        if uzaktan_mi(konum):
            sayac["uzaktan"] += 1
    return dict(sayac.most_common())


def istatistik_metni(
    an: datetime,
    takip_edilen_firma: int,
    taranan_firma: int,
    aktif_ilan: int,
    ogrenci_ilani: int,
    konumlar: list[str],
    firma_adlari: list[str],
    kararlar: list[dict],
) -> str:
    veri = {
        "surum": SURUM,
        "guncelleme": an.isoformat(),
        "takip_edilen_firma": takip_edilen_firma,
        "taranan_firma": taranan_firma,
        "aktif_ilan": aktif_ilan,
        "ogrenci_ilani": ogrenci_ilani,
        "sehirler": sehir_dagilimi(konumlar),
        "firmalar": list(dict.fromkeys(gorunen_ad(a) for a in firma_adlari)),
        "kararlar": [{**k, "firma": gorunen_ad(k["firma"])} for k in kararlar],
    }
    return json.dumps(veri, ensure_ascii=False, indent=1)
