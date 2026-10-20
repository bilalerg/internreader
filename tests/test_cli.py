"""Komut satırı duman testi: komutlar uçtan uca çalışıyor mu (ağ ve yapay zekâ olmadan)."""

import json

from internreader.__main__ import main


def test_ice_aktar_ve_durum(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'cli.db').as_posix()}")
    csv = tmp_path / "firmalar.csv"
    csv.write_text("ad,web,ats,slug,kariyer,etiket\nBeakwise,https://beakwise.com,,,,ai\n", encoding="utf-8")

    assert main(["ice-aktar", str(csv), "--kaynak", "test"]) == 0
    capsys.readouterr()
    assert main(["durum"]) == 0
    durum = json.loads(capsys.readouterr().out)
    assert durum["firma"] == 1 and durum["aktif_ilan"] == 0 and durum["son_tarama"] is None
