"""Bülten gönderimi: kime ne zaman gönderilecek, kime hangi ilan gitti, gönderim kayıtları."""

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from internreader.db import Abone, Bulten, EpostaSayaci, Gonderim, IlanKaydi
from internreader.depo._ortak import _parcalar, utc
from internreader.isleme.tekillestirme import ilan_anahtari
from internreader.yayin import TURKIYE_SAATI

HAFTALIK_GUN = 0  # pazartesi (datetime.weekday); haftalık bülten o sabahki çalışmada gider
HOS_GELDIN_DURUMU = "hos_geldin"  # bultenler.durum: abonelik onaylanınca giden e-posta (e-posta bütçesi için sayılır)
SESSIZLIK_DURUMU = "sessizlik"  # bultenler.durum: pazartesi "bu hafta sana uyan yeni ilan çıkmadı" e-postası
ALINAN_DURUMLAR = ("gonderildi", HOS_GELDIN_DURUMU, SESSIZLIK_DURUMU)  # aboneye gerçekten giden e-postalar
SESSIZLIK_GUNU = 7  # bu kadar gündür abone olup bu kadar gündür e-posta almayana pazartesi sessizlik e-postası


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


def sessiz_aboneler(oturum: Session, an: datetime) -> list[Abone]:
    """Sessizlik e-postasının adayları: onaylı, en az 7 gündür abone ve son 7 günde hiç e-posta almamış.
    Günler Türkiye takvimiyle sayılır (bugün + önceki 6 gün): iş bir pazartesi 09:37'de, ertesi pazartesi 07:05'te
    çalışsa da geçen haftanın e-postası bu haftayı engellemez. Sessizlik e-postası da "alınan e-posta" sayılır: iş aynı
    gün iki kez çalışsa da kimse ikincisini almaz, haftada en fazla bir tane gider."""
    gun_basi = an.astimezone(TURKIYE_SAATI).replace(hour=0, minute=0, second=0, microsecond=0)
    esik = (gun_basi - timedelta(days=SESSIZLIK_GUNU - 1)).astimezone(UTC)  # SQLite saat dilimi saklamaz: UTC
    alanlar = select(Bulten.abone_id).where(
        Bulten.tarih >= esik, Bulten.durum.in_(ALINAN_DURUMLAR), Bulten.abone_id.is_not(None)
    )
    sorgu = (
        select(Abone)
        .where(
            Abone.durum == "onayli",
            func.coalesce(Abone.onay_tarihi, Abone.olusturma) < esik,
            Abone.id.not_in(alanlar),
        )
        .order_by(Abone.id)
    )
    return list(oturum.scalars(sorgu))


def gonderilen_kimlikler(oturum: Session, abone_id: int) -> set[str]:
    """Aboneye giden ilanların kimlikleri ve firma + başlık anahtarları (isleme/tekillestirme.py → ilan_anahtari): aynı
    ilan başka bir adresle yeniden yayınlansa da tekrar gitmez. Firma ve başlık `ilanlar` tablosundan okunur. Gönderim
    kaydı ilana CASCADE ile bağlı: ilan silinirse kayıt da anahtar da kaybolur. Bugün ilan silinmiyor (kapanınca
    aktif=False olur); silen bir bakım eklenirse anahtar gönderim kaydına taşınmalı."""
    sorgu = (
        select(Gonderim.ilan_kimlik, IlanKaydi.firma, IlanKaydi.baslik)
        .join(IlanKaydi, IlanKaydi.kimlik == Gonderim.ilan_kimlik)
        .where(Gonderim.abone_id == abone_id)
    )
    gonderilmis: set[str] = set()
    for kimlik, firma, baslik in oturum.execute(sorgu):
        gonderilmis |= {kimlik, ilan_anahtari(firma, baslik)}
    return gonderilmis


def gonderim_kaydet(
    oturum: Session, abone: Abone, kimlikler: Iterable[str], an: datetime, son_bulten_yaz: bool = True
) -> None:
    for kimlik in kimlikler:
        oturum.add(Gonderim(abone_id=abone.id, ilan_kimlik=kimlik, tarih=an))
    if son_bulten_yaz:
        abone.son_bulten = an


def bulten_kaydet(oturum: Session, abone_id: int | None, ilan_sayisi: int, durum: str, an: datetime) -> None:
    oturum.add(Bulten(abone_id=abone_id, ilan_sayisi=ilan_sayisi, durum=durum, tarih=an))


def son_bulten_tarihi(oturum: Session) -> datetime | None:
    """En son giden bültenin zamanı (elle onay önizlemesinin başlangıcı için yedek)."""
    return utc(oturum.scalar(select(func.max(Bulten.tarih)).where(Bulten.durum == "gonderildi")))


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
    """`once`'den eski gönderim kayıtlarından yalnızca kapanmış ilanlarınkiler silinir. Açık ilanın kaydı ne kadar eski
    olursa olsun kalır: silinseydi aylardır açık duran ilan aynı aboneye yeniden giderdi. Aynı firma + başlıkla hâlâ
    açık bir kopyası olan kapalı ilanın kaydı da kalır; kopyayı o kayıt durduruyor (bkz. gonderilen_kimlikler)."""
    acik = {
        ilan_anahtari(firma, baslik)
        for firma, baslik in oturum.execute(select(IlanKaydi.firma, IlanKaydi.baslik).where(IlanKaydi.aktif.is_(True)))
    }
    eskiler = oturum.execute(
        select(IlanKaydi.kimlik, IlanKaydi.firma, IlanKaydi.baslik)
        .join(Gonderim, Gonderim.ilan_kimlik == IlanKaydi.kimlik)
        .where(Gonderim.tarih < once, IlanKaydi.aktif.is_(False))
        .distinct()
    )
    kapali = [kimlik for kimlik, firma, baslik in eskiler if ilan_anahtari(firma, baslik) not in acik]
    silinen = 0
    for parca in _parcalar(kapali):
        silinen += (
            oturum.execute(delete(Gonderim).where(Gonderim.tarih < once, Gonderim.ilan_kimlik.in_(parca))).rowcount or 0
        )
    return silinen


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
