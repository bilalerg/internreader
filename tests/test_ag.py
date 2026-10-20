"""Ağ katmanının ağdan bağımsız parçaları: gövde okuma sınırları ve karakter kodlaması."""

import pytest
import requests

from internreader.ag import govdeyi_oku, metni_coz


class SahteYanit:
    def __init__(self, parcalar, url="https://f.com/kariyer"):
        self.parcalar, self.url = parcalar, url

    def iter_content(self, chunk_size):
        yield from self.parcalar


def test_charset_yoksa_utf8_turkce_bozulmaz():
    # requests bu durumda Latin-1 varsayıp "YazÄ±lÄ±m" üretiyordu
    assert metni_coz("Yazılım Stajyeri".encode(), "text/html") == "Yazılım Stajyeri"


def test_meta_charset_ve_turkce_windows_kodlamasi():
    icerik = '<meta charset="windows-1254"><h1>Yazılım Mühendisi</h1>'.encode("cp1254")
    assert "Yazılım Mühendisi" in metni_coz(icerik, "text/html")
    assert "Yazılım" in metni_coz("Yazılım".encode("cp1254"))  # hiçbir ipucu yoksa: utf-8 olmadı → cp1254


def test_basliktaki_charset_once_gelir():
    assert metni_coz("Şirket".encode("iso-8859-9"), "text/html; charset=ISO-8859-9") == "Şirket"


def test_govde_boyutu_sinirlanir():
    assert len(govdeyi_oku(SahteYanit([b"a" * 1000] * 10), azami_bayt=2500)) == 2500


def test_damla_damla_gonderen_sunucu_toplam_sureye_takilir():
    with pytest.raises(requests.Timeout):
        govdeyi_oku(SahteYanit([b"x"] * 5), azami_bayt=10_000, toplam_sure=-1)
