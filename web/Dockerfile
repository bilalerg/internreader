# Site derleyici: her sabah günlük taramadan sonra çalışır, güncel veriyle statik siteyi /web/dist'e üretir.
# dist bir Docker volume'üdür; Caddy aynı volume'ü okuyarak siteyi sunar.
#   docker compose run --rm site-derle
FROM node:24-alpine

ENV ASTRO_TELEMETRY_DISABLED=1 \
    NPM_CONFIG_UPDATE_NOTIFIER=false

WORKDIR /web

# Önce bağımlılıklar (önbellek katmanı), sonra kod
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY web/ ./

# INTERNREADER_CIKTI'deki gerçek veri yoksa depodaki örnek veriyle derlenir
CMD ["npm", "run", "build"]
