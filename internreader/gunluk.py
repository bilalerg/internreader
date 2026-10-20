"""Kayıt (log) ayarı: print yerine seviyeli, zaman damgalı kayıt. Sunucuda bu kayıtlar dosyaya/izlemeye gider."""

import logging
import sys


def kayit_kur(seviye: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, seviye.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,  # kayıtlar stderr'e: stdout yalnızca komutun verisi (ör. durum JSON'u) için temiz kalır
        force=True,
    )
    # Kütüphanelerin ayrıntılı kayıtlarını sustur (urllib3 her yeniden denemeyi WARNING olarak yazar;
    # başarısız istekler zaten bizim kodumuzda özetleniyor)
    for gurultulu in ("urllib3", "httpx", "httpx2", "anthropic", "alembic"):
        logging.getLogger(gurultulu).setLevel(logging.ERROR)
