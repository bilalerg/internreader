"""Veritabanı şemasını hazırlar: bekleyen göçleri (internreader/goc/surumler) uygular.

- Yeni veritabanı: bütün göçler sırayla uygulanır.
- Göç sistemi gelmeden önce kurulmuş veritabanı (tablolar var, alembic_version yok): ilk göç "zaten uygulanmış"
  diye işaretlenir, sonra kalanlar uygulanır. Böylece 18.10'dan önceki yerel veriler kaybolmaz.
- Postgres'te API ve sabah işi aynı anda açılırsa danışma kilidi (advisory lock) birini bekletir; göç bir kez çalışır.
- SQLite'ta göç sırasında dış anahtar denetimi kapatılır: SQLite tablo değiştirirken tabloyu yeniden kurar ve
  denetim açıkken bu, bağlı kayıtların (ör. sınıflandırmalar) zincirleme silinmesine yol açabilir.
"""

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, Engine, inspect, text

kayit = logging.getLogger(__name__)

GOC_KLASORU = Path(__file__).parent / "goc"
TEMEL_SURUM = "0001"  # göç sisteminden önceki şema
KILIT_NO = 727_274_001  # Postgres danışma kilidi için sabit bir sayı


def alembic_ayari(baglanti: Connection | None = None) -> Config:
    ayar = Config()
    ayar.set_main_option("script_location", str(GOC_KLASORU))
    ayar.set_main_option("path_separator", "os")
    ayar.set_main_option("version_locations", str(GOC_KLASORU / "surumler"))
    ayar.attributes["baglanti"] = baglanti
    return ayar


def guncel_surum(motor: Engine) -> str | None:
    with motor.connect() as baglanti:
        return MigrationContext.configure(baglanti).get_current_revision()


def son_surum() -> str:
    return ScriptDirectory.from_config(alembic_ayari()).get_current_head()


def semayi_hazirla(motor: Engine) -> None:
    sqlite = motor.dialect.name == "sqlite"
    with motor.connect() as baglanti:
        if sqlite:
            baglanti.exec_driver_sql("PRAGMA foreign_keys=OFF")
            baglanti.commit()
        with baglanti.begin():
            if motor.dialect.name == "postgresql":
                baglanti.execute(text("SELECT pg_advisory_xact_lock(:no)"), {"no": KILIT_NO})
            tablolar = set(inspect(baglanti).get_table_names())
            ayar = alembic_ayari(baglanti)
            if "alembic_version" not in tablolar and "firmalar" in tablolar:
                kayit.info("Göç sistemi öncesi veritabanı: temel sürüm (%s) işaretleniyor", TEMEL_SURUM)
                command.stamp(ayar, TEMEL_SURUM)
            command.upgrade(ayar, "head")
        if sqlite:
            baglanti.exec_driver_sql("PRAGMA foreign_keys=ON")
            baglanti.commit()
