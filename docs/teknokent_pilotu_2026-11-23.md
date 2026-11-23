# Teknokent dizini pilotu — 23 Kasım 2026

## Yöntem ve sınır

Resmî [İTÜ ARI](https://firmalar.ariteknokent.com.tr/), [YTÜ](https://www.yildizteknopark.com.tr/firmalarimiz) ve [Teknopark İstanbul](https://www.teknoparkistanbul.com.tr/firma-katalogu) dizinleri okundu. İTÜ/YTÜ canlı sayfaları `ops/teknokent_dizin_pilotu.py` ile, Teknopark İstanbul'un erişim engeli veren kataloğu web okuyucusu ile bir defa alınıp yerel anlık görüntüye kaydedildi. Alan adı veya tam normalize ad eşleşmesi kullanıldı; ad benzerliği tek başına birleştirilmedi. Robots dosyalarında bu dizinler için tarama yasağı görünmedi.

| Kaynak | Dizin kaydı | CSV ile eşleşen | İnceleme adayı |
| --- | ---: | ---: | ---: |
| İTÜ ARI | 132 | 94 | 38 |
| YTÜ | 679 | 530 | 149 |
| Teknopark İstanbul | 338 | 335 | 3 |

Toplam 1.149 **dizin kaydı** var; kaynaklar arası tekil şirket sayısı değildir. 190 inceleme adayı otomatik olarak “yeni faal şirket” anlamına gelmez: farklı ticaret unvanları, eksik alan adları ve mükerrer kayıtlar olabilir. Teknopark İstanbul'daki üç ad eşleşmezliğinden birinde kaynak metninin karakter kodlaması bozuk. Katalogda görünme işletmenin bugün faal veya işe alım yapıyor olduğunu kanıtlamaz.

## 50 şirketlik ilk site kontrolü

İTÜ'den 15 eşleşmeyen ve 15 eşleşen, YTÜ'den 20 eşleşen kaynaksız şirket seçildi. 43 ana site açıldı; 7 siteye erişilemedi. Açılanların hiçbirinde kullanılan **katı tarihli faaliyet kanıtı** saptanmadı; hepsinin faaliyet durumu `belirsiz` kaldı. Başlık/açıklamadaki `alan_sinyali`, yazılım, oyun, siber güvenlik, savunma, robotik, IoT, bulut ve veri gibi alanlar için yalnızca ön elemedir; doğrulanmış faaliyet etiketi değildir.

Yedi sitede kariyer bağlantısı bulundu. Anadolu İnovasyon, Elaves, Ada Yazılım ve Aktek bağlantıları genel kariyer/başvuru sayfaları; açık pozisyon doğrulanmadı. FEV bağlantısı Almanya'daki tek bir yönetici rolüne gidiyor. [Forto iş panosunda](https://careers.forto.com/forto-jobs/) 11 açık iş var, fakat görünen roller Türkiye'de giriş seviyesi yazılım rolü değil. [Borda'nın ilan panosu](https://bordatech.hire.trakstar.com/) “No jobs available” diyor. Bu yüzden pilotta **doğrulanmış uygun açık ilan kaynağı: 0**. Kariyer bağlantısı bulunan yedi şirketi aktif taramaya eklemedik.

Dosyalar: `teknokent_dizinleri_2026-11-23.csv` eşleşmeleri, `teknokent_pilotu_2026-11-23.csv` şirket bazlı site/kanıt durumunu, `teknopark_istanbul_dizini_2026-11-23.csv` resmî katalogdaki sektör etiketlerini içerir. Aktif `veri/firmalar.csv` değiştirilmedi.

## Sıradaki karar kapısı

Önce 190 eşleşmeyen kaydı alan adı ve ticaret unvanıyla tekilleştirip, resmi şirket sitesi + son 6–12 ayda tarihli faaliyet kanıtı + gerçek açık pozisyon listesi olanları kaynak olarak eklemek gerekir. Alan etiketi sadece “yazılım” ile sınırlandırılmamalı; işin kendisi yazılım mühendisliğiyle ilgiliyse oyun, siber güvenlik, savunma, gömülü, robotik, veri ve bulut şirketleri de kapsama alınmalı.
