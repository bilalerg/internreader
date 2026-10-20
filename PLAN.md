# InternReader — plan

## Güncel durum (19.10.2026, v0.3) — önce bunu oku

Aşağıdaki eski bölümler tarih sırasıyla duruyor; çeliştikleri yerde bu bölüm geçerlidir.

**Mimari (modüler, 18.10'da yeniden yazıldı):**
kaynaklar (ATS + kariyer sayfası) → yapay zekâ (sayfa okuma, sınıflandırma) → işleme (konum, tekilleştirme)
→ depo (SQLite yerelde / Postgres sunucuda) → yayın (README tablosu, JSON, WhatsApp özeti).
Kod yapısı ve komutlar için `README.md`.

**İlk gerçek çalıştırma (18.10, 17:05):**
- 1.300 firma → 41 ATS firması (1.003 ilan) + 237 kariyer sayfası (39'u yapay zekâyla okundu, 157'si önbellekten).
- 485 ilan sınıflandı. Maliyet: sayfa okuma 0,022 $ + sınıflandırma 0,035 $ = **0,057 $**.
- Öğrenciye uygun yazılım/AI/veri ilanı: **20**. Kapsam darboğazı sürüyor (31.10 kontrol noktası geçerli).

**İkinci çalıştırma (18.10, 18:03; keşif + tohum listesi sonrası):**
- 272 kariyer sayfası (önce 237), 42 ATS firması. 102 sayfa yapay zekâyla okundu, 155'i önbellekten.
- 162 yeni ilan sınıflandı. Maliyet 0,10 $ (sayfa okuma 0,090 $ + sınıflandırma 0,012 $). Günün toplamı **0,159 $**.
- Yayın: **23 açık öğrenci ilanı**; ilk WhatsApp özeti 20 ilan (yayın tarihi 45 günden eski 3 ilan özete girmedi).

**Ölçüp ertelenen karar — sayfa metni kalıp temizliği:** Sayfa okumada mesajın çoğu sayfa metni (menü, alt bilgi).
Bağlantı listesini kısaltmak yalnızca %13 kazandırdı. Metinden <nav>/<footer> atmak daha çok kazandırır ama bütün
sayfaların özeti değişir (tek seferlik ~0,09 $ yeniden okuma) ve pozisyon kaçırma riski var. **Karar:** birkaç günlük
gerçek "değişen sayfa" oranını gör (`durum` → son_tarama.sayfa_durumlari), günde 30'dan fazla sayfa değişiyorsa yap.

**Veri kalitesi notları:** Teknopark listelerinden gelen firmaların adı resmî unvan (ör. "Nova Spark X Teknoloji A.Ş."
= Patika Global). Yayında marka adı göstermek için firmalar tablosuna `gorunen_ad` alanı eklenebilir.

**18.10'da düzeltilen hatalar:**
- Bozuk bir bağlantı (`http://[getaquotelink]`) tüm taramayı çökertiyordu → firma başına hata yalıtımı.
- Kesilen yapay zekâ cevabının maliyeti bütçeye sayılmıyordu → kullanım her durumda kaydediliyor.
- Kapanan ilanlar zaman damgasıyla bulunuyordu (Windows saat çözünürlüğünde kaçırıyordu) → küme farkı.
- Keşif, site cevap vermeyince bilinen kariyer sayfasını siliyordu; PNG/CSS dosyalarını kariyer sayfası sanıyordu.
- 8 sn bağlantı sınırı, WARP/DDoS korumalı Türk sunucularında (bağlantı ~20 sn) 28 siteyi "kapalı" saydırdı → 25 sn.
- Sınıflandırıcıya açıklamanın ilk 400 karakteri gidiyordu (şirket tanıtımı) → seviye cümleleri seçiliyor.
- Sunucu karakter kodlamasını bildirmeyince sayfa Latin-1 sanılıyordu; sayfaların ~%5'inde Türkçe bozuktu → başlık →
  <meta charset> → UTF-8 → cp1254 sırası.
- Veriyi damla damla gönderen bir sunucu keşfi 5+ dakika kilitledi → gövde parça parça okunuyor, toplam süre ve boyut
  sınırı var. Keşif sonuçları 100 firmada bir yazılıyor (yarıda kesilse de iş kaybolmuyor).
- Sitede bağlantısı olan ama API'si 404 veren ATS panosu (Complizen) keşif ↔ tarama döngüsü yaratıyordu → keşif
  bulduğu panoyu bir kez deneyip doğruluyor.

**Maliyet güvenceleri:** çalıştırma tavanı (0,50 $), aylık tavan (2 $), sayfa önbelleği, tek seferlik
sınıflandırma, servis sigortası (3 ardışık hata → kapat). Kalan kredi ~5,75 $ (18.10 akşam, tahmini).

**18.10 akşam — rakipler ve karar:**
- Doğrudan rakipler bulundu (ikisi de Ağu–Eyl 2026'da açılmış, arama motorlarında henüz görünmüyor):
  **StajımVar** (tüm bölümler, 99 kaynak, işveren paneli, YZ yok, e-posta yok) ve **StartupJobs Türkiye** (Çek şirketi;
  21 girişim, tüm seviyeler, haftalık e-posta, 139 €/ilan). Kısmi: Fırsat Atlası, envantermedya, Masqot, Kariyer.net Kopilot.
- **Karar:** dar odakla devam. Konum: "Yazılım ve yapay zekâ stajları, şirketlerin kendi sayfalarından yapay zekâyla
  okunup her sabah e-postana." İşveren paneli / CV üretici / tüm bölümler yapılmaz.
- **30.11.2026 karar günü:** 100 onaylı e-posta abonesi yoksa yeni geliştirme durur.

**Site (18.10):** Astro + React adaları; Türkiye haritası simülasyonu, 4 adımlı "nasıl çalışır", gerçek verili bülten
önizlemesi + çift onaylı kayıt (FastAPI), KVKK, onay/çıkış sayfaları. Caddy + günlük site derleme ile yayına hazır.

**Arka uç ve yapay zekâ (18–19.10 gece, v0.3):**
- Veritabanı: alembic göçleri (`internreader/goc/`), her açılışta otomatik `upgrade head`; Postgres'te danışma kilidi
  (API ve sabah işi aynı anda açılsa da göç bir kez çalışır). `depo.py` konulara bölündü (`internreader/depo/`).
- Bülten: tercih eşleşmesi, gönderilen ilanları hatırlama (aynı ilan iki kez gitmez), günlük/haftalık, HTML + düz metin,
  RFC 8058 tek tıkla çıkış. SMTP yoksa e-postalar `cikti/giden_eposta/`'ya yazılır. Geliştirme anahtarıyla gerçek
  gönderim reddedilir (çıkış bağlantıları bozuk olurdu).
- Bakım: onaylanmamış kayıtlar (72 saat), 180 günden eski gönderim kayıtları, 60 günden eski kapalı ilan metinleri silinir.
- Yapay zekâ:
  - **Ayrıntılar:** öğrenci ilanlarından özet, son başvuru, kimler başvurabilir, çalışma modeli, ücret, teknolojiler.
    Uydurmaya karşı kod denetimi. İlk gerçek çalıştırma: 17 ilan, 0,0067 $; hiç uydurma teknoloji yok.
  - **İmza:** yeniden yayınlanan ilan (aynı firma + başlık + açıklama) yapay zekâya gitmez.
  - **Toplu mod:** `INTERNREADER_YZ_TOPLU=1` → Message Batches, yarı fiyat; bütçe tahminle kırpılır, 45 dk'da
    bitmezse iptal edilip normal yoldan devam edilir. Gerçek API'ye karşı henüz denenmedi.
  - **Değerlendirme:** 30 elle etiketli ilan; ilk ölçüm seviye %96, rol %100, öğrenciye uygun isabet/kapsama %100
    (0,0015 $). Set kolay; 50'ye tamamlanırken zor örnekler eklenecek.
- Sağlık: `/api/saglik` veritabanını yoklar (yoksa 503); Docker sağlık kontrolü buna bağlı.

**Sıradaki adımlar:**
1. Kullanıcı: GitHub reposu (`internreader`, public) → ilk commit; CI otomatik koşar.
2. Kullanıcı: Student Pack → DigitalOcean; sunucuda `docker compose` + `ops/crontab`.
3. Firma kapsamı: öğrenci alan büyük firmalar (tohum listesi `veri/tohum_firmalar.csv`, 75 firma) — bankalar ve
   e-ticaret devleri kendi portallarını (SuccessFactors vb.) kullanıyor; bunlar için yeni toplayıcılar gerekebilir.
4. WhatsApp kanalı açılışı (günlük özet `cikti/whatsapp_*.txt`, elle paylaşım).
5. ~~Alembic~~ (19.10'da yapıldı).
6. Değerlendirme seti: 30 → 50 ilan (Bilal etiketleri gözden geçirir, zor örnekler ekler).
7. E-posta sağlayıcısı + alan adı DNS'i (SPF, DKIM, DMARC) → gerçek bülten gönderimi.
8. Sunucuda bir hafta toplu modu aç, `durum` çıktısında maliyeti normal modla kıyasla.

---

## Geçmiş (eski çalışma adı: StajRadar)

Başlangıç: 16.10.2026

> **16.10 akşamki araştırmanın sonucu (ayrıntılar `ARASTIRMA.md` dosyasında):**
> - Ana dağıtım kanalı Telegram yerine **WhatsApp kanalı + GitHub README** oldu. Gerekçe: Türkiye'de WhatsApp kullanımı %90, Telegram %13,8.
> - Firma listesi **öğrenci alan firmalar** odağında genişletilecek. Mevcut listeden yalnızca yaklaşık 20 öğrenci fırsatı çıkıyor.
> - Yeni kaynaklar: Workday ve Peoplise toplayıcıları; izin alınarak üniversite kariyer panoları ve VC portföy panoları.
> - "Staj Radar" adı başka bir projede kullanılıyor. Aday isim: **staj.dev**.
> - 31.10 kontrol noktası: haftada 30'dan az yeni öğrenci fırsatı çıkıyorsa kaynak stratejisi değişecek.
> - Aşağıdaki plan metninde Telegram geçen yerler bu karara göre okunmalı.

## Ne yapıyor?
Türkiye'deki yazılım, yapay zekâ ve veri **staj / junior / yarı zamanlı** ilanlarını, özellikle teknoloji girişimlerinin kendi kariyer sayfalarındaki ilanları, tek bir yerde topluyor. Yapay zekâ her ilanı okuyup "öğrenciye uygun mu?" sorusuna cevap veriyor. Yeni ilanlar her gün bir web sayfasına ve bir Telegram kanalına düşüyor.

## Amaç
Para kazanmak değil, **aktif kullanıcısı olan bir yapay zekâ projesi** yapmak. Proje CV'ye girecek, mülakatta anlatılacak ve Bilal'in kendi iş aramasında da kullanılacak.

## Kapsam (1. sürüm)
- Yer: Türkiye. Öncelik İstanbul, uzaktan çalışma ilanları da dahil.
- Roller: yazılım, AI/ML, veri, backend, frontend, mobil, gömülü, DevOps.
- Türler: staj, uzun dönem staj, yarı zamanlı, junior, yeni mezun.
- Kaynaklar:
  1. Hazır ilan sistemlerinin herkese açık bağlantıları: Greenhouse, Lever, Ashby, Workable, Recruitee, SmartRecruiters, Teamtailor.
  2. Seçilmiş firmaların kendi kariyer sayfaları.
- Başlangıç firma listesi: takip Excel'i (~150), Dijitalpark (459), site taraması (147) ve ilan sistemi bilinen 25 firma.

## Kurallar
- LinkedIn ve kariyer.net'ten veri çekmiyoruz (kullanım şartları yasaklıyor).
- Sitelerin robots.txt kurallarına uyuyoruz. Siteleri günde en fazla 2 kez tarıyoruz.
- İlan metninin tamamını kopyalamıyoruz. Kısa bir özet verip orijinal ilana bağlantı veriyoruz.
- 1. sürümde CV yükleme yok (KVKK). CV eşleştirme sonra, açık onay ve silme seçeneğiyle gelecek.
- API anahtarları koda yazılmaz, yalnızca GitHub Secrets'ta durur.

## Nasıl çalışıyor?
```
firmalar.csv ──► toplayıcılar ──► yeni ilan mı? ──► yapay zekâ ayıklama ──► veri/ilanlar.json
                (her gün 2 kez)   (daha önce          (yalnızca yeni            │
                                   görüldüyse atla)    ilanlar)                 ├─► web sayfası (filtreli)
                                                                                ├─► Telegram kanalı
                                                                                └─► Bilal'in takip Excel'i
```

Yapay zekânın her ilandan çıkaracağı alanlar:
- tür (staj / uzun dönem staj / yarı zamanlı / junior / yeni mezun)
- alan (AI-ML / backend / frontend / mobil / veri / gömülü / oyun / DevOps)
- şehir, yaka, uzaktan / hibrit / ofis
- mezuniyet şartı (ör. "en geç Haziran 2027")
- ücretli mi
- son başvuru tarihi
- ilan dili (TR / EN)
- **yapay zekâ kullanımı** (16.10'da eklendi): AI/LLM işin özünde mi / artı mı / yok mu. "AI kullanan yazılımcı" filtresi bu alana göre çalışacak.
- 2 cümlelik Türkçe özet
- öğrenciye uygun mu + tek cümle gerekçe

**Doğruluk ölçümü (değerlendirme seti):** 50 ilanı Bilal elle etiketler (doğru cevaplar). Yapay zekânın çıkardığı alanlar bu cevaplarla karşılaştırılır ve doğruluk yüzdesi ölçülür. Örnek hedef: mezuniyet şartı alanında %90+. Model ya da prompt her değiştiğinde ölçüm tekrarlanır. "API bağlamak" ile "AI mühendisliği" arasındaki fark bu adım; mülakatta anlatılacak.

## İlk ölçüm (16.10.2026)
- 1.299 firmadan yalnızca 40'ı Lever, Greenhouse, Ashby gibi hazır ilan sistemleri (ATS) kullanıyor. Keşif betiği 932 siteyi taradı ve sadece 2 yeni ATS buldu.
- Bu 40 firmadan 1.000 ilan geldi; Türkiye'de ya da uzaktan olan 182 ilan var. Kaba filtreden 7 öğrenci ilanı geçti.
- 392 firmanın kendi kariyer sayfası bulundu. 154 siteye erişilemedi.
- **Sonuç:** Türk firmalarının çoğu ATS kullanmıyor. Asıl kapsam kariyer sayfalarında.
- **18.10 akşam — rakipler ve karar:**
- Doğrudan rakipler bulundu (ikisi de Ağu–Eyl 2026'da açılmış, arama motorlarında henüz görünmüyor):
  **StajımVar** (tüm bölümler, 99 kaynak, işveren paneli, YZ yok, e-posta yok) ve **StartupJobs Türkiye** (Çek şirketi;
  21 girişim, tüm seviyeler, haftalık e-posta, 139 €/ilan). Kısmi: Fırsat Atlası, envantermedya, Masqot, Kariyer.net Kopilot.
- **Karar:** dar odakla devam. Konum: "Yazılım ve yapay zekâ stajları, şirketlerin kendi sayfalarından yapay zekâyla
  okunup her sabah e-postana." İşveren paneli / CV üretici / tüm bölümler yapılmaz.
- **30.11.2026 karar günü:** 100 onaylı e-posta abonesi yoksa yeni geliştirme durur.

**Site (18.10):** Astro + React adaları; Türkiye haritası simülasyonu, 4 adımlı "nasıl çalışır", gerçek verili bülten
önizlemesi + çift onaylı kayıt (FastAPI), KVKK, onay/çıkış sayfaları. Caddy + günlük site derleme ile yayına hazır.

**Sıradaki adımlar:**
  1. Workday ve Peoplise (Türk ATS) toplayıcıları.
  2. **Kariyer sayfası okuyucu:** yapay zekâ sayfayı okuyup açık pozisyonları çıkaracak. Sayfa değişmediyse yapay zekâ tekrar çağrılmayacak (içerik hash'i karşılaştırması).
  3. Teknopark ilan panoları.
- Ürünün yapay zekâ ağırlığı bu adımla artıyor.

## HiringCafe'den alınan dersler (16.10)
- **Başlangıç bir tabloydu.** Ali Mir 2022'deki işten çıkarmalardan sonra işsiz kalan arkadaşları için 10.000 bulunması zor girişim ilanını bir tabloya topladı. Tablo viral oldu, crawler sonra geldi. Pitt CSC'nin GitHub listesi de bir README tablosu.
- **Kopyalanacaklar:**
  - İlanları doğrudan şirket kariyer sayfalarından çekmek.
  - AI ile ilan metninden yapılandırılmış filtreler çıkarmak.
  - Ücretli öne çıkarma ve sahte ilan olmaması.
  - "Hayalet ilan" temizliği: aylardır açık kalan ilanlar. Örnek: Dream Games'in 2022 tarihli ilanları hâlâ açık görünüyor.
  - Büyümeyi Reddit ve tavsiye ile sağlamak.
- **Kopyalanmayacaklar:** Küresel ölçek (5,7 M ilan) ve AI "talent agent". Onun yerine Türkiye'ye özel alanlar: zorunlu staj, sigorta, mezuniyet şartı, yaka.
- **Öneri:** İlk yayın biçimi, her gün otomatik güncellenen bir **GitHub README tablosu** + Telegram olsun. Web sitesi sonra gelsin. Daha hızlı yayına çıkar, sıfır maliyetli, ve geliştirici öğrenciler GitHub'da yıldız verip paylaşır.

## AI ajanları ve StajRadar (17.10 gece)
- Soru: İnsanlar CV'lerini Claude'a verip API bağlantılarıyla iş arattırıyor, hatta otomatik başvurtuyor. StajRadar'a yine de gerek var mı?
- Cevap: Ajanların da bir veri kaynağına ihtiyacı var. Genel ajanlar LinkedIn, Indeed ve Google'a bakıyor. Türk girişimlerinin kariyer sayfalarındaki ilanlar bu kaynakların çoğunda görünmüyor (dağınıklık testi: 8 ilanın 8'i şirket sitesinde var, Kariyer.net ve Youthall'da neredeyse hiçbiri yok). Ayrıca LinkedIn ajanları engelliyor.
- **Konumlanma:** StajRadar = Türkiye'deki staj/junior ilanları için güncel ve doğrulanmış **veri katmanı**.
- **Planlanan çıktı:** Herkese açık bir JSON listesi ve bir **MCP sunucusu**. İnsanların kendi Claude ajanları ilanları buradan sorgulayabilecek. Ajanlar rakip değil, bir dağıtım kanalı olacak. MCP sunucusu aynı zamanda CV'ye güçlü bir AI becerisi olarak girer.
- Otomatik başvurmak hedef değil. Toplu AI başvuruları işe alımcıları boğuyor; isme özel başvuru ve tavsiye daha iyi çalışıyor.

## Kaynak genişletme (16.10 kararı)
- **LinkedIn, Kariyer.net, Youthall: veri çekilmeyecek.**
  - LinkedIn'in herkese açık ilan arama API'si yok; erişim yalnızca partnerlere ve yeni partner alınmıyor. Kullanım şartları kazımayı yasaklıyor ve ilk denemelerimizde bot engeline takıldık.
  - Kariyer.net ve Youthall'un herkese açık API'si bulunamadı.
- **Yasal yollar:**
  1. **Jooble API:** Ücretsiz anahtar veriyor (yayıncılar için); anahtar kelime + konum ile arama yapılıyor. Dönen ilanlarda başlık, firma, konum, kısa özet ve Jooble üzerinden geçen bir link var. Türkiye kapsamı henüz doğrulanmadı.
  2. **Careerjet API:** Partner hesabıyla kullanılıyor; `tr_TR` dili destekleniyor (üçüncü taraf kaynağa göre).
  3. **Derin linkler:** "Bu aramayı LinkedIn'de / Kariyer.net'te aç" butonları. Veri çekme yok, yalnızca hazır bir arama bağlantısı.
  4. **Kullanıcı gelince:** Youthall ve Techcareer'e resmi veri akışı (feed) için ortaklık teklifi.
- **Not:** Jooble ve Careerjet'ten yalnızca kısa özet geliyor. Yönlendirdikleri orijinal sayfayı çekmek, o siteden (ör. Kariyer.net) veri çekmek anlamına gelir; bunu yapmıyoruz. Bu yüzden bu kaynaklarda AI'nın ayıklayabileceği bilgi sınırlı kalacak.
- **2. hafta:** Kullanıcı Jooble ve Careerjet anahtarlarını alacak; İstanbul'daki yazılım staj/junior ilanlarının kapsamı test edilecek.

## Benzerleri (16.10.2026 kontrolü)
- **Yurt dışı:**
  - SimplifyJobs / Pitt CSC "Summer2027-Internships" GitHub listesi: ~45 bin yıldız, 2.064 ilan, her gün güncelleniyor. Bir üniversitenin bilgisayar kulübü yürütüyor.
  - HiringCafe: şirket kariyer sayfalarını AI ile tarıyor. Kendi beyanına göre aylık 2 milyon aktif kullanıcı, reklamsız; büyük kısmı Reddit ve tavsiye ile gelmiş. 6,8 M$ yatırım almış.
- **Türkiye:**
  - Youthall, Techcareer, Kariyer.net ve Anbean genel platformlar.
  - "Türkiye Kariyer Radarı" (GitHub, 03.10.2026, 0 yıldız): bilgisayarda yerel çalışan bir panel; kariyer.net, LinkedIn ve Youthall'u tarıyor; İK ve iletişim ilanlarına odaklı; AI yok.
  - Kodilan (eski yazılımcı ilan sitesi): kapanmış, alan adı şimdi alakasız bir sitede.
- **Türkiye, ikinci ve daha geniş kontrol (16.10 akşam):** Öğrenciye staj ilanı sunan çok sayıda platform var:
  - Youthall (Stajim.net de artık Youthall'a yönleniyor)
  - Kampusum.co ("500+ şirket")
  - Toptalent
  - Anbean
  - Stajyeri.com.tr
  - İŞKUR Staj Portalı
  - Coderspace (teknoloji yetenekleri platformu)
  - Techcareer
  - Kariyer.net, eleman.net, Yenibiriş, Indeed

  Bunların hepsi **işverenin ilan girdiği** platformlar. Şirket sitelerinden ve ATS'lerden ilanı kendisi toplayıp AI ile "öğrenciye uygun mu?" diye ayıklayan bir örnek bulunamadı. Youthall'daki AI özelliği (2023) CV geri bildirimi ve profil yazımı; ilan eşleştirme değil. Küçük Telegram, LinkedIn veya Instagram paylaşım hesapları muhtemelen var ama aramalarda çıkmadı. %100 emin olunamaz.
- **Üçüncü kontrol (16.10 akşam, GitHub):**
  - **`yusflhan-a11y/staj-radar`** "Staj Radar":
    - Aynı isim. 04.10.2026'da açılmış, son güncelleme 10.10, 0 yıldız.
    - Sadece arka uç (backend), yayında bir ürün yok.
    - Youthall, Kariyer.net ve LinkedIn'i Playwright ile kazıyor; bot korumasını aşmak için "stealth" eklentisi kullanıyor (kullanım şartlarına aykırı).
    - Bütün bölümler için.
    - **→ İsmi değiştirmemiz gerekiyor.**
  - **GDG on Campus İstanbul Üniversitesi "İş İlanları ve Kariyer İmkanları":**
    - Kulübün WhatsApp grubunda paylaşılan staj ilanlarını elle topladığı bir README.
    - Biçimi bizim AI'nın çıkaracağı alanlarla neredeyse aynı: hedef sınıf, arananlar, lokasyon, tarih, link.
    - 28.02–17.03.2026 arasında güncellenmiş, sonra bırakılmış. 5 yıldız.
    - **→ Talep var; ama elle tutulan liste 3 haftada ölüyor. Otomasyonun gerekçesi bu.**
    - **→ Dağıtım ortağı adayı:** GDG on Campus kulüpleri birçok üniversitede var ve kariyer WhatsApp grupları var.
- **Dağınıklık testi (1. hafta; kullanıcının düzeltmesiyle güncellendi):** Değer yalnızca "başka yerde olmayan ilan" değil; ilanlar platformlar arasında dağınık, ve hepsini tek yerde toplamak başlı başına değer. Test şöyle yapılacak:
  1. Farklı kaynaklardan 30 gerçek öğrenci ilanı al.
  2. Her ilanın nerelerde göründüğünü tabloya yaz: şirket sitesi, Youthall, Kariyer.net, LinkedIn, Techcareer.
  3. İki şeyi ölç: (a) Tek bir platform ilanların yüzde kaçını kapsıyor? (b) Biz yasal kaynaklarla (şirket siteleri, ATS, Jooble/Careerjet) yüzde kaçını yakalayabiliyoruz?

  Hiçbir platform hepsini kapsamıyorsa toplama değeri kanıtlanmış olur.
- **Ders:** Bu tür siteleri kod değil, bakımın bırakılması öldürüyor. Düzenli güncelleme ve kitle asıl farkı yaratıyor.

## Altyapı kararı (17.10 gece): VPS
Kullanıcının isteği: "Free tier'lar yerine baştan VPS'te sağlam kuralım, ileride altyapıyı değiştirmeyelim."
- **Sunucu:** GitHub Student Developer Pack ile DigitalOcean'ın 1 yıllık 200 $ kredisi (Okan öğrenci e-postasıyla başvurulacak). Kredi bitince Hetzner'a (~4–6,5 €/ay) ya da DigitalOcean'ın ücretli planına geçilecek.
- **Alan adı:** Student Pack'teki Name.com'un 1 yıllık ücretsiz alan adı (.dev/.app vb.). İsim seçildikten sonra.
- **Yapı (Docker Compose; sağlayıcı değişse de mimari değişmez):**
  - `postgres`: veritabanı.
  - `worker`: toplayıcılar + AI ayıklama; günde 2 kez zamanlanmış çalışır.
  - `api`: FastAPI; site için JSON uç noktası + MCP sunucusu.
  - `caddy`: ters vekil sunucu (reverse proxy) + otomatik HTTPS.
- Önde Cloudflare (ücretsiz): DNS, önbellek ve DDoS koruması. Trafik ani artarsa sunucu çökmez.
- **Yedek:** Her gün `pg_dump` ile sunucu dışına yedek alınacak.
- **İzleme:** Ücretsiz bir uptime servisi.
- **Güvenlik:** Yalnızca SSH anahtarıyla giriş, root girişi kapalı, ufw güvenlik duvarı, otomatik güvenlik güncellemeleri, gizli bilgiler `.env` dosyasında (repoya girmez).
- **GitHub:** CI ve deploy için Actions (SSH ile). README tablosunu sunucu otomatik günceller.
- Not: Aşağıdaki "GitHub Actions + Pages" satırları bu kararla geçersiz. GitHub artık yalnızca kodun, CI'ın ve README vitrininin yeri.

## Nerede çalışıyor? (eski plan, 16.10)
| Parça | Yer | Ücret |
|---|---|---|
| Kod | GitHub, herkese açık repo (github.com/bilalerg) | Ücretsiz |
| Günlük çalışma | GitHub Actions, zamanlanmış görev | Herkese açık repoda ücretsiz |
| Web sayfası | GitHub Pages | Ücretsiz |
| Bildirim | Telegram kanalı + bot | Ücretsiz |
| Yapay zekâ | Gemini Flash ya da Claude Haiku | Aylık ~1–5 $ |
| Ziyaret ölçümü | GoatCounter (çerezsiz) | Ücretsiz |

## Klasör yapısı
Güncel yapı `README.md` → "Kod yapısı" bölümünde.

## Kim ne yapıyor?
- **Claude:** Kodu adım adım yazar ve her parçayı sade dille anlatır.
- **Bilal:**
  - Her adımı kendisi çalıştırır.
  - Her adımın sonunda "bu parça ne yapıyor?" sorusunu kendi cümlesiyle cevaplar (mülakat hazırlığı).
  - Kararları verir.
  - Hesapları açar: GitHub repo, Telegram kanal ve bot, yapay zekâ API anahtarı.

## Takvim
| Tarih | Ne |
|---|---|
| 16.10 Cuma akşam | Plan + firma listelerini birleştirme |
| 17.10 Cumartesi | GitHub reposu; Greenhouse, Lever ve Ashby toplayıcıları; ilanlar konsolda listeleniyor |
| 18.10 Pazar | Yapay zekâ ayıklamanın ilk sürümü |
| 19–23.10 | Günlük yeni ilan listesi. **Yalnızca Bilal kullanıyor**, başvurularını buradan yapıyor |
| 24–31.10 | Web sayfası + Telegram + otomatik çalışma; bilgisayar topluluğuna beta duyurusu (5–10 kişiden geri bildirim) |
| Kasım | Kariyer sayfası toplayıcıları, CV eşleştirme, bildirimler; Reddit (r/CodingTR), Ekşi ve LinkedIn duyurusu |
| Aralık sonu | Ara kontrol: 100 abonenin altındaysa paylaşım yöntemini değiştir |
| Ocak 2027 sonu | Hedef: 500 Telegram abonesi ya da haftada 100 aktif kullanıcı |

## Ölçüm
- Telegram abone sayısı
- Haftalık ziyaretçi (GoatCounter)
- İlana tıklama sayısı

CV satırı: *"Built StajRadar: AI-powered internship aggregator for Turkish tech students — N weekly active users."*
