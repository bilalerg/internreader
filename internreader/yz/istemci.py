"""Claude istemcisi: bütün yapay zekâ çağrıları buradan geçer.

Neden ayrı bir sarmalayıcı?
- Bütçe: bir çalıştırmadaki toplam harcama tavana ulaşınca yeni çağrı yapılmaz (ButceAsildi).
- Sigorta: servis üst üste hata verirse (kredi bitti, anahtar geçersiz, kesinti) bu çalıştırmada bir daha denenmez.
- Kayıt: her çağrının token sayısı, maliyeti, süresi ve sonucu tutulur; veritabanına yazılır.
- Toplu mod: çok sayıda istek Message Batches API ile YARI FİYATINA gönderilebilir. Sonuçlar genellikle dakikalar
  içinde gelir; belirlenen sürede gelmezse toplu iş iptal edilir ve kalanlar normal yoldan gönderilir.
- Tek yer: model, yeniden deneme ve zaman aşımı ayarları dağılmaz.
"""

import functools
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import anthropic
import pydantic

from internreader.ayar import MODEL_FIYATLARI

kayit = logging.getLogger(__name__)

TOPLU_INDIRIM = 0.5  # Message Batches API fiyatı normalin yarısı


class YzKullanilamaz(Exception):
    """Bu çalıştırmada yapay zekâya artık istek atılmayacak (bütçe doldu ya da servis üst üste hata verdi)."""


class ButceAsildi(YzKullanilamaz):
    """Bu çalıştırma için ayrılan yapay zekâ bütçesi doldu."""


class ServisHatasi(Exception):
    """API isteği, SDK'nın kendi yeniden denemelerinden sonra da başarısız oldu (tek istek kaybedildi)."""


class CiktiBozuk(Exception):
    """Model geçerli bir JSON döndürmedi (çoğunlukla cevap max_tokens sınırında yarıda kesildiği için)."""


Sonuc = pydantic.BaseModel | Exception


