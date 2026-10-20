"""Küçük anahtar-değer kayıtları (son yayın zamanı, son tarama özeti...)."""

from sqlalchemy.orm import Session

from internreader.db import Durum


def durum_al(oturum: Session, anahtar: str) -> str | None:
    kayit = oturum.get(Durum, anahtar)
    return kayit.deger if kayit else None


def durum_yaz(oturum: Session, anahtar: str, deger: str) -> None:
    oturum.merge(Durum(anahtar=anahtar, deger=deger))
