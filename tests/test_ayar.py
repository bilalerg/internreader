from internreader.ayar import _site_adresi


def test_site_adresi_gizli_deger_olamaz(monkeypatch):
    monkeypatch.setenv("INTERNREADER_SITE_ADRESI", "a" * 64)
    assert _site_adresi() == "https://internreader.me"


def test_site_adresi_gecerli_url(monkeypatch):
    monkeypatch.setenv("INTERNREADER_SITE_ADRESI", "https://internreader.me/")
    assert _site_adresi() == "https://internreader.me"
