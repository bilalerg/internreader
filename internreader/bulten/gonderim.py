"""Bülten gönderimi: her aboneye, tercihlerine uyan ve ona daha önce gönderilmemiş ilanlar.
Ayrıca hoş geldin e-postası: abonelik onaylanınca hazır veriden (yapay zekâ yok) anında giden ilk e-posta.

Kurallar:
- Yeni ilan yoksa e-posta gitmez.
- Aynı ilan bir aboneye iki kez gitmez (gonderimler tablosu).
- Her abone ayrı bir veritabanı işlemiyle kaydedilir: gönderim yarıda kesilse (sunucu çökse) bile, e-postası
  gitmiş aboneye ertesi çalıştırmada aynı ilanlar tekrar gitmez.
- Bir e-postada en fazla AZAMI_ILAN ilan ve firma başına en fazla 2 ilan; fazlası bir sonraki bültene kalır.
- Bir abone aynı Türkiye gününde tek bülten alır: sabah işi iki kez çalışsa da (bkz. depo/bulten.py).
- Bir abonenin e-postası gönderilemezse (adres reddi vb.) diğerleri etkilenmez; hata kaydedilir.
"""

import logging
from contextlib import nullcontext
from datetime import datetime

from sqlalchemy.orm import sessionmaker

from internreader import depo
from internreader.abonelik import iptal_jetonu
from internreader.ayar import GELISTIRME_ANAHTARI, Ayarlar
from internreader.bulten.sablon import AZAMI_ILAN, bulten_epostasi, hos_geldin_epostasi
from internreader.bulten.secim import bulten_sec, yakin_ilanlar
from internreader.db import simdi
from internreader.eposta import EpostaGonderici
from internreader.yayin import zenginlestir
from internreader.yayin.whatsapp import taze_mi

kayit = logging.getLogger(__name__)


ARDISIK_HATA_SINIRI = 5  # art arda bu kadar hata: sorun tek abonede değil, gönderimin kendisinde


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

    rapor = {"hazir_abone": len(aboneler), "gonderilen": 0, "bos": 0, "hata": 0, "ilan": 0, "ertelendi": 0}
    ardisik_hata = 0
    # SMTP göndericisi bağlam yöneticisiyse bütün e-postalar tek bağlantıdan gider
    baglam = gonderici if hasattr(gonderici, "__enter__") else nullcontext(gonderici)
    with baglam as g:
        for sira, (abone_id, eposta, tercihler, siklik) in enumerate(aboneler):
            if ayar.gunluk_bulten_siniri and rapor["gonderilen"] >= ayar.gunluk_bulten_siniri:
                # Günlük e-posta bütçesi doldu: kalanlar ertesi gün listenin başında (adil sıra, depo/bulten.py)
                rapor["ertelendi"] = len(aboneler) - sira
                kayit.warning(
                    "Günlük bülten sınırı (%d) doldu; %d abone yarına kaldı",
                    ayar.gunluk_bulten_siniri,
                    rapor["ertelendi"],
                )
                break
            if ardisik_hata >= ARDISIK_HATA_SINIRI:
                rapor["ertelendi"] = len(aboneler) - sira
                kayit.error(
                    "Art arda %d gönderim hatası: e-posta kotası ya da SMTP ayarı; gönderim durduruldu", ardisik_hata
                )
                break
            with oturum() as o:
                gonderilmis = depo.gonderilen_kimlikler(o, abone_id)
            secilen = bulten_sec(ilanlar, tercihler, gonderilmis, AZAMI_ILAN)
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
                ardisik_hata = 0
            except Exception:  # tek abonenin hatası diğerlerini durdurmaz
                kayit.exception("Bülten gönderilemedi (abone %d)", abone_id)
                durum = "hata"
                ardisik_hata += 1
            with oturum.begin() as o:
                if durum == "gonderildi":
                    depo.gonderim_kaydet(o, depo.abone_id_ile(o, abone_id), [i["kimlik"] for i in secilen], an)
                depo.bulten_kaydet(o, abone_id, len(secilen), durum, an)
            rapor["gonderilen" if durum == "gonderildi" else "hata"] += 1
            rapor["ilan"] += len(secilen) if durum == "gonderildi" else 0
    kayit.info("Bülten: %s", rapor)
    return rapor


