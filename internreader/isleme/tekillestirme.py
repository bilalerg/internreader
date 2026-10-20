"""Tekilleştirme: aynı ilan birden fazla kez gelirse (ör. bir firma aynı pozisyonu iki şehir için listelerse) tek kayıt.

Anahtar ilanın URL'sinden türetilen kimliktir. Aynı kimlik tekrar gelirse konumlar birleştirilir.
"""

from internreader.model import Ilan


def tekillestir(ilanlar: list[Ilan]) -> list[Ilan]:
    tekil: dict[str, Ilan] = {}
    for ilan in ilanlar:
        onceki = tekil.get(ilan.kimlik)
        if onceki is None:
            tekil[ilan.kimlik] = ilan
        elif ilan.konum and ilan.konum not in onceki.konum:
            onceki.konum = f"{onceki.konum}, {ilan.konum}" if onceki.konum else ilan.konum
    return list(tekil.values())
