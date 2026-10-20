"""Kariyer sayfası önbelleği: değişmeyen sayfa yapay zekâya tekrar gönderilmez."""

import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from internreader.db import SayfaOnbellek, simdi


def url_ozeti(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def onbellek_hepsi(oturum: Session) -> dict[str, tuple[str, dict]]:
    return {k.url_ozeti: (k.icerik_ozeti, k.sonuc) for k in oturum.scalars(select(SayfaOnbellek))}


def onbellek_yaz(oturum: Session, kayitlar: dict[str, tuple[str, str, dict]]) -> None:
    """kayitlar: url → (url_özeti, içerik_özeti, sonuç)"""
    for url, (u_ozet, i_ozet, sonuc) in kayitlar.items():
        oturum.merge(SayfaOnbellek(url_ozeti=u_ozet, url=url, icerik_ozeti=i_ozet, sonuc=sonuc, tarih=simdi()))
