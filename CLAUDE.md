# InternReader — Claude için kısa bağlam

Türkiye'deki yazılım/AI staj ilanlarını toplayan, yapay zekâyla ayıklayan ve öğrencilere bülten gönderen proje.
Ayrıntılar README.md'de, güncel durum PLAN.md'nin "Güncel durum" bölümünde. Bu dosyaları baştan okuma, gerekeni grep'le.

## Komutlar
- Test: `.venv/Scripts/python -m pytest -q 2>&1 | tail -3`
- Biçim ve kurallar: `.venv/Scripts/ruff check . && .venv/Scripts/ruff format --check .`
- Site: `cd web && npm run format:check && npm run check && npm run build`
- Şema değişti (db.py): `.venv/Scripts/python -m internreader goc-uret "açıklama"`

## Yapı
internreader/: kaynaklar/ (ATS, kariyer sayfası) · yz/ (istemci, sayfa_okuyucu, siniflandirici, ayrinti_cikarici,
degerlendirme) · isleme/ · depo/ · bulten/ · yayin/ · goc/ (alembic) · boru.py (akış) · __main__.py (komut satırı).
Testler sahte istemcilerle çalışır (tests/conftest.py: SahteHttp, SahteYz); ağa ve API'ye çıkmaz.

## Kurallar
- API anahtarı yalnızca .env'de durur; asla yazdırma.
- LinkedIn, Kariyer.net ve Youthall'dan veri çekilmez. robots.txt'ye uyulur, bot doğrulamaları aşılmaz.
- Commit ve push yalnızca kullanıcı isterse yapılır.
- Gerçek yapay zekâ çağrısından önce tahmini maliyeti söyle (tavanlar: çalıştırma başına 0,50 $, aylık 2 $).
- Windows Git Bash'te heredoc içindeki `\\` tek `\`'e dönüşür. Kaçış karakteri içeren düzenlemeleri Write/Edit ile yap. Dosyalar LF.
- Token tasarrufu: ekran görüntüsü yerine metin; komutları birleştir; çıktıyı kısalt; uzun işi parçalara böl.
- Öğretme modu: önce kavramı anlat, sonra kullanıcı çalıştırsın (docs/DERS_*.md).