def hos_geldin_secimi(ilanlar: list[dict], tercihler: dict) -> tuple[list[dict], str]:
    """(ilanlar, sonuç). Sıralama ve sınırlar bültenle aynı; yeni olmayan ama güncel ilanlar da girer (taze_mi yok),
    bayatlar zaten listede yoktur. Sonuç: "gonderildi" (tam uyan), "yakin" (yakın ilanlar), "bos" (hiç ilan yok)."""
    if secilen := bulten_sec(ilanlar, tercihler, set(), AZAMI_ILAN):
        return secilen, "gonderildi"
    yakin = yakin_ilanlar(ilanlar, tercihler)
    return yakin, "yakin" if yakin else "bos"


def hos_geldin_gonder(
    oturum: sessionmaker, gonderici: EpostaGonderici, ayar: Ayarlar, abone_id: int, an: datetime | None = None
) -> str:
    """Abonelik onaylanınca giden ilk e-posta. Yapay zekâ çağrısı yok, hazır veriden.
    Sonuç: "gonderildi", "yakin", "bos" ya da "atlandi" (bütçe doldu) / "hata" (gönderilemedi). Son ikisinde ilanlar
    "gönderildi" sayılmaz: ertesi sabahki bülten kapatır. Tam uyan ilan gittiyse aynı gün sabah bülteni ikinci kez
    gitmez (son_bulten); yakın ilanlar bülten sayılmaz, tam uyan ilan çıkarsa ilk sabah gelir."""
    an = an or simdi()
    if ayar.smtp_sunucu and ayar.gizli_anahtar == GELISTIRME_ANAHTARI:
        kayit.warning("INTERNREADER_GIZLI_ANAHTAR tanımlı değil: hoş geldin e-postası gönderilmedi")
        return "atlandi"
    with oturum() as o:
        abone = depo.abone_id_ile(o, abone_id)
        if abone is None:
            return "atlandi"
        if ayar.gunluk_hos_geldin_siniri and depo.son_gun_hos_geldin_sayisi(o, an) >= ayar.gunluk_hos_geldin_siniri:
            kayit.warning(
                "Günlük hoş geldin sınırı (%d) doldu; ertesi sabahki bülten kapatacak", ayar.gunluk_hos_geldin_siniri
            )
            return "atlandi"
        eposta, tercihler, siklik = abone.eposta, dict(abone.tercihler or {}), abone.siklik
        ilanlar = [zenginlestir(x) for x in depo.yayinlanacak_ilanlar(o, an=an)]
    secilen, sonuc = hos_geldin_secimi(ilanlar, tercihler)
    jeton = iptal_jetonu(abone_id, ayar.gizli_anahtar)
    ileti = hos_geldin_epostasi(
        alici=eposta,
        ilanlar=secilen,
        tam_uyan=sonuc == "gonderildi",
        an=an,
        site_adresi=ayar.site_adresi,
        iptal_adresi=f"{ayar.site_adresi}/iptal?jeton={jeton}",
        tek_tik_adresi=f"{ayar.site_adresi}/api/abone/iptal-tek?jeton={jeton}",
        siklik=siklik,
    )
    try:
        gonderici.gonder(ileti)
    except Exception:  # onay yine başarılı: abonelik başladı, ertesi sabah normal bülten gider
        kayit.exception("Hoş geldin e-postası gönderilemedi (abone %d)", abone_id)
        with oturum.begin() as o:
            depo.bulten_kaydet(o, abone_id, len(secilen), "hata", an)
        return "hata"
    with oturum.begin() as o:
        abone = depo.abone_id_ile(o, abone_id)
        if abone is not None:  # gönderim sırasında çıkmış olabilir
            depo.gonderim_kaydet(o, abone, [i["kimlik"] for i in secilen], an, son_bulten_yaz=sonuc == "gonderildi")
        depo.bulten_kaydet(o, abone_id if abone is not None else None, len(secilen), depo.HOS_GELDIN_DURUMU, an)
    kayit.info("Hoş geldin e-postası: %s, %d ilan", sonuc, len(secilen))
    return sonuc
