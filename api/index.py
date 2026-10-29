"""Vercel girişi: abonelik API'si sunucusuz fonksiyon olarak çalışır.

vercel.json /api/* isteklerini buraya yönlendirir; yol değişmeden FastAPI'ye ulaşır (/api/abone, /api/saglik...).
Ayarlar Vercel'in ortam değişkenlerinden okunur (DATABASE_URL, INTERNREADER_GIZLI_ANAHTAR, SMTP_*...).
Kendi sunucumuzda bu dosya kullanılmaz; orada uvicorn internreader.api:uygulama --factory çalışır.
"""

from internreader.api import uygulama

app = uygulama()
