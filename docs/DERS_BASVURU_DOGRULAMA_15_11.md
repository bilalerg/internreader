# İlanı görmek ile başvuruyu doğrulamak

Bu doğrulama akışı, başvuru takibi paneliyle birlikte geliştirilmiştir.

## Neden ayrı bir tablo?

`ilanlar.aktif`, ilanın kaynak listesinde takip edilip edilmediğini tutar. Kaynak listesi eski olabilir.
`ilan_dogrulamalari` ise başvuruya ilişkin kanıtı tutar. Aynı ilan listede görünüp başvurusu kapalı olabilir.

- `durum`: acik / kapali / belirsiz.
- `neden`: kararın gerekçesi; ilan metni veya anahtar saklanmaz.
- `ilk_kontrol`: doğrulama takibinin başlangıcı.
- `kontrol_zamani`: son detay sayfası kontrol denemesi (başarısız denemeler dahil).
- `acik_dogrulama_zamani`: son açık kanıtı; başarısız kontrol bunu ilerletmez.
- `gorulmeme_sayisi`: son görülmeden beri ilanı içermeyen başarılı kaynak listelerinin sayısı.

## Akış

1. `depo/ilanlar.py`: ilan listede yeniden görülürse kayıp sayacı sıfırlanır.
2. ATS'nin açık listesinde bulunmak açık kanıtıdır. Detay sayfasından alınmış kapanış kanıtını tek başına silemez.
3. Başarılı listede ilk yokluk belirsizdir; ikinci yokluk `aktif=False` yapar. Hatalı tarama sayacı artırmaz.
4. Günlük `calistir`, ayrıntı çıkarımından sonra ve yayın/bültenden önce `dogrulama.py` adımını çağırır.
5. En çok 120 öğrenci ilanı, dört iş parçacığıyla kontrol edilir; yeni ilanlar önce gelir. Detay kontrolleri arasında en az 24 saat vardır.
6. `isleme/basvuru.py` HTML'den kanıt çıkarır: tek H1 ilan başlığıyla eşleşen detay sayfasında kısa ve açık kapanış
   ifadesi veya etkin başvuru bağlantısı/form kontrolü bulunmalı. Yönlendirme sonrası genel kariyer sayfasında ise
   yalnızca aynı başlıklı tek iş kartının kendi etkin başvuru bağlantısı açık kanıtıdır. Başka kartların düğmeleri
   sayılmaz. Lever gibi H1 kullanmayan ATS'lerde ilan başlığı ile aynı ilan adresine özgü başvuru bağlantısı birlikte
   aranır; başvuru formu adreslerinde URL'deki ilan başlığı, sayfa metni ve etkin form birlikte kontrol edilir.
   200 yanıtı veya yalnızca başlık açık kanıtı değildir.
7. `depo.yayinlanacak_ilanlar`, kapalı ilanı site ve bültenden eler. Üç gündür açık kanıtı olmayan takipteki kayıtlar
   da geçici olarak yayından düşer; silinmez. Başarılı kontrolle geri gelebilir.
8. JSON'daki `dogrulama` bilgisi siteye taşınır; belirsiz ilanlarda "Başvuru durumu doğrulanamadı" görünür.
9. E-posta akışı yalnızca taze `acik` kanıtı olan ilanları kullanır. Belirsiz veya henüz kontrol edilmemiş ilanlar sitede etiketli görünebilir, ancak bültene girmez.
10. Bülten iş akışı, göndermeden önce GitHub Actions anahtarıyla imzalanan zararsız bir HEAD bağlantısını canlı API'de doğrular. İmzalar uyuşmazsa gönderim durur.

Üç gün ve 120 ilan ilk uygulamanın politika değerleridir, evrensel doğrular değildir. Canlıya geçmeden önce
kaynak başına belirsiz sonuç oranı ve kuyruk kapasitesi gözden geçirilmelidir. Kapalı durum sonraki ağ hatasında
unutulmaz; kapanış nedeni korunur, son deneme zamanı ilerler.

## Sınırlar

- İlk sürüm HTML okur; JavaScript çalıştırmaz, başvuru göndermez, CSS dosyalarını hesaplamaz. İşaretlenmiş gizli
  ve disabled içerikleri; nav/header/footer/aside ve related/recommended alanlarını atlar.
- Çok ilanlı #çapa sayfaları, belirsiz kart yapıları ve tekil başlığı doğrulanamayan sayfalar belirsiz kalır.
  Liste kartı tanıma yalnızca belirgin `article`/`li` işaretli ilan kartları için geçerlidir; her şirket desteklenmez.
- robots.txt korunur. LinkedIn, Kariyer.net, Youthall ve Jooble detayları okunmaz; bu alanlara yönlendirme takip edilmez.
- 403/404/410/429/5xx/timeout tek başına kapanış değildir. İlanın kaynakta kaybolması ile erişim hatası ayrıdır.
- Aynı firma/başlık/kaynak/konumla yeni adrese taşınan ilanın kayıp doğrulaması bekleyen eski kartı gizlenir;
  iki adres aynı taramada bulunuyorsa sırf başlıkları aynı diye birleştirilmez.
- Ara tarama ATS listelerini okur; detay doğrulaması günlük işte veya elle `dogrula` komutuyla yapılır.
- Göç `0009` boş yeni tablo ekler; mevcut ilanları silmez. Uygulama göçü normal başlangıçta uygular.
- LLM çağrısı eklenmez; HTTP ve deterministik kurallar kullanılır.

## Canlı sayfa örneklemi (15.11.2026)

- GitHub'daki o güncel 55 ilan arasından farklı kaynaklardan 11 ilan sayfası robots.txt kurallarına uyarak salt okunur
  kontrol edildi. Sonuç: 8 `acik`, 3 `belirsiz`, 0 `kapali`. Bu küçük örneklem doğruluk oranı ölçümü değildir.
- Workday ve Workable örnekleri HTML'de görünür ilan içeriği vermediği için, Skymod örneği ise tekil başlık ve başvuru
  kontrolü eşleşmediği için belirsiz kaldı. Tarayıcı/ATS API desteği ayrı çalışma gerektirir.
- Bu örneklem salt okunur toplandı; test başvuru göndermedi.

## Öğrenme sırası

1. `isleme/basvuru.py`: saf fonksiyon; HTML girer, karar çıkar. Ağ/veritabanı yok.
2. `dogrulama.py`: sıradaki kayıtları alır, HTTP ile okur, kararları kaydeder.
3. `depo/dogrulama.py`: kayıt ve yayın politikası. Ağ yok.
4. `__main__.py`: günlük akışta kontrolün nerede çağrıldığı.

Yerel geçici veritabanları ve sahte HTTP ile test:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_basvuru_dogrulama.py tests/test_sema.py
```

Elle kullanım (gerçek HTTP isteği ve yapılandırılan veritabanına yazma içerir; test değildir):

```powershell
.\.venv\Scripts\python.exe -m internreader dogrula --sinir 20
.\.venv\Scripts\python.exe -m internreader yayinla
```

`yayinla` yalnızca çıktı üretir; GitHub'a push etmez.
