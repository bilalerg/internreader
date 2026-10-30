"""HTTP API: sitenin abonelik formu buraya istek atar.

Uç noktalar (site ile aynı alan adında, /api altında; ters vekil (Caddy) yönlendirir, bu yüzden CORS gerekmez):
  GET  /api/saglik        izleme için {"durum": "ok"}; veritabanı yoksa 503
  POST /api/abone         kayıt isteği → onay e-postası (202)
  POST /api/abone/onay    {"jeton": ...} e-postadaki bağlantının açtığı sayfa çağırır; ilk onayda hoş geldin e-postası
  POST /api/abone/iptal   {"jeton": ...} tek tıkla çıkış; kayıt silinir
  GET  /api/t/{jeton}     e-postadaki "Başvur" bağlantısı: tıklamayı kaydeder, ilana yönlendirir (bkz. bulten/tiklama.py)
  GET  /api/cron/gunluk   Vercel Cron çağırır (Authorization: Bearer CRON_SECRET): GitHub'da sabah işini başlatır

Güvenlik:
- IP başına hız sınırı (bellekte; tek sunucu için yeterli).
- Bal küpü (honeypot): insanların görmediği "web_sitesi" alanını dolduran istek sessizce yok sayılır.
- Adres sızdırmama: adres kayıtlı olsa da olmasa da aynı cevap döner.
- Onay ve çıkış GET değil POST: e-posta güvenlik tarayıcıları bağlantıları önceden açınca kendiliğinden onay olmaz.
Çalıştırma: python -m internreader api   (sunucuda: uvicorn internreader.api:uygulama --factory)
"""

import hmac
import logging
import os
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from typing import Literal

import requests
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from internreader import abonelik, depo
from internreader.ayar import GELISTIRME_ANAHTARI, Ayarlar, ayarlari_oku
from internreader.bulten import hos_geldin_gonder
from internreader.bulten.tiklama import jeton_coz, supheli_mi
from internreader.db import oturum_fabrikasi, simdi
from internreader.eposta import EpostaGonderici, dogrulama_epostasi, gonderici_olustur
from internreader.isleme.kategori import ALANLAR
from internreader.isleme.sehir import SEHIRLER

kayit = logging.getLogger(__name__)

SEHIR_SECENEKLERI = frozenset(SEHIRLER) | {"uzaktan"}  # "uzaktan" eski formdan; artık çalışma modelinde seçiliyor
SEVIYELER = ("staj", "uzun_donem_staj", "yari_zamanli", "junior", "yeni_mezun")
Alan = Literal[
    "yazilim", "yapay_zeka", "veri", "oyun", "savunma"
]  # isleme/kategori.py ALANLAR ile aynı (testte denetlenir)
Seviye = Literal["staj", "uzun_donem_staj", "yari_zamanli", "junior", "yeni_mezun"]
CalismaModeli = Literal["uzaktan", "hibrit", "yerinde"]
KAYIT_CEVABI = {"mesaj": "Onay bağlantısını e-posta adresine gönderdik. Gelen kutunu (ve spam klasörünü) kontrol et."}


