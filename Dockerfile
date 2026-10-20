# InternReader çalışma imajı. Sunucuda: docker compose run --rm internreader calistir
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /uygulama

# Önce yalnızca bağımlılıklar: kod değişince bu katman önbellekten gelir, imaj saniyeler içinde yeniden kurulur
COPY requirements.txt requirements-sunucu.txt ./
RUN pip install -r requirements-sunucu.txt

COPY internreader ./internreader
COPY veri/firmalar.csv veri/tohum_firmalar.csv ./veri/

# Kök kullanıcıyla çalışmaz (güvenlik): yalnızca çıktı klasörüne yazabilen ayrı bir kullanıcı
RUN useradd --create-home --uid 10001 internreader \
    && mkdir -p cikti \
    && chown -R internreader:internreader /uygulama/cikti
USER internreader

ENTRYPOINT ["python", "-m", "internreader"]
CMD ["durum"]
