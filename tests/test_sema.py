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


def test_dogrulanmis_kariyer_adresleri_yalnizca_eski_degeri_degistirir(tmp_path):
    motor = motor_olustur(f"sqlite:///{(tmp_path / 'kariyer.db').as_posix()}")
    with motor.begin() as baglanti:
        command.upgrade(alembic_ayari(baglanti), "0009")
        ekle = text(
            "INSERT INTO firmalar (anahtar, ad, kariyer, etiket, aktif, eklenme) "
            "VALUES (:key, :name, :career, '[]', 1, '2026-11-01')"
        )
        for key, name, career in (
            ("avikon.com.tr", "Avikon", "https://www.avikon.com.tr/tr/kariyer"),
            ("idenfit.com", "Idenfit", "https://idenfit.com/insan-kaynaklari-yonetimi-modulu/"),
            ("techsign.com.tr", "Techsign", "https://techsign.ai/en/career/"),
        ):
            baglanti.execute(ekle, {"key": key, "name": name, "career": career})
    semayi_hazirla(motor)
    with motor.connect() as baglanti:
        got = {ad: kariyer for ad, kariyer in baglanti.execute(text("SELECT ad, kariyer FROM firmalar"))}
        assert got == {
            "Avikon": "https://avikon.com.tr/kariyer",
            "Idenfit": None,
            "Techsign": "https://techsign.ai/en/career/",
        }
