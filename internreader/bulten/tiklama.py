"""Tıklama ölçümü: e-postadaki "Başvur" bağlantısı önce /api/t/<jeton> adresine gelir, kaydedilir, ilana yönlenir.

- İlan adresi jetonun içinde ve imzalı. Veritabanı kapalı olsa da öğrenci ilana ulaşır: ölçüm kaybolabilir, başvuru
  kaybolmaz. İmza olmasa bu uç herkesin kullanabileceği bir yönlendirici olurdu (open redirect).
- Aboneyle bağ kurulmaz (KVKK, en az veri): jetonda ve kayıtta e-posta adresi ya da abone no yok. "Kaç kişi tıkladı?"
  sorusu için `kisi` kodu kullanılır: abone no + hafta + gizli anahtardan üretilir, her hafta değişir, haftalar arasında
  aynı kişi izlenemez. Sunucu kayıtlarında görünen adreste de kişisel veri kalmaz.
- E-posta güvenlik tarayıcıları (Outlook SafeLinks vb.) bağlantıları kendiliğinden açar. Bunlar silinmez, "şüpheli" işaretlenir
  ve rapora girmez: tarayıcı adı bot olanlar, e-posta gittikten hemen sonra açılanlar (bkz. depo/tiklamalar.py toplu açılış).
- Düz metin sürümünde bağlantı doğrudan ilana gider: uzun ve anlamsız bir adres okunan metni bozardı.
"""

import base64
import hashlib
import hmac
import json
import re
import secrets
from collections.abc import Callable
from datetime import datetime

from internreader.ayar import Ayarlar
from internreader.yayin import TURKIYE_SAATI

ANI_ACILIS_SN = 30  # e-posta gittikten sonra bu süre içinde açılan bağlantı büyük olasılıkla tarayıcıdır
BOT_TARAYICI = re.compile(
    r"(?i)bot\b|bot/|crawl|spider|scan|preview|proofpoint|barracuda|mimecast|safelink|symantec|fortinet|sophos|cisco|"
    r"trend ?micro|python|curl|wget|go-http|java/|okhttp|libwww|headless|phantom|whatsapp|telegram|facebookexternal"
)


def hafta_etiketi(an: datetime) -> str:
    yil, hafta, _ = an.astimezone(TURKIYE_SAATI).isocalendar()
    return f"{yil}-W{hafta:02d}"


def kisi_kodu(abone_id: int, hafta: str, gizli_anahtar: str) -> str:
    return hmac.new(gizli_anahtar.encode(), f"kisi:{abone_id}:{hafta}".encode(), hashlib.sha256).hexdigest()[:16]


def _imza(govde: str, gizli_anahtar: str) -> str:
    return hmac.new(gizli_anahtar.encode(), f"tik:{govde}".encode(), hashlib.sha256).hexdigest()[:32]


def jeton_olustur(veri: dict, gizli_anahtar: str) -> str:
    govde = base64.urlsafe_b64encode(json.dumps(veri, separators=(",", ":")).encode()).decode().rstrip("=")
    return f"{govde}.{_imza(govde, gizli_anahtar)}"


def jeton_coz(jeton: str, gizli_anahtar: str) -> dict | None:
    """İmza doğru ve adres http(s) ise içeriği döndürür; değilse None (çağıran kullanıcıyı siteye gönderir)."""
    govde, _, imza = jeton.rpartition(".")
    if not govde or not hmac.compare_digest(_imza(govde, gizli_anahtar), imza):
        return None
    try:
        veri = json.loads(base64.urlsafe_b64decode(govde + "=" * (-len(govde) % 4)))
    except ValueError:
        return None
    return veri if str(veri.get("u", "")).startswith(("https://", "http://")) else None


def baglanti_yapici(ayar: Ayarlar, abone_id: int, tur: str, an: datetime) -> Callable[[dict], str]:
    """Bir e-postanın bağlantı üreticisi. `tur`: bulten | hos_geldin | deneme (deneme rapora girmez)."""
    hafta = hafta_etiketi(an)
    ortak = {
        "e": secrets.token_hex(8),  # bu e-postanın rastgele numarası; aboneye geri götürmez
        "k": kisi_kodu(abone_id, hafta, ayar.gizli_anahtar),
        "h": hafta,
        "t": tur,
        "z": int(an.timestamp()),
    }

    def yap(ilan: dict) -> str:
        jeton = jeton_olustur({**ortak, "i": ilan["kimlik"], "u": ilan["url"]}, ayar.gizli_anahtar)
        return f"{ayar.site_adresi}/api/t/{jeton}"

    return yap


def supheli_mi(tarayici: str, gonderim_zamani: int, an: datetime) -> bool:
    return not tarayici or bool(BOT_TARAYICI.search(tarayici)) or an.timestamp() - gonderim_zamani < ANI_ACILIS_SN
