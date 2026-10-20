# InternReader

Türkiye'deki **yazılım, yapay zekâ ve veri staj / junior / yeni mezun** ilanlarını şirketlerin kendi
sitelerinden ve ilan sistemlerinden toplayan, yapay zekâyla "öğrenciye uygun mu?" diye ayıklayan açık kaynak araç.

*Collects software/AI internship and junior job postings in Türkiye directly from company career pages and ATS
boards, classifies them with an LLM (Claude Haiku) under a strict cost budget, and emails each subscriber only the
listings matching their city, field and level.*

## Neden?

Öğrenci ilanları dağınık: bir kısmı şirketin kendi kariyer sayfasında, bir kısmı Lever/Greenhouse gibi
sistemlerde, bir kısmı hiçbir platformda yok. Elle tutulan listeler birkaç haftada güncelliğini yitiriyor.
InternReader bu işi her gün otomatik yapar ve sonucu tek bir listede toplar.

## Nasıl çalışır?

```
firmalar (1.300+)
   │
   ├─ ilan sistemi biliniyorsa (Lever, Greenhouse, Ashby, Workable, Recruitee, SmartRecruiters, Breezy, Workday)
   │     → herkese açık API'den ilanlar (yapay zekâ gerekmez)
   │
   └─ yalnızca kariyer sayfası varsa
         → sayfa indirilir → değişmediyse önbellekten (ücretsiz)
                           → değiştiyse yapay zekâ pozisyonları çıkarır → uydurma kontrolü (başlık sayfada geçmeli)
   │
   ▼
tekilleştirme → veritabanı (ilk/son görülme, kapanan ilanlar)
   │
   ▼
konum ön seçimi (Türkiye / uzaktan) → yalnızca YENİ ilanlar yapay zekâyla sınıflanır (30'lu partiler)
   │                                   seviye: staj, uzun dönem staj, yarı zamanlı, junior, yeni mezun, deneyimli
   │                                   rol: yazılım, yapay zekâ, veri, diğer teknik, teknik değil
   │                                   (aynı ilan yeni adresle yeniden yayınlandıysa eski karar kullanılır: imza)
   ▼
ayrıntılar: öğrenciye uygun ilanın metninden özet, son başvuru, kimler başvurabilir, çalışma modeli, ücret,
   │        teknolojiler (her ilan bir kez; teknoloji adı metinde geçmiyorsa ve tarih saçmaysa kod atar)
   ▼
yayın: JSON (site) + istatistik → bülten: her aboneye tercihine uyan, daha önce gönderilmemiş ilanlar
   ▼
bakım: onaylanmamış kayıtlar, eski gönderim kayıtları, kapanmış ilanların metinleri silinir
```

## Maliyet tasarımı

Yapay zekâ yalnızca gerektiğinde ve sınırlı bütçeyle çağrılır:

| Önlem | Etkisi |
|---|---|
| Sayfa içerik özeti (hash) önbelleği | Değişmeyen kariyer sayfası tekrar okunmaz |
| Her ilan bir kez sınıflanır | Sonuç veritabanında saklanır |
| Toplu sınıflandırma (30 ilan / istek) | İstek başına sabit maliyet paylaşılır |
| Sınıflandırma imzası (firma + başlık + açıklama özeti) | Yeniden yayınlanan ilan yapay zekâya gitmez |
| Ayrıntılar yalnızca öğrenciye uygun ilanlarda, bir kez | Günde birkaç düzine ilan; ilan başına ~0,0004 $ |
| Toplu mod (`INTERNREADER_YZ_TOPLU=1`, Message Batches) | Yarı fiyat; 45 dk'da bitmezse normal yoldan devam |
| Konum ön seçimi | Yurt dışı ilanlar yapay zekâya hiç gitmez |
| Çalıştırma ve aylık bütçe tavanı | Tavan dolunca sistem yapay zekâsız çalışmaya devam eder |
| Servis sigortası | API üst üste hata verirse o çalıştırmada bir daha denenmez |
| Her çağrının kaydı | `yz_kullanim` tablosu: token, maliyet, süre, durum (tamam / kesildi / reddedildi / bozuk) |

İlk gün iki tam çalıştırma (1.300 firma; 647 ilan sınıflandırma + 141 sayfa okuma) toplam **0,159 $** tuttu.
Günlük çalıştırmalarda yalnızca yeni ilanlar ve değişen sayfalar ücretlidir.

### Doğruluk ölçümü

`veri/degerlendirme/siniflandirma.jsonl`: elle etiketlenmiş gerçek ilanlar. `python -m internreader degerlendir`
sınıflandırıcıyı bu sette çalıştırır; prompt ya da model her değiştiğinde yeniden çalıştırılıp sonuç kıyaslanır.

