# Ücretsiz kurulum: Vercel + Neon + GitHub Actions + Brevo

Sunucu kiralamadan, kart vermeden canlıya çıkış. Her adım tek iş; bitirmeden sonrakine geçme.
Gizli değerleri (anahtar, parola, bağlantı adresi) **hiçbir yere yapıştırma**: yalnızca aşağıda söylenen kutulara.

| Parça | Nerede | Ne yapar |
|---|---|---|
| Site + abonelik API'si | Vercel (Hobby, ücretsiz) | `internreader.me`; `/api/*` sunucusuz Python fonksiyonu, uyumaz (~1 sn soğuk başlangıç) |
| Veritabanı | Neon (ücretsiz Postgres) | aboneler, ilanlar, firmalar (~5 MB; sınır 500 MB) |
| Her sabahki iş | GitHub Actions | tara → yayınla → bülten → bakım; site verisini depoya ekler, Vercel yeniden yayınlar |
| Gün içi ara tarama | GitHub Actions | 6 saatte bir yalnızca ilan sistemleri; yalnızca veri değiştiyse site yeniden yayınlanır; bülten yok |
| E-posta | Brevo (ücretsiz, günde 300) | onay e-postası, hoş geldin e-postası ve bülten |

Kendi sunucunda çalıştırmak istersen eski yol (Docker + Caddy) README'de duruyor; ikisi aynı kodu kullanır.

---

## 1. Kodu GitHub'a gönder
Proje klasöründe PowerShell:
```
git push
```

## 2. Neon: veritabanı (5 dk)
1. `neon.tech` → **Sign up** → **Continue with GitHub**.
2. Proje oluştur: ad `internreader`, Postgres sürümü varsayılan, bölge **AWS US East 2 (Ohio)** (GitHub Actions
   makineleri ve Vercel'in varsayılan bölgesi Amerika'nın doğusunda; veritabanı yanlarında olunca sorgular hızlı).
3. **Connect** düğmesi → **Connection pooling** açık olsun → bağlantı adresini kopyala
   (`postgresql://...-pooler...neon.tech/neondb?sslmode=require...`). Bu adres = `DATABASE_URL`.
   Başındaki `postgresql://` olduğu gibi kalabilir; kod sürücüyü kendisi ekler.

## 3. GitHub: gizli değerler (5 dk)
Depo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**. Şunları ekle:

| Ad | Değer |
|---|---|
| `DATABASE_URL` | Neon'dan kopyaladığın adres |
| `ANTHROPIC_API_KEY` | console.anthropic.com → API Keys → yeni anahtar (adı `internreader-github`) |
| `INTERNREADER_GIZLI_ANAHTAR` | uzun rastgele metin; üretmek için: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |

Bu üç değeri bir yere not etme; Vercel'e de aynılarını gireceğiz (adım 5), o zaman tekrar üret/kopyala.
Gizli anahtar değişirse eski "abonelikten çık" bağlantıları çalışmaz: bir kez üret, iki yere de aynısını yaz.

## 4. İlk çalıştırma (~30 dk, yapay zekâ ~0,15 $)
Depo → **Actions** → **Günlük çalışma** → **Run workflow** → **İlk kurulum** kutusunu işaretle → **Run workflow**.
Firma listesi içe aktarılır, keşif yapılır, ilanlar toplanır; bitince `web/public/veri/` depoya eklenir.
Kırmızı çarpı çıkarsa adıma tıkla, hata metnini oku (gizli değer eksikse ilk adım söyler).

