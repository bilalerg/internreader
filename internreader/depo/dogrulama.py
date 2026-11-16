"""Başvuru kanıtını sakla; liste tazeliği ile doğrulama tazeliğini karıştırma."""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from internreader.db import IlanDogrulama, IlanKaydi, Siniflandirma, simdi
from internreader.depo._ortak import utc
from internreader.isleme.basvuru import BasvuruSonucu

BELIRSIZLIK_SINIRI = timedelta(days=3)
KONTROL_ARALIGI = timedelta(hours=24)


def dogrulama_kaydi(oturum: Session, kimlik: str, an: datetime) -> IlanDogrulama:
    kayit = oturum.get(IlanDogrulama, kimlik)
    if kayit is None:
        kayit = IlanDogrulama(
            kimlik=kimlik,
            durum="belirsiz",
            neden="henuz_kontrol_edilmedi",
            ilk_kontrol=an,
            gorulmeme_sayisi=0,
        )
        oturum.add(kayit)
    return kayit


def dogrulama_yaz(oturum: Session, kimlik: str, sonuc: BasvuruSonucu, an: datetime | None = None) -> None:
    an = an or simdi()
    kayit = dogrulama_kaydi(oturum, kimlik, an)
    kayit.kontrol_zamani = an
    # Kesin kapanış, sonraki bağlantı hatasıyla unutulmaz; ancak olumlu kanıtla tekrar açılabilir.
    if sonuc.durum == "belirsiz" and (
        kayit.durum == "kapali" or (kayit.durum == "acik" and kayit.neden == "ats_acik_ilan_listesinde")
    ):
        return
    kayit.durum, kayit.neden = sonuc.durum, sonuc.neden
    if sonuc.durum == "acik":
        kayit.acik_dogrulama_zamani = an


def dogrulama_yayin_bilgisi(kayit: IlanDogrulama | None, an: datetime) -> dict:
    if kayit is None:
        return {"durum": "belirsiz", "neden": "henuz_kontrol_edilmedi", "kontrol_zamani": None, "bayat": False}
    dayanak = kayit.acik_dogrulama_zamani or kayit.ilk_kontrol
    bayat = an - utc(dayanak) >= BELIRSIZLIK_SINIRI
    return {
        "durum": "belirsiz" if bayat and kayit.durum != "kapali" else kayit.durum,
        "neden": "dogrulama_suresi_doldu" if bayat and kayit.durum != "kapali" else kayit.neden,
        "kontrol_zamani": utc(kayit.kontrol_zamani).isoformat() if kayit.kontrol_zamani else None,
        "acik_dogrulama_zamani": utc(kayit.acik_dogrulama_zamani).isoformat() if kayit.acik_dogrulama_zamani else None,
        "bayat": bayat,
    }


def dogrulama_bekleyenler(oturum: Session, sinir: int, an: datetime) -> list[dict]:
    # Yeni ilanlar ve en uzun süredir kontrol edilmeyenler önce. Kapalı olup listede hâlâ duranlar da
    # tekrar açılmış olabilir; kontrol edilir. Jooble'ın robots ile yasakladığı detay sayfası okunmaz.
    sorgu = (
        select(IlanKaydi, IlanDogrulama)
        .join(Siniflandirma, Siniflandirma.kimlik == IlanKaydi.kimlik)
        .outerjoin(IlanDogrulama, IlanDogrulama.kimlik == IlanKaydi.kimlik)
        .where(
            IlanKaydi.aktif.is_(True),
            IlanKaydi.gizli.is_(False),
            Siniflandirma.ogrenciye_uygun.is_(True),
            IlanKaydi.kaynak != "jooble",
        )
        .order_by(
            IlanDogrulama.kontrol_zamani.asc().nulls_first(),
            IlanKaydi.ilk_gorulme.desc(),
            IlanKaydi.kimlik,
        )
    )
    adaylar = []
    for ilan, kontrol in oturum.execute(sorgu):
        if kontrol is None or kontrol.kontrol_zamani is None or utc(kontrol.kontrol_zamani) <= an - KONTROL_ARALIGI:
            adaylar.append({"kimlik": ilan.kimlik, "baslik": ilan.baslik, "url": ilan.url})
        if len(adaylar) >= sinir:
            break
    return adaylar if sinir > 0 else []
