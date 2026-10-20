"""Alembic ortamı: bağlantı programdan verilir (internreader/sema.py), ayrı bir alembic.ini dosyası yoktur."""

from alembic import context

from internreader.db import Taban

baglanti = context.config.attributes["baglanti"]
context.configure(
    connection=baglanti,
    target_metadata=Taban.metadata,
    render_as_batch=baglanti.dialect.name == "sqlite",  # SQLite ALTER TABLE'ı kısıtlı destekler: tablo yeniden kurulur
    compare_type=True,
)
with context.begin_transaction():
    context.run_migrations()