class YzIstemci:
    AZAMI_ARDISIK_HATA = 3

    def __init__(
        self,
        model: str,
        tavan_usd: float,
        istemci: anthropic.Anthropic | None = None,
        toplu: bool = False,
        toplu_bekleme_sn: float = 45 * 60,
        toplu_aralik_sn: float = 15,
    ):
        self.model = model
        self.tavan_usd = tavan_usd
        self.toplu = toplu
        self.toplu_bekleme_sn, self.toplu_aralik_sn = toplu_bekleme_sn, toplu_aralik_sn
        self._istemci = istemci
        self._kilit = threading.Lock()
        self.harcanan_usd = 0.0
        self.kullanimlar: list[dict] = []
        self._ardisik_hata = 0

    @property
    def istemci(self) -> anthropic.Anthropic:
        if self._istemci is None:
            # API anahtarını ANTHROPIC_API_KEY ortam değişkeninden okur (ayar.env_yukle ile .env'den gelir)
            self._istemci = anthropic.Anthropic(max_retries=4, timeout=120)
        return self._istemci

    # ------------------------------------------------------------------ bütçe ve sigorta
    def kullanilabilir_mi(self) -> bool:
        with self._kilit:
            return self.harcanan_usd < self.tavan_usd and self._ardisik_hata < self.AZAMI_ARDISIK_HATA

    def _kullanilabilir_olmali(self) -> None:
        if not self.kullanilabilir_mi():
            if self.harcanan_usd >= self.tavan_usd:
                raise ButceAsildi(f"{self.harcanan_usd:.4f} $ ≥ tavan {self.tavan_usd} $")
            raise YzKullanilamaz("servis üst üste hata verdiği için kapatıldı")

    def _istek_sonucu(self, basarili: bool) -> None:
        with self._kilit:
            self._ardisik_hata = 0 if basarili else self._ardisik_hata + 1
            if self._ardisik_hata == self.AZAMI_ARDISIK_HATA:
                kayit.error(
                    "Yapay zekâ servisi üst üste %d kez hata verdi; bu çalıştırmada kapatıldı", self._ardisik_hata
                )

    def _fiyat(self) -> tuple[float, float]:
        return MODEL_FIYATLARI.get(self.model, (4.0, 20.0))  # bilinmeyen modelde temkinli fiyat

    def _kaydet(self, islem: str, kullanim, sure_ms: int | None, durum: str, toplu: bool = False) -> float:
        girdi_fiyat, cikti_fiyat = self._fiyat()
        carpan = TOPLU_INDIRIM if toplu else 1.0
        maliyet = (kullanim.input_tokens * girdi_fiyat + kullanim.output_tokens * cikti_fiyat) / 1e6 * carpan
        with self._kilit:
            self.harcanan_usd += maliyet
            self.kullanimlar.append(
                {
                    "tarih": datetime.now(UTC),
                    "islem": islem,
                    "model": self.model,
                    "girdi_token": kullanim.input_tokens,
                    "cikti_token": kullanim.output_tokens,
                    "maliyet_usd": maliyet,
                    "sure_ms": sure_ms,
                    "durum": durum,
                    "toplu": toplu,
                }
            )
        return maliyet

    # ------------------------------------------------------------------ istek ve cevap
    @staticmethod
    @functools.cache
    def _sema(cikti_turu: type[pydantic.BaseModel]) -> dict:
        """Pydantic modelinden API'nin beklediği JSON şeması (her tür için bir kez hesaplanır)."""
        return {"type": "json_schema", "schema": anthropic.transform_schema(cikti_turu.model_json_schema())}

    def _parametreler(self, sistem: str, mesaj: str, cikti_turu: type[pydantic.BaseModel], max_tokens: int) -> dict:
        return {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": sistem,
            # bilgi çıkarma basit bir iş; düşük efor = daha az token
            "output_config": {"effort": "low", "format": self._sema(cikti_turu)},
            "messages": [{"role": "user", "content": mesaj}],
        }

    def _cevabi_coz(self, islem, yanit, cikti_turu, max_tokens: int, sure_ms: int | None, toplu: bool = False):
        """Kullanımı HER durumda kaydeder (kesilen ya da bozuk cevabın token'ları da ödendi), sonra doğrular."""
        if yanit.stop_reason == "refusal":
            self._kaydet(islem, yanit.usage, sure_ms, "reddedildi", toplu)
            raise CiktiBozuk("model isteği reddetti")
        if yanit.stop_reason == "max_tokens":
            self._kaydet(islem, yanit.usage, sure_ms, "kesildi", toplu)
            raise CiktiBozuk(f"cevap {max_tokens} token sınırında kesildi")
        metin = "".join(b.text for b in yanit.content if getattr(b, "type", "") == "text")
        try:
            sonuc = cikti_turu.model_validate_json(metin)
        except pydantic.ValidationError as hata:
            self._kaydet(islem, yanit.usage, sure_ms, "bozuk", toplu)
            raise CiktiBozuk(str(hata)[:200]) from hata
        self._kaydet(islem, yanit.usage, sure_ms, "tamam", toplu)
        return sonuc

    def yapilandirilmis(
        self, islem: str, sistem: str, mesaj: str, cikti_turu: type[pydantic.BaseModel], max_tokens: int = 16_000
    ):
        """Modelden `cikti_turu` kalıbında (JSON şeması ile zorlanmış) cevap ister ve doğrulanmış nesneyi döndürür.
        (SDK'nın parse() yardımcısı doğrulama hatasında kullanımı kaybettirdiği için create() + kendi doğrulamamız.)"""
        self._kullanilabilir_olmali()
        bas = time.monotonic()
        try:
            yanit = self.istemci.messages.create(**self._parametreler(sistem, mesaj, cikti_turu, max_tokens))
        except anthropic.APIError as hata:
            self._istek_sonucu(basarili=False)
            raise ServisHatasi(f"{type(hata).__name__}: {str(hata)[:150]}") from hata
        self._istek_sonucu(basarili=True)
        return self._cevabi_coz(islem, yanit, cikti_turu, max_tokens, int((time.monotonic() - bas) * 1000))

    # ------------------------------------------------------------------ çoklu istek
    def coklu_yapilandirilmis(
        self,
        islem: str,
        sistem: str,
        istekler: list[tuple[str, str]],
        cikti_turu: type[pydantic.BaseModel],
        max_tokens: int = 16_000,
        is_parcacigi: int = 4,
    ) -> dict[str, Sonuc]:
        """Birden çok isteği gönderir: (anahtar, mesaj) listesi → {anahtar: sonuç ya da hata}.
        Toplu mod açıksa Message Batches API (yarı fiyat), değilse paralel normal istekler."""
        if not istekler:
            return {}
        if self.toplu:
            return self._toplu(islem, sistem, istekler, cikti_turu, max_tokens)

        def tek(istek: tuple[str, str]) -> tuple[str, Sonuc]:
            try:
                return istek[0], self.yapilandirilmis(islem, sistem, istek[1], cikti_turu, max_tokens)
            except (YzKullanilamaz, ServisHatasi, CiktiBozuk) as hata:
                return istek[0], hata

        with ThreadPoolExecutor(max_workers=is_parcacigi) as havuz:
            return dict(havuz.map(tek, istekler))

    def _tahmini_maliyet(self, sistem: str, mesaj: str) -> float:
        """Göndermeden önce kaba tahmin (Türkçe metinde ~3,2 karakter/token, cevap ~700 token)."""
        girdi_fiyat, cikti_fiyat = self._fiyat()
        return ((len(sistem) + len(mesaj)) / 3.2 * girdi_fiyat + 700 * cikti_fiyat) / 1e6 * TOPLU_INDIRIM

    def _toplu(self, islem, sistem, istekler, cikti_turu, max_tokens) -> dict[str, Sonuc]:
        sonuclar: dict[str, Sonuc] = {}
        try:
            self._kullanilabilir_olmali()
        except YzKullanilamaz as hata:
            return {anahtar: hata for anahtar, _ in istekler}
        # Toplu iş gönderildikten sonra durdurulamaz: bütçeye sığmayanlar baştan ayrılır
        kalan_butce = self.tavan_usd - self.harcanan_usd
        gonderilecek: list[tuple[str, str]] = []
        for anahtar, mesaj in istekler:
            maliyet = self._tahmini_maliyet(sistem, mesaj)
            if maliyet <= kalan_butce:
                kalan_butce -= maliyet
                gonderilecek.append((anahtar, mesaj))
            else:
                sonuclar[anahtar] = ButceAsildi("toplu iş bütçeye sığmadı")
        if not gonderilecek:
            return sonuclar

        kimlikler = {f"i{n}": anahtar for n, (anahtar, _) in enumerate(gonderilecek)}  # API: ^[a-zA-Z0-9_-]{1,64}$
        try:
            is_ = self.istemci.messages.batches.create(
                requests=[
                    {"custom_id": f"i{n}", "params": self._parametreler(sistem, mesaj, cikti_turu, max_tokens)}
                    for n, (_, mesaj) in enumerate(gonderilecek)
                ]
            )
        except anthropic.APIError as hata:
            self._istek_sonucu(basarili=False)
            kayit.warning("Toplu iş açılamadı (%s); normal yoldan gönderiliyor", type(hata).__name__)
            return sonuclar | self._normal_yoldan(islem, sistem, gonderilecek, cikti_turu, max_tokens)
        self._istek_sonucu(basarili=True)
        kayit.info("Toplu iş gönderildi: %s (%d istek, %s)", is_.id, len(gonderilecek), islem)

        bitis = time.monotonic() + self.toplu_bekleme_sn
        while is_.processing_status != "ended" and time.monotonic() < bitis:
            time.sleep(self.toplu_aralik_sn)
            is_ = self.istemci.messages.batches.retrieve(is_.id)
        if is_.processing_status != "ended":
            kayit.warning("Toplu iş %s zamanında bitmedi: iptal ediliyor, biten sonuçlar alınacak", is_.id)
            self.istemci.messages.batches.cancel(is_.id)
            while is_.processing_status != "ended":  # iptal kısa sürede tamamlanır
                time.sleep(min(self.toplu_aralik_sn, 5))
                is_ = self.istemci.messages.batches.retrieve(is_.id)

        for sonuc in self.istemci.messages.batches.results(is_.id):
            anahtar = kimlikler[sonuc.custom_id]
            if sonuc.result.type == "succeeded":
                try:
                    sonuclar[anahtar] = self._cevabi_coz(
                        islem, sonuc.result.message, cikti_turu, max_tokens, None, toplu=True
                    )
                except CiktiBozuk as hata:
                    sonuclar[anahtar] = hata
            # errored / canceled / expired: aşağıda normal yoldan tekrar denenir
        eksik = [(a, m) for a, m in gonderilecek if a not in sonuclar]
        if eksik:
            kayit.info("Toplu işten sonuç gelmeyen %d istek normal yoldan gönderiliyor", len(eksik))
            sonuclar |= self._normal_yoldan(islem, sistem, eksik, cikti_turu, max_tokens)
        return sonuclar

    def _normal_yoldan(self, islem, sistem, istekler, cikti_turu, max_tokens) -> dict[str, Sonuc]:
        toplu, self.toplu = self.toplu, False
        try:
            return self.coklu_yapilandirilmis(islem, sistem, istekler, cikti_turu, max_tokens)
        finally:
            self.toplu = toplu
