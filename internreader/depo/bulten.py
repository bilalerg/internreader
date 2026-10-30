"""Bülten gönderimi: kime ne zaman gönderilecek, kime hangi ilan gitti, gönderim kayıtları."""

from collections.abc import Iterable
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from internreader.db import Abone, Bulten, EpostaSayaci, Gonderim
from internreader.depo._ortak import utc
from internreader.yayin import TURKIYE_SAATI

HAFTALIK_GUN = 0  # pazartesi (datetime.weekday); haftalık bülten o sabahki çalışmada gider
HOS_GELDIN_DURUMU = "hos_geldin"  # bultenler.durum: abonelik onaylanınca giden e-posta (e-posta bütçesi için sayılır)


def gonderime_hazir_aboneler(oturum: Session, an: datetime) -> list[Abone]:
    """Onaylı aboneler: günlükler her gün, haftalıklar pazartesi (Türkiye saatiyle).

    Haftalık bülten "son bültenden 7 gün sonra" değil, takvime bağlı: herkes aynı gün alır, gün kaymaz. Sabah işi aynı
    gün iki kez çalışsa (Vercel tetiklemesi + GitHub yedek zamanlaması, elle tetikleme) kimse ikinci e-posta almaz;
    günlük sınır yüzünden alamayan abone ertesi gün listenin başındadır."""
    yerel = an.astimezone(TURKIYE_SAATI)
    haftalik_gunu = yerel.weekday() == HAFTALIK_GUN
    gun_basi = yerel.replace(hour=0, minute=0, second=0, microsecond=0)
    hazir = []
    for abone in oturum.scalars(select(Abone).where(Abone.durum == "onayli").order_by(Abone.id)):
        son = utc(abone.son_bulten)
        if (abone.siklik == "gunluk" or haftalik_gunu) and (son is None or son < gun_basi):
            hazir.append(abone)
    # Adil sıra: hiç bülten almamış ya da en uzun süredir bekleyen önce. Günlük e-posta sınırı dolarsa kalanlar
    # ertesi gün listenin başına geçer; aynı kişiler her gün dışarıda kalmaz.
    hazir.sort(key=lambda a: (a.son_bulten is not None, utc(a.son_bulten) or an))
    return hazir


def gonderilen_kimlikler(oturum: Session, abone_id: int) -> set[str]:
    return set(oturum.scalars(select(Gonderim.ilan_kimlik).where(Gonderim.abone_id == abone_id)))


def gonderim_kaydet(
    oturum: Session, abone: Abone, kimlikler: Iterable[str], an: datetime, son_bulten_yaz: bool = True
) -> None:
    for kimlik in kimlikler:
        oturum.add(Gonderim(abone_id=abone.id, ilan_kimlik=kimlik, tarih=an))
    if son_bulten_yaz:
        abone.son_bulten = an


def bulten_kaydet(oturum: Session, abone_id: int | None, ilan_sayisi: int, durum: str, an: datetime) -> None:
    oturum.add(Bulten(abone_id=abone_id, ilan_sayisi=ilan_sayisi, durum=durum, tarih=an))


def bulten_istatistigi(oturum: Session, an: datetime, gun: int = 7) -> dict:
    """Son `gun` günde gönderilen bülten ve bülten alan farklı abone sayısı (aktif kullanıcı ölçümünün bir parçası)."""
    esik = an - timedelta(days=gun)
    kosul = (Bulten.tarih >= esik, Bulten.durum == "gonderildi")
    return {
        "gun": gun,
        "bulten": oturum.scalar(select(func.count()).select_from(Bulten).where(*kosul)) or 0,
        "abone": oturum.scalar(select(func.count(func.distinct(Bulten.abone_id))).where(*kosul)) or 0,
    }


def eski_gonderimleri_sil(oturum: Session, once: datetime) -> int:
    """Kapanmış ilanlar tekrar gönderilmeyeceği için eski gönderim kayıtları tutulmaz."""
    return oturum.execute(delete(Gonderim).where(Gonderim.tarih < once)).rowcount or 0


def _turkiye_gunu(an: datetime) -> str:
    return an.astimezone(TURKIYE_SAATI).date().isoformat()


def eposta_kotasi_ayir(oturum: Session, an: datetime, azami: int) -> bool:
    """Bugünün sayacından bir e-postalık yer ayırır; `azami` doluysa False. 0 = sınırsız, yine de sayılır.
    Atomik: `UPDATE ... WHERE adet < azami`. Sabah işi ve API aynı anda çalışsa da kota aşılmaz. Sayaç ayrı olduğu için
    aynı gün iki çalışma, onay ve hoş geldin e-postaları birlikte sayılır."""
    gun = _turkiye_gunu(an)
    kosul = [EpostaSayaci.gun == gun]
    if azami:
        kosul.append(EpostaSayaci.adet < azami)
    artir = update(EpostaSayaci).where(*kosul).values(adet=EpostaSayaci.adet + 1)
    if oturum.execute(artir).rowcount:
        return True
    if oturum.get(EpostaSayaci, gun) is not None:
        return False
    try:
        with oturum.begin_nested():  # iki istek aynı anda günün ilk e-postasını ayırabilir
            oturum.add(EpostaSayaci(gun=gun, adet=0))
    except IntegrityError:
        pass
    return bool(oturum.execute(artir).rowcount)


def eposta_kotasi_iade(oturum: Session, an: datetime) -> None:
    """Gönderilemeyen ya da gerekmeyen e-postanın yeri geri verilir."""
    oturum.execute(
        update(EpostaSayaci)
        .where(EpostaSayaci.gun == _turkiye_gunu(an), EpostaSayaci.adet > 0)
        .values(adet=EpostaSayaci.adet - 1)
    )


def eposta_sayisi(oturum: Session, an: datetime) -> int:
    sayac = oturum.get(EpostaSayaci, _turkiye_gunu(an))
    return sayac.adet if sayac else 0
