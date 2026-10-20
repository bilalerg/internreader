"""Veritabanı göçleri: modelle aynı şemayı üretir mi, eski (göç öncesi) veritabanını kayıpsız günceller mi."""

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect, text

from internreader.db import Taban, motor_olustur
from internreader.sema import TEMEL_SURUM, alembic_ayari, guncel_surum, semayi_hazirla, son_surum


def test_goclerle_kurulan_sema_modellerle_birebir_ayni(tmp_path):
    motor = motor_olustur(f"sqlite:///{(tmp_path / 'g.db').as_posix()}")
    semayi_hazirla(motor)
    with motor.connect() as baglanti:
        farklar = compare_metadata(MigrationContext.configure(baglanti), Taban.metadata)
    assert farklar == [], f"modelde göçü yazılmamış değişiklik var: {farklar}"
    assert guncel_surum(motor) == son_surum()


def test_goc_oncesi_veritabani_verisiyle_birlikte_guncellenir(tmp_path):
    motor = motor_olustur(f"sqlite:///{(tmp_path / 'eski.db').as_posix()}")
    with motor.begin() as baglanti:  # 18.10 öncesi gibi: temel şema var, sürüm tablosu yok
        command.upgrade(alembic_ayari(baglanti), TEMEL_SURUM)
        baglanti.exec_driver_sql("DROP TABLE alembic_version")
        baglanti.execute(
            text(
                "INSERT INTO firmalar (anahtar, ad, etiket, aktif, eklenme) VALUES ('x.com', 'X', '[]', 1, '2026-10-01')"
            )
        )
    semayi_hazirla(motor)
    with motor.connect() as baglanti:
        assert baglanti.execute(text("SELECT ad FROM firmalar")).scalar() == "X"  # veri korundu
        assert "ilan_ayrintilari" in inspect(baglanti).get_table_names()
    assert guncel_surum(motor) == son_surum()
    semayi_hazirla(motor)  # ikinci kez çalıştırmak zararsız
