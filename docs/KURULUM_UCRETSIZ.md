# Ücretsiz kurulum: Vercel + Neon + GitHub Actions + Brevo

Sunucu kiralamadan, kart vermeden canlıya çıkış. Her adım tek iş; bitirmeden sonrakine geçme.
Gizli değerleri (anahtar, parola, bağlantı adresi) **hiçbir yere yapıştırma**: yalnızca aşağıda söylenen kutulara.

| Parça | Nerede | Ne yapar |
|---|---|---|
| Site + abonelik API'si | Vercel (Hobby, ücretsiz) | `internreader.me`; `/api/*` sunucusuz Python fonksiyonu, uyumaz (~1 sn soğuk başlangıç) |
| Veritabanı | Neon (ücretsiz Postgres) | aboneler, ilanlar, firmalar (~5 MB; sınır 500 MB) |
| Her sabahki iş | GitHub Actions | tara → yayınla → bülten → bakım; site verisini depoya ekler, Vercel yeniden yayınlar |
| E-posta | Brevo (ücretsiz, günde 300) | onay e-postası ve bülten |

Kendi sunucunda çalıştırmak istersen eski yol (Docker + Caddy) README'de duruyor; ikisi aynı kodu kullanır.

---

## 1. Kodu GitHub'a gönder
Proje klasöründe PowerShell:
```
git push
```

## 2. Neon: veritabanı (5 dk)
1. `neon.tech` → **Sign up** → **Continue with GitHub**.
2. Proje oluştur: ad `internreader`, Postgres sürümü varsayılan, bölge **AWS Europe Central 1 (Frankfurt)**.
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
Ertesi sabah 07:00'deki çalışmadan sonra bülten gelir; hemen denemek için Actions → Günlük çalışma → Run workflow.

## 9. Herkese duyurmadan önce
- İŞKUR'dan yazılı görüş (Alo 170 ya da CİMER): "Yalnızca şirketlerin kendi ilan sayfalarına bağlantı veren, başvuru ve
  CV almayan, ücret almayan bir liste için özel istihdam bürosu izni gerekir mi?"
- İlan kaldırma talebi gelirse: yerelde `DATABASE_URL`'i Neon adresine ayarlayıp `python -m internreader firma-kapat "Firma"`.

## Sınırlar ve bilinmesi gerekenler
- **Vercel Hobby ticari olmayan kullanım içindir.** Reklam/sponsor gelirse Pro plan (ayda 20 $) gerekir.
- **Yapay zekâ harcaması:** çalıştırma başına en fazla 0,50 $, ayda en fazla 2 $ (kod frenler). Kredi bitince sistem yapay
  zekâsız (yedek kurallarla) çalışmaya devam eder.
- **GitHub Actions** herkese açık depoda ücretsiz. Zamanlanmış işler bazen 5–15 dk gecikebilir.
- **Yedek:** Neon ücretsiz planı 7 günlük geri dönüş sağlar (Restore). Ayrıca yedek gerekmez.
