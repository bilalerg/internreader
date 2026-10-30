"""Tıklama kayıtları ve raporu: "bülteni kaç kişi gerçekten kullanıyor?" (bkz. bulten/tiklama.py)."""

from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from internreader.db import Bulten, IlanKaydi, Tiklama
from internreader.depo.bulten import HOS_GELDIN_DURUMU

TOPLU_ACILIS_ILAN = 3  # aynı e-postada bu kadar farklı ilan...
TOPLU_ACILIS_SN = 10  # ...bu süre içinde açıldıysa insan değil, güvenlik tarayıcısıdır


def tiklama_kaydet(
    oturum: Session, ilan_kimlik: str, eposta_no: str, kisi: str, hafta: str, tur: str, supheli: bool, an: datetime
) -> bool:
    """Aynı e-postadaki aynı ilan bir kez sayılır. Tarayıcının açtığı bağlantıya sonra insan da tıklayabilir: `supheli`
    ayrı sayıldığı için insanın tıklaması kaybolmaz."""
    var = oturum.scalar(
        select(Tiklama.id).where(
            Tiklama.eposta_no == eposta_no, Tiklama.ilan_kimlik == ilan_kimlik, Tiklama.supheli.is_(supheli)
        )
    )
    if var is not None:
        return False
    oturum.add(
        Tiklama(
            tarih=an, ilan_kimlik=ilan_kimlik, eposta_no=eposta_no, kisi=kisi, hafta=hafta, tur=tur, supheli=supheli
        )
    )
    return True


def _toplu_acilanlar(satirlar: list) -> set[int]:
    """Bir e-postada kısa sürede art arda açılan bağlantılar: tarayıcı adını gizleyen güvenlik tarayıcıları."""
    epostalar: dict[str, list] = {}
    for s in satirlar:
        epostalar.setdefault(s.eposta_no, []).append(s)
    toplu = set()
    for liste in epostalar.values():
        liste.sort(key=lambda s: s.tarih)
        for bas in range(len(liste) - TOPLU_ACILIS_ILAN + 1):
            pencere = liste[bas : bas + TOPLU_ACILIS_ILAN]
            if (pencere[-1].tarih - pencere[0].tarih).total_seconds() <= TOPLU_ACILIS_SN:
                toplu |= {s.id for s in pencere}
    return toplu


def tiklama_raporu(oturum: Session, an: datetime, gun: int = 7) -> dict:
    """Son `gun` günün sayıları. `tiklama_orani`: gönderilen e-postaların yüzde kaçında en az bir ilana tıklandı.
    `haftalik_tekil_kisi`: e-postanın gittiği haftaya göre farklı kişi sayısı (kod her hafta değiştiği için haftalıktır)."""
    esik = an - timedelta(days=gun)
    satirlar = list(oturum.execute(select(Tiklama).where(Tiklama.tarih >= esik)).scalars())
    deneme = [s for s in satirlar if s.tur == "deneme"]
    gercek = [s for s in satirlar if s.tur != "deneme"]
    toplu = _toplu_acilanlar(gercek)
    insan = [s for s in gercek if not s.supheli and s.id not in toplu]
    gonderilen = (
        oturum.scalar(
            select(func.count())
            .select_from(Bulten)
            .where(Bulten.tarih >= esik, Bulten.durum.in_(("gonderildi", HOS_GELDIN_DURUMU)), Bulten.ilan_sayisi > 0)
        )
        or 0
    )
    tiklanan = len({s.eposta_no for s in insan})
    haftalik: dict[str, set] = {}
    for s in insan:
        haftalik.setdefault(s.hafta, set()).add(s.kisi)
    enler = Counter(s.ilan_kimlik for s in insan).most_common(5)
    ilanlar = {
        i.kimlik: i for i in oturum.scalars(select(IlanKaydi).where(IlanKaydi.kimlik.in_([k for k, _ in enler])))
    }
    return {
        "gun": gun,
        "gonderilen_eposta": gonderilen,
        "tiklanan_eposta": tiklanan,
        "tiklama_orani": round(tiklanan / gonderilen, 3) if gonderilen else None,
        "tiklama": len(insan),
        "haftalik_tekil_kisi": {h: len(k) for h, k in sorted(haftalik.items())},
        "elenen_supheli": len(gercek) - len(insan),
        "deneme": len(deneme),
        "en_cok": [
            {"firma": ilanlar[k].firma, "baslik": ilanlar[k].baslik, "tiklama": n} if k in ilanlar else {"tiklama": n}
            for k, n in enler
        ],
    }


def eski_tiklamalari_sil(oturum: Session, once: datetime) -> int:
    return oturum.execute(delete(Tiklama).where(Tiklama.tarih < once)).rowcount or 0
