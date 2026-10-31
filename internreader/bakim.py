"""Günlük bakım: veritabanında gereğinden fazla veri tutulmaz (KVKK'nın "en az veri" ilkesi + disk).

- Onaylanmayan abonelik istekleri: 72 saat sonra silinir.
- Gönderim kayıtları: kapanmış ilanların 180 günden eski kayıtları silinir. Açık ilanın kaydı (ve aynı firma +
  başlıkla hâlâ açık kopyası olanınki) kalır: silinseydi aylardır açık duran ilan aynı aboneye yeniden giderdi.
- Kapalı ilanların açıklama metni: 60 gün sonra boşaltılır (başlık, firma ve yapay zekâ kararı kalır).
- Tıklama kayıtları: 180 günden eskiler silinir.
- Jooble ilanları: 21 gün aramalarda görülmezse kapanır (Jooble haftada bir taranır; iki kaçırılan tarama ilanı düşürmez).
"""

import logging
from datetime import timedelta

from sqlalchemy.orm import sessionmaker

from internreader import abonelik, depo
from internreader.db import simdi

kayit = logging.getLogger(__name__)

GONDERIM_SAKLAMA = timedelta(days=180)
KAPALI_ILAN_METNI_SAKLAMA = timedelta(days=60)
TIKLAMA_SAKLAMA = timedelta(days=180)
JOOBLE_ILAN_OMRU = timedelta(days=21)


def bakim_yap(oturum: sessionmaker) -> dict:
    an = simdi()
    with oturum.begin() as o:
        sonuc = {
            "onaylanmayan_abonelik": abonelik.suresi_dolanlari_temizle(o),
            "eski_gonderim": depo.eski_gonderimleri_sil(o, an - GONDERIM_SAKLAMA),
            "kapali_ilan_metni": depo.kapali_ilan_metinlerini_temizle(o, an - KAPALI_ILAN_METNI_SAKLAMA),
            "eski_tiklama": depo.eski_tiklamalari_sil(o, an - TIKLAMA_SAKLAMA),
            "gorulmeyen_jooble": depo.gorulmeyen_jooble_ilanlarini_kapat(o, an - JOOBLE_ILAN_OMRU),
        }
    kayit.info("Bakım: %s", sonuc)
    return sonuc
