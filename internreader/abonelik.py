"""Abonelik: çift onaylı (double opt-in) kayıt, onay ve tek tıkla çıkış.

Neden çift onay? Biri formda başkasının adresini yazabilir. Bülten ancak adresin sahibi e-postadaki bağlantıya
tıkladıktan sonra başlar. Bu hem KVKK açısından (açık rıza kanıtı) hem de e-postaların spam'e düşmemesi için gerekli.

Jetonlar:
- Onay jetonu rastgeledir; veritabanında yalnızca özeti (SHA-256) tutulur, 72 saat geçerlidir.
- Çıkış jetonu gizli anahtarla imzalanır (HMAC): her e-postaya eklenebilir, tahmin edilemez, veritabanı gerektirmez.
"""

import hashlib
import hmac
import secrets
from datetime import timedelta

from sqlalchemy.orm import Session

from internreader import depo
from internreader.db import simdi

KVKK_SURUMU = "2026-10-29"  # aydınlatma metni değişirse artırılır; hangi metne onay verildiği kayıtlı kalır
ONAY_GECERLILIK = timedelta(hours=72)


def _ozet(jeton: str) -> str:
    return hashlib.sha256(jeton.encode()).hexdigest()


def kayit_iste(oturum: Session, eposta: str, tercihler: dict, siklik: str, kaynak: str) -> str | None:
    """Onay e-postası gönderilmesi gerekiyorsa ham onay jetonunu döndürür; adres zaten onaylıysa None.
    Çağıran taraf iki durumda da kullanıcıya AYNI cevabı verir (adresin kayıtlı olup olmadığı dışarı sızmaz)."""
    abone = depo.abone_eposta_ile(oturum, eposta)
    if abone is not None and abone.durum == "onayli":
        return None
    if abone is None:
        abone = depo.abone_ekle(oturum, eposta)
    jeton = secrets.token_urlsafe(32)
    an = simdi()
    abone.tercihler, abone.siklik, abone.kaynak = tercihler, siklik, kaynak
    abone.durum, abone.onay_jetonu_ozeti, abone.onay_jetonu_tarihi = "bekliyor", _ozet(jeton), an
    abone.kvkk_surumu, abone.kvkk_onay_tarihi = KVKK_SURUMU, an
    return jeton


def onayla(oturum: Session, jeton: str) -> bool:
    """Jeton geçerliyse aboneliği başlatır. Aynı bağlantıya ikinci kez tıklamak da başarılı sayılır."""
    abone = depo.abone_onay_ozeti_ile(oturum, _ozet(jeton))
    if abone is None:
        return False
    if abone.durum == "onayli":
        return True
    if depo.utc(abone.onay_jetonu_tarihi) < simdi() - ONAY_GECERLILIK:
        return False
    abone.durum, abone.onay_tarihi = "onayli", simdi()
    return True


def iptal_jetonu(abone_id: int, gizli_anahtar: str) -> str:
    imza = hmac.new(gizli_anahtar.encode(), f"iptal:{abone_id}".encode(), hashlib.sha256).hexdigest()[:32]
    return f"{abone_id}.{imza}"


def iptal_et(oturum: Session, jeton: str, gizli_anahtar: str) -> bool:
    """İmza doğruysa abone kaydı (e-posta dahil) tamamen silinir. Zaten silinmişse de başarılı sayılır."""
    try:
        abone_id = int(jeton.split(".", 1)[0])
    except ValueError:
        return False
    if not hmac.compare_digest(iptal_jetonu(abone_id, gizli_anahtar), jeton):
        return False
    abone = depo.abone_id_ile(oturum, abone_id)
    if abone is not None:
        depo.abone_sil(oturum, abone)
    return True


def suresi_dolanlari_temizle(oturum: Session) -> int:
    """72 saat içinde onaylanmayan kayıtları siler (her gün çalıştırma sonunda çağrılır)."""
    return depo.onaylanmamislari_sil(oturum, simdi() - ONAY_GECERLILIK)
