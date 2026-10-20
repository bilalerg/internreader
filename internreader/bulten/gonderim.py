"""Bülten gönderimi: her aboneye, tercihlerine uyan ve ona daha önce gönderilmemiş ilanlar.

Kurallar:
- Yeni ilan yoksa e-posta gitmez.
- Aynı ilan bir aboneye iki kez gitmez (gonderimler tablosu).
- Her abone ayrı bir veritabanı işlemiyle kaydedilir: gönderim yarıda kesilse (sunucu çökse) bile, e-postası
  gitmiş aboneye ertesi çalıştırmada aynı ilanlar tekrar gitmez.
- Bir e-postada en fazla AZAMI_ILAN ilan; fazlası bir sonraki bültene kalır.
- Bir abonenin e-postası gönderilemezse (adres reddi vb.) diğerleri etkilenmez; hata kaydedilir.
"""

import logging
from contextlib import nullcontext
from datetime import datetime

from sqlalchemy.orm import sessionmaker

from internreader import depo
from internreader.abonelik import iptal_jetonu
from internreader.ayar import GELISTIRME_ANAHTARI, Ayarlar
from internreader.bulten.sablon import AZAMI_ILAN, bulten_epostasi
from internreader.bulten.secim import eslesir
from internreader.db import simdi
from internreader.eposta import EpostaGonderici
from internreader.yayin import zenginlestir
from internreader.yayin.whatsapp import taze_mi

kayit = logging.getLogger(__name__)


def bultenleri_gonder(
    oturum: sessionmaker, gonderici: EpostaGonderici, ayar: Ayarlar, an: datetime | None = None
) -> dict:
    if ayar.smtp_sunucu and ayar.gizli_anahtar == GELISTIRME_ANAHTARI:
        # Çıkış bağlantıları API'nin doğrulayamayacağı anahtarla imzalanırdı: kimse abonelikten çıkamazdı
        raise RuntimeError("Gerçek e-posta gönderimi için INTERNREADER_GIZLI_ANAHTAR tanımlı olmalı (API ile aynı)")
    an = an or simdi()
    with oturum() as o:
        ilanlar = [i for i in (zenginlestir(x) for x in depo.yayinlanacak_ilanlar(o)) if taze_mi(i, an)]
        aboneler = [(a.id, a.eposta, dict(a.tercihler or {}), a.siklik) for a in depo.gonderime_hazir_aboneler(o, an)]

    rapor = {"hazir_abone": len(aboneler), "gonderilen": 0, "bos": 0, "hata": 0, "ilan": 0}
    # SMTP göndericisi bağlam yöneticisiyse bütün e-postalar tek bağlantıdan gider
    baglam = gonderici if hasattr(gonderici, "__enter__") else nullcontext(gonderici)
    with baglam as g:
        for abone_id, eposta, tercihler, siklik in aboneler:
            with oturum() as o:
                gonderilmis = depo.gonderilen_kimlikler(o, abone_id)
            secilen = [i for i in ilanlar if i["kimlik"] not in gonderilmis and eslesir(i, tercihler)][:AZAMI_ILAN]
            if not secilen:
                rapor["bos"] += 1
                continue
            jeton = iptal_jetonu(abone_id, ayar.gizli_anahtar)
            ileti = bulten_epostasi(
                alici=eposta,
                ilanlar=secilen,
                an=an,
                site_adresi=ayar.site_adresi,
                iptal_adresi=f"{ayar.site_adresi}/iptal?jeton={jeton}",
                tek_tik_adresi=f"{ayar.site_adresi}/api/abone/iptal-tek?jeton={jeton}",
                siklik=siklik,
            )
            try:
                g.gonder(ileti)
                durum = "gonderildi"
            except Exception:  # tek abonenin hatası diğerlerini durdurmaz
                kayit.exception("Bülten gönderilemedi (abone %d)", abone_id)
                durum = "hata"
            with oturum.begin() as o:
                if durum == "gonderildi":
                    depo.gonderim_kaydet(o, depo.abone_id_ile(o, abone_id), [i["kimlik"] for i in secilen], an)
                depo.bulten_kaydet(o, abone_id, len(secilen), durum, an)
            rapor["gonderilen" if durum == "gonderildi" else "hata"] += 1
            rapor["ilan"] += len(secilen) if durum == "gonderildi" else 0
    kayit.info("Bülten: %s", rapor)
    return rapor
