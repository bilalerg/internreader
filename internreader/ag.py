"""Ağ katmanı: bütün HTTP istekleri buradan geçer.

- Geçici hatalarda (429, 5xx, bağlantı kopması) kademeli bekleyerek yeniden dener.
- Kariyer sayfalarında robots.txt kurallarına uyar (site izin vermiyorsa sayfayı okumayız).
- Bağlantı kabul etmeyen sunucuyu robots.txt adımında fark eder ve o sunucuya bir daha denemez (hızlı başarısızlık).
- Herkese aynı, açık bir kullanıcı ajanıyla (InternReader/...) kendini tanıtır.
"""

import json
import logging
import re
import threading
import time
import urllib.parse
import urllib.robotparser

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

kayit = logging.getLogger(__name__)


class RobotsEngeli(Exception):
    """Site robots.txt ile bu sayfanın okunmasına izin vermiyor."""


class HttpIstemci:
    # Sunucu bu sürede bağlantıyı kabul etmezse kapalı sayılır (okuma süresi ayrı). Düşük tutmak cazip ama bazı
    # Türk barındırma firmalarının DDoS korumaları ilk bağlantı denemelerini düşürüyor: Windows/VPN üzerinden
    # bağlantı ~20 sn sürebiliyor (ölçüldü, 18.10.2026). 8 sn ile çalışan 28 site "kapalı" sanılmıştı.
    BAGLANTI_ZAMAN_ASIMI = 25

    def __init__(self, kullanici_ajani: str, zaman_asimi: int = 25, havuz_boyutu: int = 16):
        self.zaman_asimi = (self.BAGLANTI_ZAMAN_ASIMI, zaman_asimi)
        self.kullanici_ajani = kullanici_ajani
        self.oturum = requests.Session()
        self.oturum.headers.update({"User-Agent": kullanici_ajani, "Accept-Language": "tr,en;q=0.8"})
        yeniden = Retry(
            total=2,
            connect=1,
            read=1,
            backoff_factor=1.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "POST"}),
            respect_retry_after_header=True,
        )
        adaptor = HTTPAdapter(max_retries=yeniden, pool_connections=havuz_boyutu, pool_maxsize=havuz_boyutu)
        self.oturum.mount("https://", adaptor)
        self.oturum.mount("http://", adaptor)
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._ulasilamayan: set[str] = set()  # bağlantı kabul etmeyen sunucular (bu çalıştırma boyunca)
        self._kilit = threading.Lock()

    # --- robots.txt ---
    def izinli_mi(self, url: str) -> bool:
        p = urllib.parse.urlparse(url)
        kok = f"{p.scheme}://{p.netloc}"
        with self._kilit:
            onbellekte = kok in self._robots
            rp = self._robots.get(kok)
        if not onbellekte:
            rp = urllib.robotparser.RobotFileParser()
            try:
                with self.oturum.get(
                    f"{kok}/robots.txt", timeout=(self.BAGLANTI_ZAMAN_ASIMI, 10), stream=True
                ) as yanit:
                    if yanit.status_code >= 400:
                        rp = None  # robots.txt yok → kısıt yok
                    else:
                        metin = metni_coz(govdeyi_oku(yanit, 500_000, toplam_sure=30))
                        rp.parse(metin.splitlines())
            except requests.ConnectionError:  # sunucu bağlantı kabul etmiyor → sayfası da açılmaz
                with self._kilit:
                    self._ulasilamayan.add(kok)
                rp = None
            except requests.RequestException:
                rp = None
            with self._kilit:
                self._robots[kok] = rp
        return True if rp is None else rp.can_fetch(self.kullanici_ajani, url)

    # --- istekler ---
    def sayfa(self, url: str, robots_kontrolu: bool = True) -> tuple[str, str]:
        """(son adres, HTML metni) döndürür. robots.txt izin vermezse RobotsEngeli fırlatır."""
        if robots_kontrolu and not self.izinli_mi(url):
            raise RobotsEngeli(url)
        p = urllib.parse.urlparse(url)
        if f"{p.scheme}://{p.netloc}" in self._ulasilamayan:
            raise requests.ConnectionError(f"{p.netloc} bağlantı kabul etmiyor")
        with self.oturum.get(url, timeout=self.zaman_asimi, stream=True) as yanit:
            yanit.raise_for_status()
            icerik = govdeyi_oku(yanit, SAYFA_AZAMI_BAYT)
            return yanit.url, metni_coz(icerik, yanit.headers.get("content-type", ""))

    def json_al(self, url: str):
        with self.oturum.get(url, timeout=self.zaman_asimi, stream=True) as yanit:
            yanit.raise_for_status()
            return json.loads(govdeyi_oku(yanit, JSON_AZAMI_BAYT))

    def json_gonder(self, url: str, govde: dict):
        with self.oturum.post(url, json=govde, timeout=self.zaman_asimi, stream=True) as yanit:
            yanit.raise_for_status()
            return json.loads(govdeyi_oku(yanit, JSON_AZAMI_BAYT))


# --- gövde okuma ve karakter kodlaması (ağdan bağımsız, test edilebilir) ---
SAYFA_AZAMI_BAYT = 3_000_000  # daha büyük "kariyer sayfası" yoktur; fazlası kesilir
JSON_AZAMI_BAYT = 40_000_000  # büyük firmaların ATS cevapları (açıklamalarıyla) birkaç MB olabilir
TOPLAM_SURE_SN = 90


def govdeyi_oku(yanit, azami_bayt: int, toplam_sure: float = TOPLAM_SURE_SN) -> bytes:
    """Cevabı parça parça okur. requests'in zaman aşımı iki veri parçası arasındaki beklemeyi sınırlar, toplam süreyi
    değil: veriyi damla damla gönderen bir sunucu isteği saatlerce açık tutabiliyor (18.10'da keşif böyle takıldı).
    Burada hem toplam süre hem boyut sınırlanır."""
    bitis = time.monotonic() + toplam_sure
    parcalar, boyut = [], 0
    for parca in yanit.iter_content(chunk_size=65_536):
        parcalar.append(parca)
        boyut += len(parca)
        if boyut >= azami_bayt:
            break
        if time.monotonic() > bitis:
            raise requests.Timeout(f"{yanit.url}: {toplam_sure:.0f} sn içinde indirilemedi")
    return b"".join(parcalar)[:azami_bayt]


_META_KODLAMA = re.compile(rb"""<meta[^>]+charset\s*=\s*["']?\s*([A-Za-z0-9_\-]+)""", re.I)


def metni_coz(icerik: bytes, content_type: str = "") -> str:
    """Baytları metne çevirir. Sıra: HTTP başlığındaki charset → sayfadaki <meta charset> → UTF-8 → cp1254 (Türkçe
    Windows). requests başlıkta charset yoksa Latin-1 varsayıyor; 18.10 ölçümünde sayfaların ~%5'inde "Yazılım"
    "YazÄ±lÄ±m" oluyordu (yapay zekâ okuması ve uydurma kontrolü bozuluyordu)."""
    adaylar = []
    if eslesme := re.search(r"charset\s*=\s*[\"']?([A-Za-z0-9_\-]+)", content_type, re.I):
        adaylar.append(eslesme.group(1))
    if eslesme := _META_KODLAMA.search(icerik[:8192]):
        adaylar.append(eslesme.group(1).decode("ascii"))
    for kodlama in [*adaylar, "utf-8", "cp1254"]:
        try:
            return icerik.decode(kodlama).lstrip("﻿")  # baştaki BOM işareti metne karışmasın
        except (LookupError, UnicodeDecodeError):
            continue
    return icerik.decode("utf-8", errors="replace")
