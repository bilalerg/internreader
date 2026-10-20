# InternReader (eski çalışma adı: StajRadar): ön araştırma raporu

Tarih: 16.10.2026 (Cuma akşamı)
Yöntem:
- Web araması (25+ sorgu)
- GitHub API taraması
- Google Play araması
- 1.299 firmalık listede ATS testi
- 392 kariyer sayfasında kapsam testi
- 8 gerçek ilanla dağınıklık testi

Yasal bölüm hukuki danışmanlık değildir.

---

## 1. Kısa sonuç

**Devam edilmeli, ama dört değişiklikle:**

1. **Dağıtım WhatsApp ve Instagram ağırlıklı olmalı, Telegram değil.** Türkiye'de internet kullanıcılarının %90'ı WhatsApp'ı, %71'i Instagram'ı kullanıyor; Telegram'ı kullananlar yalnızca %13,8.
2. **Firma listesi "öğrenci alan firmalar" odağıyla yeniden kurulmalı.** Mevcut listeden şu an yalnızca yaklaşık 20 öğrenci fırsatı çıkıyor. Bu, ürün için yetersiz.
3. **Yeni kaynaklar eklenmeli:**
   - Üniversite kariyer merkezi panoları (ODTÜ KPM, Boğaziçi Kariyer Merkezi vb.). İzin istenerek.
   - Yatırımcı (VC) portföy iş panoları.
   - Jooble ve Careerjet API'leri.
4. **İsim değişmeli.** "Staj Radar" adlı bir GitHub projesi 04.10.2026'da açılmış.

Fikrin özü sağlam:
- İlanlar gerçekten dağınık.
- Hiçbir platform hepsini göstermiyor.
- Türkiye'de otomatik toplayıp AI ile ayıklayan, bakımı süren bir ürün bulunamadı.
- Elle tutulan listeler birkaç haftada ölüyor.

---

## 2. Rakipler

### Türkiye: işverenin ilan girdiği platformlar
| Platform | Not |
|---|---|
| Youthall | En büyüğü; Stajim.net'i de bünyesine katmış. Android uygulaması 10 bin+ indirme, puanı 3,2. AI özelliği CV geri bildirimi; ilan eşleştirme değil. |
| Kariyer.net, İşin Olsun | Genel iş ilanı siteleri. İşin Olsun 10 milyon+ indirme. |
| Techcareer, Coderspace | Teknoloji odaklı. |
| Kampusum, Toptalent, Anbean | Öğrenci kariyer platformları. |
| Stajyeri.com.tr, Staj Bank, CVyolla, Unisbul | Küçük staj siteleri. |
| İŞKUR Staj Portalı | Devlet portalı. |
| Uygulamalar: Stajyerim, Stajnet, Staj Bul | Sırasıyla 500+, 100+ ve 10+ indirme. Hepsi iki taraflı pazar yeri. |

Bu platformların hepsinde ilanı işveren giriyor. Şirket ilan vermezse ilan orada görünmüyor.

### Türkiye: benzer deneme
| Proje | Durum |
|---|---|
| `yusflhan-a11y/staj-radar` (GitHub) | 04.10.2026'da açılmış, 0 yıldız. Sadece arka uç. Youthall, Kariyer.net ve LinkedIn'i Playwright + stealth ile kazıyor (kullanım şartlarına aykırı). **Aynı isim.** |
| "Türkiye Kariyer Radarı" (GitHub) | 03.10.2026'da açılmış, 0 yıldız. Bilgisayarda yerel çalışan bir panel. İK ve iletişim ilanlarına odaklı, AI yok. |
| GDG on Campus İstanbul Üniversitesi README | WhatsApp grubunda paylaşılan ilanları elle derliyor. 28.02–17.03.2026 arasında güncellenmiş, sonra bırakılmış. |
| Kodilan | Kapanmış; alan adı şimdi alakasız bir sitede. |

### Yurt dışı (model örnekleri)
- **HiringCafe:** Şirket sitelerini AI ile tarıyor. Kendi beyanına göre aylık 2 milyon aktif kullanıcı, reklamsız, 6,8 M$ yatırım. Başlangıcı: 10.000 girişim ilanından oluşan bir tablo.
- **SimplifyJobs / Pitt CSC staj listesi:** GitHub'da ~45 bin yıldız. Bir üniversite kulübü yürütüyor.
- **builtin.com ve startup.jobs:** Türk girişimlerinin ilanlarını (Good Job Games, Dream Games, Analog Devices İstanbul, Sezzle) ATS'lerden toplayıp yayınlıyor. Ama İngilizce, Türk öğrenciye özel değil ve "uygun mu?" ayıklaması yok.

---

## 3. Dağınıklık testi (8 gerçek ilan)