| Ölçüm (19.10.2026, 30 örnek, claude-haiku-5-5) | Sonuç |
|---|---|
| Seviye doğruluğu | %96 |
| Rol doğruluğu | %100 |
| "Öğrenciye uygun" kararı: isabet / kapsama | %100 / %100 |
| Maliyet | 0,0015 $ |

Set şimdilik kolay örneklere ağırlık veriyor; zor örnekler ("Engineer II", "All Levels", "Uzman Yardımcısı")
eklendikçe rakamlar düşecek. Ölçümün asıl amacı da bunları bulmak.

## Kurallar

- LinkedIn, Kariyer.net, Youthall gibi platformlardan veri **çekilmez**; bot doğrulamaları aşılmaz.
- Sitelerin `robots.txt` kurallarına uyulur; istekler açık bir kullanıcı ajanıyla yapılır.
- İlan metni kopyalanmaz; başlık, firma, konum ve orijinal ilana bağlantı verilir.

## Kurulum (yerel)

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt pytest ruff   # Linux/macOS: .venv/bin/pip
cp .env.example .env                                         # ANTHROPIC_API_KEY değerini doldurun
```

## Komutlar

```bash
python -m internreader ice-aktar veri/firmalar.csv      # firma listesini veritabanına al
python -m internreader kesif [--yokla] [--kaynak K]     # ilan sistemi / kariyer sayfası keşfi (ayda bir)
python -m internreader tara [--yz-tavani 0.50]          # ilanları topla + sınıflandır
python -m internreader yayinla                          # cikti/: README tablosu, ilanlar.json, WhatsApp özeti
python -m internreader calistir                         # tara + ayrıntılar + yayınla + bülten + bakım (her sabah)
python -m internreader bulten-gonder                    # yalnızca bülten (SMTP yoksa cikti/giden_eposta/'ya yazar)
python -m internreader bakim                            # eski/geçersiz kayıtları temizle
python -m internreader durum                            # veritabanı özeti ve bu ayki yapay zekâ harcaması
python -m internreader degerlendir                      # sınıflandırıcı doğruluğu (etiketli set, ~0,002 $)
python -m internreader api [--port 8000]                # abonelik API'si (geliştirme sunucusu)
python -m internreader goc-uret "açıklama"              # db.py değişince veritabanı göçü üret (alembic)
```

## Site (web/)

Astro ile statik derlenen tek sayfalık site + React adaları (yalnızca etkileşimli parçalar tarayıcıda çalışır):

- **Türkiye haritası simülasyonu** (`TurkiyeRadari.tsx`): Natural Earth sınırından derlemede hesaplanan nokta haritası;
  okuma çizgisi şehirleri tararken gerçek ilan sayılarıyla nabız atar, gerçek öğrenci ilanları belirir.
- **Nasıl çalışır** (`BoruHatti.tsx`): dört adımlı simülasyon; yapay zekânın bu sabahki gerçek kabul/ret kararları ve gerekçeleri.
- **Bülteni dene + abone ol** (`Bulten.tsx`): şehir/alan/seviye seç → bugünün gerçek ilanlarıyla e-posta önizlemesi → kayıt.
- **Çift onaylı kayıt**: `/onay` ve `/iptal` sayfaları butonla POST atar (e-posta tarayıcıları bağlantıyı açınca kendiliğinden
  onay/çıkış olmaz). Çıkışta e-posta adresi silinir. KVKK aydınlatma metni: `/kvkk`.

```bash
cd web && npm install
npm run dev            # http://localhost:4321  (/api istekleri yerel API'ye: python -m internreader api)
npm run build          # dist/  (veri: INTERNREADER_CIKTI ya da ../cikti, yoksa src/veri/ornek)
npm run format         # Prettier
```

Tasarım dili "sabah gazetesi + fosforlu kalem": kâğıt zemin, mürekkep yazı, tek vurgu rengi; gece modunda "gece baskısı".
Fontlar (Fraunces, IBM Plex) siteyle birlikte sunulur; çerez ve takip kodu yoktur.

## Kod yapısı

```
internreader/
  ayar.py            ayarlar (.env / ortam değişkenleri), model fiyatları
  ag.py              HTTP: yeniden deneme, robots.txt, kapalı sunucuyu hızlı atlama
  model.py           alan modelleri: FirmaBilgisi, Ilan
  db.py              veritabanı tabloları (SQLite yerelde, Postgres sunucuda)
  sema.py + goc/     şema göçleri (alembic): her açılışta "upgrade head"; Postgres'te kilitle, SQLite'ta batch modu
  depo/              veritabanı işlemleri, konuya göre: firmalar, ilanlar, ayrintilar, aboneler, bulten, kullanim…
  kaynaklar/         ats.py (8 ilan sistemi), kariyer_sayfasi.py (HTML → metin + bağlantılar)
  yz/                istemci.py (bütçe, sigorta, kayıt, toplu mod), sayfa_okuyucu.py, siniflandirici.py,
                     ayrinti_cikarici.py (özet, son başvuru…), degerlendirme.py (doğruluk ölçümü)
  isleme/            filtre.py (konum, yedek kural), tekillestirme.py
  yayin/             readme.py, json_disa.py, whatsapp.py, istatistik.py (sitenin verisi)
  boru.py            iş akışı: katmanları sırayla bağlar
  kesif.py           firmaların ilan sistemini ve kariyer sayfasını bulur
  abonelik.py        çift onaylı kayıt, onay, imzalı çıkış bağlantısı
  eposta.py          gönderici arayüzü: SMTP (465/587) ya da dosyaya yazan (deneme)
  bulten/            secim.py (tercih eşleşmesi), sablon.py (HTML + düz metin, tek tıkla çıkış), gonderim.py
  bakim.py           günlük temizlik (KVKK: gereğinden uzun veri tutulmaz)
  api.py             FastAPI: /api/saglik (veritabanını yoklar), /api/abone, /onay, /iptal, /iptal-tek (RFC 8058)
  __main__.py        komut satırı
