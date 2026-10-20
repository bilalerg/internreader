"""Veritabanı göçleri (Alembic). Şema değişikliği = numaralı bir göç dosyası (surumler/).

Yeni göç üretmek (modelleri değiştirdikten sonra):
    python -m internreader goc-uret "ne değişti"
Uygulamak: uygulama her açılışta bekleyen göçleri kendisi uygular (bkz. internreader/sema.py).
"""