| İlan | Şirket sitesi / ATS | Kariyer.net | Youthall | Techcareer | Diğer |
|---|---|---|---|---|---|
| Good Job Games – SE New Grad | ✔ Greenhouse | – | – | – | ODTÜ KPM, builtin, startup.jobs, bayt |
| Obilet – Jr. Data Analyst | ✔ Recruitee | – | – | – | (Earlybird panosunda "Data Analyst") |
| Dream Games – SE Part-time | ✔ kendi sitesi + Lever | – | – | ✔ | Boğaziçi KM, Index Ventures panosu, builtin |
| P.I. Works – Product Design Intern | ✔ BambooHR | – | eski dönemde ✔ | – | builtin (eski) |
| Analog Devices – SW Systems Design Intern | ✔ Workday | – | – | benzer ADI stajları ✔ | builtin |
| Sezzle – Junior SE (Türkiye) | ✔ Greenhouse | – | – | – | builtin, torre, remotejobs |
| Hyperever – Uzun dönem staj | ✔ kendi sitesi | – | – | – | – |
| Codeway – stajyer ilanı | ✔ Lever | – | – | – | – |

"–" işareti, arama sonuçlarında görünmediği anlamına geliyor (LinkedIn'de olabilir; arama motoru indekslemiyor).

**Sonuç:**
- Hiçbir platform bu ilanların hepsini göstermiyor.
- Kariyer.net ve Youthall bu girişim ilanlarının neredeyse hiçbirini taşımıyor.
- **Şirketin kendi sitesi ve ATS'si 8 ilanın 8'ini de içeriyor.** Doğrudan kaynaktan toplama yaklaşımı doğru.
- Sürpriz kaynaklar: üniversite kariyer merkezi panoları (ODTÜ KPM, Boğaziçi) ve VC portföy panoları (Earlybird, Index Ventures). Bunlar Türk girişim ilanlarını öğrencilere yönelik olarak zaten topluyor.

---

## 4. Kapsam testi (mevcut 1.299 firma)

**ATS testi:**
- 1.299 firmadan 40'ı ATS kullanıyor (yaklaşık %3).
- Bu 40 firmadan 1.000 ilan geldi. Türkiye'de ya da uzaktan olan 182 ilan var; bunlardan 7'si öğrenci ilanı.

**Kariyer sayfası testi (392 sayfa, basit kurallarla):**

| Sınıf | Sayı |
|---|---|
| İlan listesi var | 39 (~210 başlık) |
| Kariyer.net (18), LinkedIn (9) veya Google Form'a yönlendiriyor | 30 |
| Genel CV / açık pozisyon yok | 22 |
| JS ile yükleniyor (boş görünüyor) | 9 |
| Erişilemedi | 50 |
| Belirsiz | 242 |

- **"Belirsiz" sınıfı:** 15 sayfa elle okundu. Bunların çoğu gerçek bir kariyer sayfası değil; keşif betiği "gizlil**ik**" kelimesini "ik" (insan kaynakları) sandı. Bu bir keşif hatası ve düzeltilecek. 15 sayfanın yalnızca 1'inde gerçek ilan vardı.
- **Kendi sayfasında gerçek öğrenci fırsatı olan firmalar:** ~12. Örnekler: ANKASYS, ARKSOFT, Beakwise (uzun dönem SE stajı), C-Prot, GÖRSENTAM, LOTEC, Mavvo, SDT, Sestek, Skymod, TÜBİTAK BİLGEM, İnores.
- **robots.txt ile engellenen:** 3 site. Bunlar atlanacak.

**Sonuç:** Mevcut liste ağırlıklı olarak teknopark KOBİ'lerinden ve savunma tedarikçilerinden oluşuyor. Bu listeden şu an yalnızca **yaklaşık 20 öğrenci fırsatı** çıkıyor. Haftada 30+ yeni fırsat için yapılması gerekenler:
- Firma listesini **öğrenci alan firmalarla** genişletmek: büyük teknoloji şirketleri, bankaların teknoloji şirketleri, oyun şirketleri, telekom, ana savunma firmaları ve Türkiye genelindeki teknoparklar (ODTÜ Teknokent, İTÜ Arı, YTÜ, Bilkent Cyberpark, Hacettepe…).
- Workday, SuccessFactors ve Peoplise toplayıcıları eklemek. Büyük şirketler bunları kullanıyor.
- Üniversite kariyer merkezi panoları ve VC portföy panoları. **İzin istenerek** (bkz. §7).
- Jooble ve Careerjet API'leri. Web siteleri bot doğrulaması istiyor; bu yüzden kapsamları yalnızca API anahtarıyla ölçülecek.

---

## 5. Talep

- Bilgisayar mühendisliği bölümleri 174 üniversitede var; 2025'te görünen toplam kontenjan 12.749 (üçüncü taraf kaynak, resmi değil). Buna yazılım mühendisliği ve bilgisayar programcılığı da eklenince on binlerce öğrenci ediyor. Her biri zorunlu staja (genelde 20 iş günü × 2) ve ilk işe ihtiyaç duyuyor.
- Talebin kanıtları:
  - GDG İÜ'nün WhatsApp kariyer grubu ve elle tuttuğu liste.
  - ODTÜ ve Boğaziçi kariyer merkezlerinin ilanları yeniden paylaşması.
  - Youthall'un büyüklüğü.
- Mevcut staj uygulamalarının küçük kalmasının nedeni talep eksikliği değil. Hepsi işverenin ilan girmesini bekleyen iki taraflı pazar yerleri ve işveren tarafını dolduramıyorlar.

---

## 6. Dağıtım

| Kanal | Veri | Karar |
|---|---|---|
| WhatsApp | İnternet kullanıcılarının %90'ı (TÜİK 2026 hane halkı anketi haberleri) | **Ana kanal.** Günlük özeti WhatsApp kanalında paylaşmak. Resmi bir kanal API'si yok; gayriresmî araçlar hesap kapatma riski taşıyor. Bu yüzden özet otomatik hazırlanacak, paylaşım elle yapılacak (günde ~1 dk). |
| Instagram | %71,1 | İkinci kanal. Resmi içerik yayınlama API'si var (işletme hesabı gerekiyor). Kasım'da. |
| Telegram | %13,8 | İkincil. Otomasyonu kolay ama kitlesi küçük. |
| GitHub README | Yazılım öğrencileri | Ana kayıt yeri + yıldız/CV etkisi. |
| GDG on Campus kulüpleri | İÜ, ODTÜ (287 üye), BAİBÜ (547), DEÜ (183), İstinye (112), Yeditepe, Haliç, Doğuş, Kayseri, Yaşar… | Kulüplerin kariyer WhatsApp gruplarına "otomatik liste" teklifi. Çevre gerektirmiyor. |
| Kendi LinkedIn paylaşımı | – | "İş ararken yaptım" hikâyesi. |

---

## 7. Yasal çerçeve

Türk hukukunda web kazımaya özel bir düzenleme yok. Değerlendirme şu başlıklar üzerinden yapılıyor:
- **FSEK m.6/I-11 ve Ek m.8 (veri tabanı koruması):** Özgün bir veri tabanının önemli bir bölümünü sistematik olarak kopyalamak risklidir. Yargıtay internet sitelerini veri tabanı olarak koruyan kararlar vermiş (11. HD, 2016/6829 E., 2018/768 K.).
- **KVKK:** Kişisel veri toplamak en yüksek risk.
- **TTK m.54 (haksız rekabet).**
- **Sitelerin kullanım şartları.** hiQ–LinkedIn davası sonunda kullanım şartlarının ihlali nedeniyle hiQ aleyhine bitti.

**StajRadar'ın kuralları (riski düşük tutmak için):**
1. Yalnızca şirketlerin kendi kariyer sayfaları ve ATS'leri. Bunlar başka birinin derlediği bir veri tabanı değil, şirketin kendi ilanları ve herkese açık.
2. Kariyer.net, Youthall ve LinkedIn gibi platformlardan veri çekmek yok. Bot korumasını aşmak da yok.
3. robots.txt'ye uyulacak. Bir siteye günde en fazla 2 ziyaret.
4. İlan metninin tamamı kopyalanmayacak; kısa özet + orijinal bağlantı verilecek.
5. Kişisel veri saklanmayacak. İlandaki işe alımcı adı ve e-postası atılacak.
6. Üniversite panoları ve VC panoları yalnızca **yazılı izinle** kullanılacak. İzin yoksa bağlantı vermekle yetinilecek.
7. Her ilanda bir "kaldırılmasını isteyin" bağlantısı olacak.

---

## 8. Teknik riskler

| Risk | Önlem |
|---|---|
| GitHub, herkese açık repolarda 60 gün hiç etkinlik olmazsa zamanlanmış görevleri kapatıyor | Günlük güncelleme commit'leri etkinlik sayılır. Yine de haftalık kontrol yapılacak. |
| Keşif kalitesi ("gizlilik" hatası) | Kariyer bağlantısı kalıpları sıkılaştırılacak; AI ile "bu bir kariyer sayfası mı?" kontrolü eklenecek. |
| JS ile yüklenen sayfalar (9) | Sonra başsız (headless) tarayıcı. Şimdilik atlanacak. |
| Hayalet ilanlar (ör. Dream Games'in 2022 tarihli ilanları) | "X aydır açık" etiketi. |
| AI maliyeti | Haiku ile ayda ~1,5 $. Değişmeyen sayfa tekrar gönderilmeyecek. |
| AI yanlış bilgi çıkarması | Başlığın sayfada gerçekten geçtiği kontrol edilecek; 50 ilanlık değerlendirme setiyle ölçülecek. |

---

## 9. İsim

"Staj Radar" alınmış; "Türkiye Kariyer Radarı" adında bir proje de var. Kontrol edilen adaylar (16.10, RDAP ve GitHub):

| Aday | Alan adı | GitHub kullanıcı adı |
|---|---|---|
| **staj.dev** | boş görünüyor (.dev için HTTPS zorunlu; GitHub Pages ile uyumlu) | stajdev: boş |
| stajist.com | boş | boş |
| kodstaj.com | boş | boş |
| stajpusula.com | boş | boş |
| stajakisi.com | boş | boş |
| stajla.com | **dolu** | dolu |

Öneri: **staj.dev.** Kısa, yazılım öğrencisine hitap ediyor ve akılda kalıyor. Diğer mühendisliklere açılırsa ileride yeniden düşünülebilir. Alan adını satın alma kararı kullanıcıda.

---

## 10. Revize plan

| Tarih | İş |
|---|---|
| 17–18.10 (hafta sonu) | İsim kararı. Keşif hatasının düzeltilmesi. Workday + Peoplise toplayıcıları. |
| 19–23.10 | Firma listesini öğrenci alan firmalarla genişletmek (Türkiye teknopark dizinleri + büyük teknoloji). AI kariyer sayfası okuyucu (Haiku). 50 ilanlık değerlendirme seti. |
| 24–31.10 | GitHub README tablosu + WhatsApp kanalı (günlük özet). GDG İÜ ve GDG ODTÜ'ye beta teklifi. Jooble/Careerjet anahtarlarıyla kapsam testi. Üniversite kariyer merkezlerine izin e-postası. |
| 31.10 kontrol noktası | Haftada **30'dan az yeni öğrenci fırsatı** çıkıyorsa kaynak stratejisi değişecek. |
| Kasım | Web sitesi, Instagram, CV eşleştirme. |

---

## Kaynaklar
- DataReportal Digital 2026 Turkey: https://datareportal.com/reports/digital-2026-turkey
- TÜİK 2026 internet kullanımı haberi: https://www.dailysabah.com/turkiye/internet-use-in-turkiye-rises-to-923-in-2026-survey/news
- Telegram oranı (Türk teknoloji raporu): https://www.ekonomist.com.tr/teknoloji/turkiye-nin-2026-dijital-karnesi-en-cok-kullanilan-ilk-3-uygulama-hangileri-oldu--77517
- HiringCafe: https://thenextweb.com/news/hiringcafe-6-8m-pre-seed-ai-talent-agent
- SimplifyJobs listesi: https://gittrend.io/repo/SimplifyJobs/Summer2027-Internships
- GDG İÜ listesi: https://github.com/gdgoncampusIstanbulUniversity/Is-Ilanlar-ve-Kariyer-imkanlari
- Staj Radar (aynı isim): https://github.com/yusflhan-a11y/staj-radar
- Türkiye Kariyer Radarı: https://github.com/emirhanas2/turkiye-kariyer-radari
- ODTÜ KPM ilan örneği: https://kpm.metu.edu.tr/?p=8992
- Web kazıma ve Türk hukuku (Mondaq): https://www.mondaq.com/turkey/copyright/1304748/web-kaz%C4%B1ma-web-scraping-ve-internet-sitelerine-y%C3%B6nelik-koruma
- Web kazıma ve haksız rekabet: https://www.goksusafiisik.av.tr/tr/publications/2025-summer-issue/web-scraping-eyleminin-haksiz-rekabet-acisindan-degerlendirilmesi?id=510
- hiQ – LinkedIn: https://www.idtheftcenter.org/podcast/weekly-breach-breakdown-scraping-by-court-rules-hiq-violated-linkedin-terms-conditions-data-scraping/
- GitHub zamanlanmış görev kuralı: https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows
- WhatsApp Kanalları API durumu: https://whapi.cloud/blog/whatsapp-channel-api-automation
- Bilgisayar mühendisliği kontenjanı (üçüncü taraf): https://ykskocum.com/bolum/bilgisayar-muhendisligi/
- GDG on Campus ODTÜ: https://gdg.community.dev/gdg-on-campus-middle-east-technical-university-cankaya-ankara-turkiye/
- Ham veriler: `scratchpad/kapsam_sonuc.json`, `veri/ham_ilanlar.json`