tests/               ağa ve yapay zekâya bağlanmayan testler (sahte istemcilerle)
web/                 site (Astro + React + Tailwind)
ops/                 Caddyfile, crontab
```

## Testler

```bash
pytest -q          # SQLite
ruff check . && ruff format --check .
cd web && npm run format:check && npm run check && npm run build
```

CI her push'ta testleri hem SQLite hem gerçek bir Postgres üzerinde çalıştırır (`.github/workflows/ci.yml`).

## Sunucuda çalıştırma

```
internet ──► Caddy (HTTPS, 80/443) ──► /          statik site (her sabah yeniden derlenir)
                                   ├─► /api/*     FastAPI (abonelik)  ──► Postgres
                                   └─► /veri/*    yalnızca ilanlar.json ve istatistik.json
cron 07:00 ──► internreader calistir (tara + yayınla) ──► site-derle
```

```bash
mkdir -p cikti && sudo chown 10001:10001 cikti     # konteyner güvenlik için root olmayan kullanıcıyla çalışır
docker compose up -d db api caddy
docker compose run --rm internreader ice-aktar veri/firmalar.csv
docker compose run --rm internreader calistir && docker compose run --rm site-derle
```

Günlük zamanlama, gece yedeği ve aylık keşif için `ops/crontab`. Gizli değerler (`ANTHROPIC_API_KEY`,
`POSTGRES_PASSWORD`, `INTERNREADER_GIZLI_ANAHTAR`, `SITE_ALAN_ADI`) yalnızca sunucudaki `.env` dosyasında durur.

### Yayına hazırlık listesi

- [ ] `web/src/ayarlar.ts`: `veriSorumlusu`, `iletisimEpostasi` (KVKK için zorunlu), `whatsappKanali`
- [ ] KVKK aydınlatma metnini gözden geçir (`web/src/pages/kvkk.astro`)
- [ ] E-posta sağlayıcısı seç, `.env`'e `SMTP_*` ve `EPOSTA_KIMDEN` yaz (`.env.example`'da açıklamalı)
- [ ] Gönderen alan adı için DNS'te **SPF, DKIM, DMARC** kayıtları (sağlayıcı değerleri verir); yoksa e-postalar spama düşer
- [ ] `INTERNREADER_GIZLI_ANAHTAR` uzun ve rastgele; değişirse eski çıkış bağlantıları çalışmaz (geliştirme anahtarıyla
      gerçek gönderim kod tarafından reddedilir)
- [ ] Alan adının DNS kaydı sunucuya yönlendirilmiş olmalı (Caddy sertifikayı kendisi alır)

## Yol haritası

- [x] 8 ilan sistemi + kariyer sayfası okuyucu, uydurma koruması
- [x] Yapay zekâ sınıflandırma, bütçe tavanları, önbellek
- [x] Veritabanı (ilk/son görülme, kapanan ilanlar), Docker, CI
- [x] Site: tanıtım, canlı simülasyonlar, bülten önizlemesi, çift onaylı kayıt, KVKK
- [x] Kişiye özel bülten: tercih eşleşmesi, gönderilenleri hatırlama, günlük/haftalık, tek tıkla çıkış
- [x] Şema göçleri (alembic), sağlık kontrolü, günlük bakım
- [x] Yapay zekâ: ilan ayrıntıları, imza ile tekrar kullanım, toplu mod (yarı fiyat), doğruluk ölçümü
- [ ] Gerçek e-posta gönderimi (SMTP sağlayıcısı + SPF/DKIM/DMARC)
- [ ] Değerlendirme setini 50 örneğe tamamla (zor örneklerle)
- [ ] Sunucuya kurulum (VPS), günlük WhatsApp kanalı
- [ ] MCP sunucusu (kendi yapay zekâ asistanınızdan ilan sorgulama)
