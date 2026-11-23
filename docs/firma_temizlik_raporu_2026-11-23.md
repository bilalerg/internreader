# Firma listesi denetimi — 23 Kasım 2026

## Kapsam

`veri/firmalar.csv` içindeki **3.342 şirketin tamamı** kontrol edildi. Bu sayı canlı veritabanında daha önce görülen 3.418 sayısından farklıdır; bu rapor yerel CSV içindir. Alan adları robots kurallarına uyan HTTP istemcisiyle okundu. Site açılması, şirketin bugün faal olduğunun veya işe aldığının kanıtı sayılmadı.

| İlk kontrol | Şirket |
| --- | ---: |
| Site açıldı | 2.566 |
| Web adresi yok/geçersiz | 364 |
| Erişilemedi | 396 |
| Robots/adres engeli | 15 |
| Okunamadı | 1 |

Erişilemeyenlerin 357'si alternatif `www`/HTTP kök adresiyle yeniden denendi; **131'i açıldı**. Böylece toplam 2.697 siteye en az bir biçimde ulaşıldı. Dört eski adres satış/park sayfasıydı. Ana sayfada son 365 gün içinde tarihli şirket haberi gibi katı faaliyet kanıtı **23 şirkette** bulundu. Kalanları “kapalı” saymak için kanıt yok. Kayıtlarda aynı normalize web alan adının birden çok şirkete verilmesi görülmedi.

[İTÜ ARI](https://firmalar.ariteknokent.com.tr/), [YTÜ](https://www.yildizteknopark.com.tr/firmalarimiz) ve [Teknopark İstanbul](https://www.teknoparkistanbul.com.tr/firma-katalogu) güncel dizinleriyle eşleşen **844 tekil CSV şirketi** var. Önceki 959 sayısı şirket değil, birden fazla dizinde bulunabilen *eşleşen dizin kaydı* sayısıydı. Dizinde görünme de faaliyet kanıtı değildir.

## Kariyer kaynakları

CSV'de kayıtlı veya ana sitelerde bulunan 753 kariyer adresi kontrol edildi: **728 açıldı, 24 erişilemedi, 1 engellendi**. Açılan adresler genel kariyer sayfası da olabilir; açık ilan sayısı değildir. Yanlış iki kariyer bağlantısı, [Asis](https://www.asis.com.tr/insan-kaynaklari/) ve [Baycan](https://baycan.com.tr/kariyer/insan-kaynaklari-sureci) için düzeltildi. Kayıtlı 11 diğer bağlantı inceleme sırasında hata/engel verdi ve otomatik silinmedi.

## CSV'de yapılan kesin düzeltmeler

- [Grand Games](https://grand.gs/): park edilmiş eski web adresi değiştirildi; [kariyer sayfası](https://grand.gs/careers/) eklendi. Lever `grand` kaynağı açık ilan döndürüyor.
- [Cerebrum Tech](https://www.cerebrumtechnologies.com/): park edilmiş adres, şirket profilinde yayımlanan güncel adresle değiştirildi.
- [Art Life Medya](https://artlifeb2b.com/): eski alan adı süresi dolmuş; şirketin kendisini tanıttığı yeni adresle değiştirildi ve yanlış `savunma` etiketi düzeltildi. Yeni site otomatik tarayıcıya robots engeli veriyor.
- Robimek: eski `robimek.com` alan adı satış sayfası olduğu için `web` alanından kaldırıldı. **Şirket kaydı silinmedi**; güncel adres doğrulanamadı.

## İnceleme sırası

`firma_temizlik_oncelikleri_2026-11-23.csv` her şirketi kanıt ve eylem sütunlarıyla sıralar. Öncelik: 11 kayıtlı kariyer bağlantısı hatası, 295 tamamen kaynaksız kayıt, 69 web'i olmayan ama ATS/kariyer kaynağı bulunan kayıt, 278 erişim/engel sorunu. Açılan 1.928 sitede ne tarihli faaliyet ne doğrulanmış ilan kaynağı bulundu; bunlar belirsiz kaldı. 733 kayıtta bilinen veya aday ilan kaynağının *gerçek açık pozisyon* içerip içermediği ayrıca doğrulanmalıdır.

Hiçbir şirket sırf bir HTTP hatası, eski alan adı veya dizin eşleşmezliği nedeniyle silinmedi. Bu çalışmanın tamamlanan kısmı **tüm CSV'nin ağ ve kaynak ön elemesi**; şirketin hukuken/faalen çalıştığını ve yatırım/çalışan durumunu 3.342 şirket için tek tek kanıtlayan bir sicil denetimi değildir.
