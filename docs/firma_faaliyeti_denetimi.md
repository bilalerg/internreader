# Firma faaliyeti denetimi

`veri/firmalar.csv` aday havuzudur. Bir alan adının açılması şirketin çalıştığını kanıtlamaz.
`firmalar.aktif` yalnızca tarama iznidir; `faaliyet_durumu` ayrı tutulur.

- **faal:** Son 3 günde açık olduğu ayrıca doğrulanmış bir başvuru ilanı ya da şirketin kendi alan adında son 365 gün içinde tarihli haber bağlantısı.
- **belirsiz:** Kanıt yok, erişim/robots hatası var, web adresi yok veya başka alana yönleniyor. Şirket listeden çıkarılmaz; günlük ilan taraması devam eder.
- **adres_sorunlu:** Alan adı açıkça satış/park sayfasına dönüşmüş. Bu şirketin kapandığı anlamına gelmez.

Kontrol zamanı, kanıt zamanı, bağlantı ve karar nedeni veritabanında tutulur. Yeni eklenen şirketler `belirsiz` başlar. Denetim yapay zekâ ve arama API kredisi kullanmaz. Haftalık/aylık genel keşiften ve günlük ilan taramasından bağımsızdır.

## İlk kuru örneklem (22 Kasım 2026)

CSV'deki 3.340 firmadan kaynak ve ATS/kariyer/web durumu farklı 100 kayıt ayrı yerel veritabanında incelendi: 98 `belirsiz`, 2 `adres_sorunlu`, 0 `faal`. Sorunlu adresler Grand Games ve Cerebrum Tech idi; ikisinde de alan adı satış metni elle teyit edildi. Bu örneklemde ilan doğrulama geçmişi yoktu; bu nedenle canlı veritabanındaki doğrulanmış açık ilan kanıtı ölçülemedi. `belirsiz` kayıtlar faal değil hükmü değildir.

## Kullanım

`python -m internreader firma-denetle --sinir 100` kuru çalışır ve JSON raporlar. `--yaz` sonuçları kaydeder. GitHub Actions `Firma faaliyeti denetimi` elle kuru başlatılabilir; günlük zamanlama 250 kayıtlık partileri kaydeder. Önce hiç denetlenmeyenler seçilir; liste bitince en eski kontrol tekrar edilir. Yaklaşık iki haftada bir tur tamamlanır. Şirketler otomatik silinmez ve yalnızca `belirsiz` olduğu için taramadan düşmez.