class AboneIstegi(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    eposta: EmailStr = Field(max_length=254)
    sehirler: list[str] = Field(default_factory=list, max_length=20)  # boş = şehir fark etmez
    alanlar: list[Alan] = Field(default_factory=lambda: list(ALANLAR), min_length=1, max_length=len(ALANLAR))
    seviyeler: list[Seviye] = Field(default_factory=lambda: list(SEVIYELER), min_length=1, max_length=len(SEVIYELER))
    calisma_modelleri: list[CalismaModeli] = Field(default_factory=list, max_length=3)  # boş = hepsi
    sadece_girisim: bool = False
    siklik: Literal["gunluk", "haftalik"] = "gunluk"
    kvkk_onay: bool
    kaynak: str = Field("site", max_length=40, pattern=r"^[a-z0-9_-]*$")
    web_sitesi: str = Field("", max_length=300)  # bal küpü

    @field_validator("sehirler")
    @classmethod
    def _sehirler_gecerli(cls, deger: list[str]) -> list[str]:
        if bilinmeyen := set(deger) - SEHIR_SECENEKLERI:
            raise ValueError(f"bilinmeyen şehir: {', '.join(sorted(bilinmeyen))}")
        return sorted(set(deger))

    @field_validator("alanlar", "seviyeler", "calisma_modelleri")
    @classmethod
    def _tekrarsiz(cls, deger: list[str]) -> list[str]:
        return sorted(set(deger))

    @field_validator("kvkk_onay")
    @classmethod
    def _kvkk_onayli(cls, deger: bool) -> bool:
        if not deger:
            raise ValueError("aydınlatma metnini onaylaman gerekiyor")
        return deger


class JetonIstegi(BaseModel):
    model_config = ConfigDict(extra="forbid")
    jeton: str = Field(min_length=10, max_length=200)


class HizSiniri:
    """Kayan pencere: bir anahtar (IP) `pencere_sn` saniyede en fazla `azami` istek yapabilir."""

    def __init__(self, azami: int, pencere_sn: float):
        self.azami, self.pencere = azami, pencere_sn
        self._istekler: dict[str, deque] = defaultdict(deque)
        self._kilit = threading.Lock()

    def izin_ver(self, anahtar: str) -> bool:
        an = time.monotonic()
        with self._kilit:
            kuyruk = self._istekler[anahtar]
            while kuyruk and kuyruk[0] <= an - self.pencere:
                kuyruk.popleft()
            if len(kuyruk) >= self.azami:
                return False
            kuyruk.append(an)
            return True


def _hata(kod: int, hata: str, mesaj: str) -> JSONResponse:
    return JSONResponse(status_code=kod, content={"hata": hata, "mesaj": mesaj})


def is_akisini_tetikle(ayar: Ayarlar) -> int:
    """GitHub'da gunluk.yml için workflow_dispatch; GitHub'ın durum kodunu döndürür (başarı: 204). Token yazdırılmaz."""
    cevap = requests.post(
        f"https://api.github.com/repos/{ayar.github_depo}/actions/workflows/gunluk.yml/dispatches",
        headers={
            "Authorization": f"Bearer {ayar.github_tetik_tokeni}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={"ref": "main"},
        timeout=15,
    )
    return cevap.status_code


def uygulama_olustur(
    ayar: Ayarlar,
    oturum: sessionmaker,
    gonderici: EpostaGonderici,
    kayit_siniri: HizSiniri | None = None,
    jeton_siniri: HizSiniri | None = None,
    tetikleyici: Callable[[Ayarlar], int] = is_akisini_tetikle,
    tik_siniri: HizSiniri | None = None,
) -> FastAPI:
    # Herkese açık API belgesi kapalı: yalnızca kendi sitemiz kullanıyor
    app = FastAPI(title="InternReader", docs_url=None, redoc_url=None, openapi_url=None)
    kayit_siniri = kayit_siniri or HizSiniri(azami=5, pencere_sn=600)
    jeton_siniri = jeton_siniri or HizSiniri(azami=30, pencere_sn=600)
    tik_siniri = tik_siniri or HizSiniri(azami=120, pencere_sn=600)

    # Vercel'de istek platformun vekilinden gelir; gerçek IP'yi Vercel "x-real-ip" başlığına kendisi yazar
    # (istemcinin gönderdiği değer ezilir, taklit edilemez). Kendi sunucumuzda uvicorn --proxy-headers kullanılır.
    vercelde = os.getenv("VERCEL") == "1"

    def istemci(istek: Request) -> str:
        if vercelde and istek.headers.get("x-real-ip"):
            return istek.headers["x-real-ip"]
        return istek.client.host if istek.client else "bilinmiyor"

    @app.exception_handler(RequestValidationError)
    def _dogrulama_hatasi(_: Request, hata: RequestValidationError) -> JSONResponse:
        # Hangi alanların hatalı olduğu döner (form o alanları işaretler); iç ayrıntılar dışarı verilmez
        # Liste öğesindeki hatada konumun sonu sıra numarasıdır ("alanlar", 0): alanın adı alınır
        alanlar = sorted(
            {next((p for p in reversed(h["loc"]) if isinstance(p, str)), "") for h in hata.errors()} - {""}
        )
        return JSONResponse(
            status_code=422,
            content={"hata": "gecersiz_istek", "mesaj": "Formdaki bilgileri kontrol et.", "alanlar": alanlar},
        )

    @app.get("/api/saglik")
    def saglik():
        # İzleme ve Docker sağlık kontrolü: veritabanına ulaşılamıyorsa 503 (kayıt formu da çalışmaz)
        try:
            with oturum() as o:
                o.execute(text("SELECT 1"))
        except SQLAlchemyError:
            kayit.exception("Sağlık kontrolü: veritabanına ulaşılamadı")
            return _hata(503, "veritabani", "Veritabanına ulaşılamıyor.")
        return {"durum": "ok"}

    @app.get("/api/cron/gunluk")
    def cron_gunluk(istek: Request):
        """GitHub'ın zamanlaması saatlerce gecikebiliyor (30.10: 07:00 yerine 13:35). Vercel Cron bu ucu her sabah çağırır,
        uç da sabah işini GitHub'da başlatır. Bir sorun olursa GitHub'daki yedek zamanlama işi yine çalıştırır."""
        beklenen = f"Bearer {ayar.cron_gizli}".encode()
        if not ayar.cron_gizli or not hmac.compare_digest(istek.headers.get("authorization", "").encode(), beklenen):
            return _hata(401, "yetkisiz", "Yetkisiz istek.")
        if not ayar.github_tetik_tokeni:
            kayit.warning("GITHUB_TETIK_TOKENI tanımlı değil: sabah işi yedek zamanlamayla çalışacak")
            return _hata(
                503,
                "tetik_tokeni_yok",
                "GITHUB_TETIK_TOKENI tanımlı değil; sabah işi GitHub yedek zamanlamasıyla çalışacak.",
            )
        try:
            durum_kodu = tetikleyici(ayar)
        except requests.RequestException as hata:
            kayit.warning("GitHub'a ulaşılamadı: %s", type(hata).__name__)
            return _hata(502, "github_ulasilamadi", "GitHub'a ulaşılamadı; sabah işi yedek zamanlamayla çalışacak.")
        if durum_kodu != 204:
            kayit.warning("GitHub iş akışını başlatmadı: %d", durum_kodu)
            return _hata(
                502, "github_reddetti", f"GitHub {durum_kodu} döndü; token yetkisini ve depo adını kontrol et."
            )
        return {"durum": "tetiklendi"}

    @app.api_route("/api/t/{jeton}", methods=["GET", "HEAD"])
    def tikla(jeton: str, istek: Request):
        """Her durumda yönlendirir: ölçüm kaybolabilir, başvuru kaybolmaz. HEAD (güvenlik tarayıcıları) sayılmaz.
        Geçersiz jeton siteye gider; adres jetonda imzalı olduğu için bu uç başka adreslere yönlendirmek için kullanılamaz."""
        veri = jeton_coz(jeton, ayar.gizli_anahtar)
        if veri is None:
            return RedirectResponse(ayar.site_adresi, status_code=302)
        if istek.method == "GET" and tik_siniri.izin_ver(istemci(istek)):
            an = simdi()
            try:
                with oturum.begin() as o:
                    depo.tiklama_kaydet(
                        o,
                        ilan_kimlik=str(veri["i"]),
                        eposta_no=str(veri["e"]),
                        kisi=str(veri["k"]),
                        hafta=str(veri["h"]),
                        tur=str(veri["t"]),
                        supheli=supheli_mi(istek.headers.get("user-agent", ""), int(veri["z"]), an),
                        an=an,
                    )
            except (SQLAlchemyError, KeyError, ValueError):
                kayit.warning("Tıklama kaydedilemedi", exc_info=True)
        return RedirectResponse(
            veri["u"], status_code=302, headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"}
        )

    @app.post("/api/abone", status_code=202)
    def abone_ol(govde: AboneIstegi, istek: Request):
        if not kayit_siniri.izin_ver(istemci(istek)):
            return _hata(429, "cok_fazla_istek", "Kısa sürede çok fazla deneme oldu. Birkaç dakika sonra tekrar dene.")
        if govde.web_sitesi:  # bal küpü dolu → bot; aynı cevabı ver, hiçbir şey yapma
            kayit.info("Bal küpü dolu bir kayıt isteği yok sayıldı")
            return KAYIT_CEVABI
        eposta = str(govde.eposta).lower()
        if ayar.gunluk_onay_siniri:
            with oturum() as o:
                if depo.son_gun_onay_sayisi(o, simdi()) >= ayar.gunluk_onay_siniri:
                    kayit.warning("Günlük onay e-postası sınırı (%d) doldu", ayar.gunluk_onay_siniri)
                    return _hata(
                        503, "gunluk_sinir", "Bugün çok fazla kayıt geldi. Yarın tekrar dener misin? Kusura bakma."
                    )
        tercihler = {
            "sehirler": govde.sehirler,
            "alanlar": govde.alanlar,
            "seviyeler": govde.seviyeler,
            "calisma_modelleri": govde.calisma_modelleri,
            "sadece_girisim": govde.sadece_girisim,
        }
        with oturum.begin() as o:
            jeton = abonelik.kayit_iste(o, eposta, tercihler, govde.siklik, govde.kaynak or "site")
        if jeton:
            try:
                gonderici.gonder(dogrulama_epostasi(eposta, f"{ayar.site_adresi}/onay?jeton={jeton}"))
            except Exception:
                kayit.exception("Onay e-postası gönderilemedi")
                return _hata(
                    503, "eposta_gonderilemedi", "Onay e-postası şu an gönderilemedi. Biraz sonra tekrar dene."
                )
        return KAYIT_CEVABI

    @app.post("/api/abone/onay")
    def onayla(govde: JetonIstegi, istek: Request):
        if not jeton_siniri.izin_ver(istemci(istek)):
            return _hata(429, "cok_fazla_istek", "Kısa sürede çok fazla deneme oldu.")
        with oturum.begin() as o:
            sonuc = abonelik.onayla(o, govde.jeton)
        if sonuc is None:
            return _hata(
                400, "gecersiz_jeton", "Bağlantı geçersiz ya da süresi dolmuş. Formdan yeniden kaydolabilirsin."
            )
        hos_geldin = "zaten"
        if sonuc.yeni:  # onay kaydedildi; bundan sonra ne olursa olsun abonelik başladı, istek başarısız sayılmaz
            try:
                hos_geldin = hos_geldin_gonder(oturum, gonderici, ayar, sonuc.abone_id)
            except Exception:
                kayit.exception("Hoş geldin e-postası hazırlanamadı (abone %d)", sonuc.abone_id)
                hos_geldin = "hata"
        return {"durum": "onaylandi", "hos_geldin": hos_geldin, "siklik": sonuc.siklik}

    @app.post("/api/abone/iptal")
    def iptal(govde: JetonIstegi, istek: Request):
        if not jeton_siniri.izin_ver(istemci(istek)):
            return _hata(429, "cok_fazla_istek", "Kısa sürede çok fazla deneme oldu.")
        with oturum.begin() as o:
            tamam = abonelik.iptal_et(o, govde.jeton, ayar.gizli_anahtar)
        if not tamam:
            return _hata(400, "gecersiz_jeton", "Bu çıkış bağlantısı geçersiz.")
        return {"durum": "iptal_edildi"}

    @app.post("/api/abone/iptal-tek")
    def tek_tikla_iptal(jeton: str, istek: Request):
        """RFC 8058 tek tıkla çıkış: e-posta istemcisi (Gmail, Yahoo) List-Unsubscribe-Post başlığını görünce bu
        adrese doğrudan POST atar; gövde "List-Unsubscribe=One-Click" olur ve okunmaz. Jeton adreste gelir."""
        if not jeton_siniri.izin_ver(istemci(istek)):
            return _hata(429, "cok_fazla_istek", "Kısa sürede çok fazla deneme oldu.")
        with oturum.begin() as o:
            tamam = abonelik.iptal_et(o, jeton[:200], ayar.gizli_anahtar)
        if not tamam:
            return _hata(400, "gecersiz_jeton", "Bu çıkış bağlantısı geçersiz.")
        return {"durum": "iptal_edildi"}

    return app


def uygulama() -> FastAPI:
    """uvicorn için fabrika: ayarları ortamdan okur."""
    ayar = ayarlari_oku()
    if ayar.gizli_anahtar == GELISTIRME_ANAHTARI:
        kayit.warning("INTERNREADER_GIZLI_ANAHTAR tanımlı değil: geliştirme anahtarı kullanılıyor (sunucuda kullanma!)")
    # Vercel fonksiyonu 30 sn'de kesilir: takılan SMTP bağlantısı isteği öldürmesin
    return uygulama_olustur(ayar, oturum_fabrikasi(ayar.veritabani_url), gonderici_olustur(ayar, zaman_asimi=10))
