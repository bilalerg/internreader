"""Ortak test araçları: geçici veritabanı, sahte ağ istemcisi, sahte yapay zekâ istemcisi.

Testler internete ve gerçek yapay zekâya HİÇ bağlanmaz: hızlıdır, ücretsizdir, her seferinde aynı sonucu verir.
Varsayılan veritabanı geçici bir SQLite dosyasıdır. TEST_DATABASE_URL verilirse (CI'da Postgres) testler orada koşar;
böylece sunucudaki veritabanıyla uyumsuzluk (ör. alan uzunluğu sınırları) sunucuya gitmeden yakalanır.
"""

import os

import pytest
import requests

from internreader.db import Taban, oturum_fabrikasi
from internreader.yz.istemci import YzIstemci


@pytest.fixture
def oturum(tmp_path):
    url = os.getenv("TEST_DATABASE_URL") or f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    fabrika = oturum_fabrikasi(url)
    yield fabrika
    motor = fabrika.kw["bind"]
    if not url.startswith("sqlite"):
        # paylaşılan test veritabanı her testten sonra temizlenir (göç sürüm tablosu dahil)
        Taban.metadata.drop_all(motor)
        with motor.begin() as baglanti:
            baglanti.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
    motor.dispose()


class SahteHttp:
    """URL → hazır cevap sözlüğüyle çalışan ağ istemcisi."""

    def __init__(self, jsonlar=None, sayfalar=None):
        self.jsonlar = jsonlar or {}
        self.sayfalar = sayfalar or {}
        self.istekler = []  # (url, gövde, başlıklar): testler gönderilen sorguyu ve anahtar başlığını denetler

    def _cevap(self, url, govde, basliklar):
        """Cevap hazır bir değer, fırlatılacak bir hata ya da (url, gövde) → değer fonksiyonu olabilir."""
        self.istekler.append((url, govde, basliklar))
        for anahtar, deger in self.jsonlar.items():
            if anahtar in url:
                if isinstance(deger, Exception):
                    raise deger
                return deger(url, govde) if callable(deger) else deger
        yanit = requests.Response()
        yanit.status_code, yanit.url = 404, url
        raise requests.HTTPError(f"404 Client Error: Not Found for url: {url}", response=yanit)

    def json_al(self, url, basliklar=None):
        return self._cevap(url, None, basliklar)

    def json_gonder(self, url, govde, basliklar=None):
        return self._cevap(url, govde, basliklar)

    def sayfa(self, url, robots_kontrolu=True):
        if url not in self.sayfalar:
            raise requests.ConnectionError(url)
        return url, self.sayfalar[url]


class SahteYz(YzIstemci):
    """`cevaplar` fonksiyonu (cikti_turu, mesaj) → nesne döndürür; gerçek API çağrılmaz."""

    def __init__(self, cevaplar, tavan_usd=1.0):
        super().__init__("claude-haiku-5-5", tavan_usd, istemci=object())
        self.cevaplar = cevaplar
        self.cagrilar = []

    def yapilandirilmis(self, islem, sistem, mesaj, cikti_turu, max_tokens=16_000):
        self.cagrilar.append((islem, mesaj))
        return self.cevaplar(cikti_turu, mesaj)


@pytest.fixture
def sahte_http():
    return SahteHttp
