"""Kişiye özel e-posta bülteni.

secim.py     bir ilan abonenin tercihlerine uyuyor mu (sitedeki önizlemeyle aynı kural)
sablon.py    HTML + düz metin e-posta
gonderim.py  kime, hangi ilanlar; gönderim kayıtları
"""

from internreader.bulten.gonderim import bultenleri_gonder
from internreader.bulten.secim import eslesir

__all__ = ["bultenleri_gonder", "eslesir"]
