"""Günlük bakım: veritabanında gereğinden fazla veri tutulmaz (KVKK'nın "en az veri" ilkesi + disk).

- Onaylanmayan abonelik istekleri: 72 saat sonra silinir.
- Gönderim kayıtları: 180 günden eskiler silinir (o ilanlar çoktan kapanmıştır).
- Kapalı ilanların açıklama metni: 60 gün sonra boşaltılır (başlık, firma ve yapay zekâ kararı kalır).
"""

import logging
from datetime import timedelta

from sqlalchemy.orm import sessionmaker

from internreader import abonelik, depo
from internreader.db import simdi

kayit = logging.getLogger(__name__)

GONDERIM_SAKLAMA = timedelta(days=180)
KAPALI_ILAN_METNI_SAKLAMA = timedelta(days=60)


def bakim_yap(oturum: sessionmaker) -> dict:
    an = simdi()
    with oturum.begin() as o:
        sonuc = {
            "onaylanmayan_abonelik": abonelik.suresi_dolanlari_temizle(o),
            "eski_gonderim": depo.eski_gonderimleri_sil(o, an - GONDERIM_SAKLAMA),
            "kapali_ilan_metni": depo.kapali_ilan_metinlerini_temizle(o, an - KAPALI_ILAN_METNI_SAKLAMA),
        }
    kayit.info("Bakım: %s", sonuc)
    return sonuc
