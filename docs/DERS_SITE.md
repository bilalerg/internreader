# Ders notu — Site ve abonelik (18 Ekim 2026 akşamı)

Bu akşam InternReader'ın yüzü yapıldı: tanıtım sitesi, canlı simülasyonlar ve e-posta aboneliği. Düzen yine aynı:
sorun → çözüm → dosya → mülakatta tek cümle.

---

## 1. Statik site + "adalar"

**Benzetme:** Basılı bir gazete düşün; sayfanın çoğu sabit kâğıt, sadece birkaç yerde dokununca çalışan çıkartmalar var.

**Ne yaptık:** Astro sayfayı **derleme anında** HTML olarak üretir (hızlı açılır, arama motorları okur). Yalnızca etkileşimli
üç parça (harita, "nasıl çalışır", bülten formu) tarayıcıda React ile canlanır. Bunlara **ada** (island) denir; ekrana
gelince yüklenirler (`client:visible`).

**Dosyalar:** `web/src/pages/index.astro` (sayfa), `web/src/components/*.tsx` (adalar).

> Mülakat: "Siteyi statik derleyip yalnızca etkileşimli bileşenleri hidratladım; sayfa hızlı açılıyor, JS yükü küçük kalıyor."

---

## 2. Python ile site arasında bir sözleşme

**Sorun:** Site veriyi nereden bilecek? Python her sabah ilanları topluyor, site başka bir dilde (TypeScript).

**Çözüm:** Python iki dosya üretir: `ilanlar.json` ve `istatistik.json`. Site bunları okur. İki taraf bu dosyaların biçimi
üzerinde **anlaşmıştır** (sözleşme): `surum` alanı var; bir alan silinirse sürüm artar, okuyan taraf fark eder.
TypeScript tarafında aynı biçim `web/src/veri/tipler.ts` dosyasında yazılı.

> Mülakat: "Veri üreten Python servisi ile siteyi sürümlü bir JSON sözleşmesiyle ayırdım."

---

## 3. Harita simülasyonu: canvas ve performans

**Ne yaptık:** Türkiye sınırı gerçek harita verisinden (Natural Earth) **derleme sırasında** noktalara çevrilir; tarayıcıya
harita kütüphanesi değil, yalnızca ~1.800 noktanın koordinatı gider. Noktalar `<canvas>` üzerine her karede çizilir.

**İnceliklerden üçü** (`web/src/components/TurkiyeRadari.tsx`):
- Ekranda değilken ve sekme gizliyken çizim durur (pil ve işlemci tasarrufu).
- "Hareketi azalt" tercihi olan kullanıcıya sabit görüntü gösterilir (erişilebilirlik).
- Sayaçlar sunucu çıktısında gerçek değerle başlar: JavaScript çalışmasa da arama motoru "0" değil "315" görür.

---

## 4. Çift onaylı kayıt ve güvenlik

**Neden çift onay?** Biri formda başkasının adresini yazabilir. Bülten, ancak adresin sahibi e-postadaki bağlantıya
tıklayınca başlar. Bu hem KVKK için rızanın kanıtı hem de spam'e düşmemek için gerekli.

**Güvenlik önlemleri** (`internreader/api.py`, `internreader/abonelik.py`):
- Veritabanında onay bağlantısının kendisi değil **özeti (hash)** saklanır; veritabanı sızsa bile bağlantılar işe yaramaz.
- Çıkış bağlantısı gizli anahtarla **imzalanır (HMAC)**: kimse başkasının adresini listeden çıkaramaz.
- **Hız sınırı:** aynı yerden 10 dakikada en fazla 5 kayıt isteği.
- **Bal küpü:** insanların görmediği bir alan; botlar doldurur, sessizce elenir.
- **Adres sızdırmama:** "bu adres kayıtlı mı?" sorusu dışarıdan anlaşılamaz; herkes aynı cevabı alır.
- Onay/çıkış **butonla** yapılır: e-posta güvenlik tarayıcıları bağlantıları önceden açınca kendiliğinden onay olmaz.

> Mülakat: "Aboneliği double opt-in yaptım; token'ları hash'li sakladım, çıkış linkini HMAC ile imzaladım, rate limit ve
> honeypot ekledim, kullanıcı enumerasyonunu engelledim."

---

## 5. KVKK: en az veri

Yalnızca e-posta ve tercihler tutulur; IP adresi kaydedilmez, çerez yok. Çıkışta adres **silinir**; onaylanmayan kayıt 72
saat sonra silinir. Metin: `web/src/pages/kvkk.astro`. (Yayından önce veri sorumlusu adı ve iletişim adresi eklenmeli.)

---

## 6. Sunucuda düzen

```
internet ──► Caddy (HTTPS) ──► /         statik site
                           ├─► /api/*    FastAPI ──► Postgres
                           └─► /veri/*   yalnızca iki JSON dosyası
```

**Önemli ayrıntı:** `cikti/` klasöründe WhatsApp metinleri ve e-posta taslakları da var. Caddy bu klasörün tamamını değil,
**yalnızca iki dosyayı** dışarı açar (izin listesi). Site her sabah taramadan sonra güncel veriyle yeniden derlenir (~6 sn).

---

## 7. Bu akşamki hatalardan dersler

- **Hidrasyon uyuşmazlığı:** Sayfadaki küçük bir script, React yüklenmeden önce React'in yönettiği öğelere dokunuyordu;
  React "sunucudan gelen HTML farklı" diye uyardı. Kural: React'in alanına dışarıdan dokunma.
- **Yapışık kelimeler ("yalnızcakendi"):** Astro, satır sonu ile bir HTML öğesi arasındaki boşluğu yutabiliyor. Gerçek
  sayfa metninde yapışık kelime arayan küçük bir kontrol yazdım.
- **Aynı adlı iki alan:** Tarama simülasyonunda firma adı ile durum adı aynı anahtarı (`ad`) kullanınca biri diğerinin
  üstüne yazdı; listede firma yerine "değişmedi" görünüyordu.
- **Yanlış sunucu:** Önizleme aracı başka bir klasördeki ayar dosyasını okuyup eski Kalisto projesini başlattı; hemen
  durdurup doğru ayarı ekledim. Ders: araç beklenmedik bir şey yaptığında önce durdur, sonra sebebini bul.

---

## Kendin dene (15 dakika)

İki ayrı terminalde:

```bash
.venv/Scripts/python -X utf8 -m internreader api
```

```bash
cd web && npm run dev
```

1. Tarayıcıda `http://localhost:4321` aç, "Bülteni dene"de İstanbul'u seç: önizleme nasıl değişti?
2. Kendi e-postanla kaydol (gerçek e-posta gitmez). `cikti/giden_eposta/` klasöründeki dosyayı aç, içindeki onay
   bağlantısını tarayıcıya yapıştır, onayla.
3. `.venv/Scripts/python -X utf8 -m internreader durum` → `aboneler` satırında ne yazıyor?

## Kendini sına

1. Onay bağlantısının kendisi yerine neden özetini saklıyoruz?
2. Onay neden bağlantıyı açınca değil, butona basınca oluyor?
3. Caddy neden `cikti/` klasörünün tamamını değil, yalnızca iki dosyayı dışarı açıyor?