## 5. Vercel: site + API (10 dk)
1. `vercel.com` → **Sign Up** → **Continue with GitHub** → plan: **Hobby**.
2. **Add New → Project** → `internreader` deposunu **Import** et.
3. Ayarlara dokunma (her şey `vercel.json`'da). **Environment Variables** bölümüne ekle:
   `DATABASE_URL`, `INTERNREADER_GIZLI_ANAHTAR` (GitHub'dakilerle aynı), `INTERNREADER_SITE_ADRESI` = `https://internreader.me`.
4. **Deploy**. Bitince verilen `...vercel.app` adresini aç: site görünmeli; `/api/saglik` → `{"durum":"ok"}`.

## 6. Alan adı: internreader.me → Vercel (10 dk + yayılma süresi)
1. Vercel → proje → **Settings → Domains** → `internreader.me` ekle (www yönlendirmesini de kabul et).
   Vercel hangi DNS kayıtlarını istediğini gösterir (genelde `A @ 76.76.21.21` ve `CNAME www cname.vercel-dns.com`).
2. Namecheap → **Domain List** → `internreader.me` → **Manage** → **Advanced DNS**:
   - GitHub Pages için eklenmiş kayıtları sil (`185.199.x.x` A kayıtları, `github.io` CNAME'i).
   - Vercel'in gösterdiği kayıtları ekle.
3. Vercel'de alan adının yanında yeşil tik çıkınca (birkaç dakika–birkaç saat) `https://internreader.me` hazır.

## 7. E-posta: iletişim adresi + Brevo (20 dk)
**İletişim adresi (KVKK ve "ilanımı kaldır" için):** Namecheap → `internreader.me` → **Manage** → **Redirect Email** →
`iletisim` → kendi Gmail'in. Sonra bana yaz: `web/src/ayarlar.ts`'e `iletisim@internreader.me` ve veri sorumlusu adını ekleyeceğim.

**Brevo (gönderim):**
1. `brevo.com` → ücretsiz hesap.
2. **Senders, Domains & Dedicated IPs → Domains → Add a domain** → `internreader.me` → Brevo'nun verdiği DNS kayıtlarını
   (Brevo kodu, DKIM, DMARC) Namecheap **Advanced DNS**'e ekle → Brevo'da **Verify**. Bu olmadan e-postalar spama düşer.
3. **SMTP & API → SMTP** → **Generate a new SMTP key**.
4. Aşağıdakileri hem GitHub gizli değerlerine (adım 3'teki yer) hem Vercel Environment Variables'a ekle:

| Ad | Değer |
|---|---|
| `SMTP_SUNUCU` | `smtp-relay.brevo.com` |
| `SMTP_KULLANICI` | Brevo SMTP sayfasındaki "Login" |
| `SMTP_PAROLA` | ürettiğin SMTP anahtarı |
| `EPOSTA_KIMDEN` | `InternReader <bulten@internreader.me>` |

Vercel'de değişken ekledikten sonra **Deployments → son dağıtım → Redeploy** (yeni değerler ancak böyle okunur).

## 8. Dene
Siteden kendi e-postanla abone ol → onay e-postası gelmeli (spam klasörüne de bak) → onayla.
Onayladığın anda hoş geldin e-postası gelir; bülten için Actions → Test bülteni → Run workflow (bölüm 11).

## 9. Herkese duyurmadan önce
- İŞKUR'dan yazılı görüş (Alo 170 ya da CİMER): "Yalnızca şirketlerin kendi ilan sayfalarına bağlantı veren, başvuru ve
  CV almayan, ücret almayan bir liste için özel istihdam bürosu izni gerekir mi?"
- İlan kaldırma talebi gelirse: yerelde `DATABASE_URL`'i Neon adresine ayarlayıp `python -m internreader firma-kapat "Firma"`.

## 10. Sabah saatini sağlama al: Vercel Cron (15 dk)
GitHub'ın zamanlaması gecikebiliyor: 30.10.2026'da 07:00 yerine 13:35'te çalıştı. Bu yüzden işi Vercel Cron başlatır;
GitHub'daki zamanlama yedek olarak kalır (Türkiye 09:37, iş o gün zaten bittiyse tarama yapmadan biter). Hobby planında
Vercel Cron 07:00–07:59 arasında herhangi bir anda çalışır; tarama da sürdüğü için site ve bülten sabah gelir, kesin saat
sözü vermiyoruz. Bu adımları yapmazsan sistem yine çalışır, yalnızca yedek saatte.

**a) GitHub'da token üret**
1. GitHub → sağ üstte profil resmi → **Settings → Developer settings → Personal access tokens → Fine-grained tokens →
   Generate new token**.
2. **Token name:** `internreader-sabah-isi`. **Expiration:** 1 yıl (takvime yenileme notu koy).
3. **Repository access:** Only select repositories → `bilalerg/internreader`.
4. **Permissions → Repository permissions → Actions: Read and write**. Başka izin verme.
5. **Generate token**, değeri kopyala (bir daha gösterilmez, başka yere yazma).

**b) Rastgele bir gizli değer üret**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**c) Vercel'e iki değişken ekle**
Vercel → proje → **Settings → Environment Variables** → Production için:
| Ad | Değer |
|---|---|
| `CRON_SECRET` | (b)'de ürettiğin değer. Vercel bunu Cron isteğine `Authorization: Bearer ...` olarak kendisi ekler |
| `GITHUB_TETIK_TOKENI` | (a)'da kopyaladığın token |

Depo adı farklıysa `GITHUB_DEPO` de ekle (varsayılan `bilalerg/internreader`).

**d) Yeniden yayınla ve dene**
1. Vercel → **Deployments → son dağıtım → Redeploy** (kod da push edilmiş olmalı; `vercel.json`'daki cron ancak böyle görünür).
2. **Settings → Cron Jobs** sayfasında `/api/cron/gunluk` görünmeli; yanındaki **Run** ile elle çalıştır.
3. GitHub → **Actions → Günlük çalışma**: birkaç saniye içinde `workflow_dispatch` ile yeni bir çalışma başlamalı.

Sorun çıkarsa ucu kendin dene (değeri kendi terminalinde yaz, kimseyle paylaşma):
```bash
curl -i -H "Authorization: Bearer CRON_SECRET_DEGERI" https://internreader.me/api/cron/gunluk
```
| Cevap | Anlamı | Ne yapmalı |
|---|---|---|
| 200 `tetiklendi` | Çalışıyor | Bir şey yapma |
| 401 | `CRON_SECRET` eksik ya da farklı | Vercel'deki değeri kontrol et, Redeploy |
| 503 `tetik_tokeni_yok` | `GITHUB_TETIK_TOKENI` tanımlı değil | Değişkeni ekle, Redeploy. Bu arada iş yedek saatte çalışır |
| 502 `github_reddetti` | Token geçersiz, süresi dolmuş ya da yetkisi yetmiyor | Token'ı yenile: Actions: Read and write, doğru depo |

Bir abone aynı gün iki bülten almaz: iş iki kez çalışsa da (tetikleme + yedek, elle çalıştırma) ikinci çalışma yalnızca
günlük e-posta sınırına takılıp alamayanlara gönderir.

## 11. Değişikliği nasıl hızlı denerim?
Sabahı beklemek zorunda değilsin.

**Bir kez yap:** GitHub → **Settings → Secrets and variables → Actions → New repository secret** → ad `TEST_EPOSTA`,
değer kendi e-posta adresin. Adres yalnızca burada durur; Actions kayıtlarında görünmez.

**Her denemede:**
1. `git push` (site ve API için Vercel ~2 dk içinde yeniden yayınlar).
2. GitHub → **Actions → Test bülteni → Run workflow** → `gunluk` (sabah bülteni) ya da `hos-geldin` (yeni aboneye giden e-posta).
3. ~1 dk sonra konu satırı `[TEST]` ile başlayan e-posta gelir.

Test e-postası Neon'daki hazır veriyi kullanır ve hiçbir kayıt yazmaz: istediğin kadar tekrarla, gerçek abonelerin bülteni
etkilenmez. Kayıtlı abone adresiysen senin tercihlerinle, değilsen tüm ilanlarla hazırlanır. İçindeki çıkış bağlantısına
tıklasan da aboneliğin silinmez.

**Site verisini tazelemek için:** Actions → **Günlük çalışma → Run workflow** (tarama ~30 dk sürebilir). Koruma yüzünden o gün
bülten almış aboneye ikinci bülten gitmez; yeni veriyi e-postada görmek için ardından Test bülteni'ni çalıştır.

**Yerelde, göndermeden:**
```bash
.venv/Scripts/python -m internreader bulten-dene ben@ornek.com --hos-geldin --gonderme
```
E-posta `cikti/test_bulten.html` dosyasına yazılır; tarayıcıda aç.

## Sınırlar ve bilinmesi gerekenler
- **Ani kalabalık:** site (Vercel CDN) ve API (sunucusuz) kendiliğinden ölçeklenir; veritabanı küçük kalır.
  **Darboğaz e-posta kotasıdır** (Brevo ücretsiz: günde 300). Kod bunu korur: günde en fazla 200 bülten
  (`INTERNREADER_GUNLUK_BULTEN_SINIRI`), 50 onay e-postası (`INTERNREADER_GUNLUK_ONAY_SINIRI`) ve 50 hoş geldin
  e-postası (`INTERNREADER_GUNLUK_HOS_GELDIN_SINIRI`). Sınır dolunca bülten alamayanlar ertesi gün ilk sırada; onay
  sınırı dolarsa form "yarın tekrar dene" der; hoş geldin sınırı dolarsa e-posta atlanır, ertesi sabah bülten kapatır. Art arda 5
  gönderim hatasında bülten durur (kota ya da SMTP sorunu). Aboneler ~200'ü geçince: Brevo ücretli plan ya da
  haftalık bülteni varsayılan yapmak; değerleri GitHub ve Vercel'de yükselt.
- **Ara tarama kotaları (30.10 ölçümü):** tek tarama ~36 sn + Actions kurulumu, ~2 dk. Neon: ayda ~3 CU-saat ek (kota 100 CU-saat;
  compute 0,25 CU'da kalırsa). Vercel: günde en fazla 4 ek dağıtım (sınır 100). Yapay zekâ tavanı çalıştırma başına 0,05 $;
  aylık 2 $ tavanı ortaktır, dolarsa sistem yapay zekâsız devam eder. Kariyer sayfaları günde bir taranır, artırılmadı.
- **Vercel Hobby ticari olmayan kullanım içindir.** Reklam/sponsor gelirse Pro plan (ayda 20 $) gerekir.
- **Yapay zekâ harcaması:** çalıştırma başına en fazla 0,50 $, ayda en fazla 2 $ (kod frenler). Kredi bitince sistem yapay
  zekâsız (yedek kurallarla) çalışmaya devam eder.
- **GitHub Actions** herkese açık depoda ücretsiz. Zamanlanmış işler bazen 5–15 dk gecikebilir.
- **Yedek:** Neon ücretsiz planı 7 günlük geri dönüş sağlar (Restore). Ayrıca yedek gerekmez.

## 12. Tıklama ölçümü ve firma araması

**Tıklamalar:** Ek kurulum gerekmez. Actions → Günlük çalışma → son çalışma → Summary → `tiklama_son_7_gun`. Denemek için Test bülteni'ni çalıştır, e-postadaki
"Başvur"a 30 saniyeden sonra tıkla, ilanın açıldığını gör; Test bülteni'ni bir kez daha çalıştırınca Summary'de `deneme` sayısı artmış olmalı.

**Firma araması (isteğe bağlı, ücretsiz):** serper.dev → kayıt → API anahtarı. GitHub → Settings → Secrets and variables → Actions → `SERPER_API_KEY`. Keşif iş akışı
her pazartesi listede olmayan firmaları ve web adresi eksik firmaları arar; anahtar yoksa bu adım atlanır.
