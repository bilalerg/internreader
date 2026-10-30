# İnceleme rehberi — 30 Ekim 2026: ilk bültenin elle denetimi

Bu turda kodu ben yazdım. Senin işin: sırayla oku, soruları kendi cümlenle cevapla. ~40 dk.

## En önemli ders: testler geçti, canlıda çalışmadı

Dünkü bayat ilan denetimi testlerden geçti ama Yeditek yayında kaldı. Neden? Test verisi kısa bir metindi. Gerçek sayfada
10.536 karakter menü var, modele ilk 6.000 karakter gidiyor; model ilanı hiç görmüyordu, özeti de menüden yazıyordu.
**Sahte veriyle yazılan test, gerçek verinin şeklini bilmez.** Bu yüzden bu tur iki kez gerçek sayfalarla doğruladık:
1. Sıfırdan: gerçek sayfa + gerçek yapay zekâ + yerel SQLite.
2. Prova: Neon'daki durumun kopyası gibi başlayıp (eski kararlar, eski özetler) sabah işinin yapacağını çalıştırdık.
   İkincisi şart: yeni kararlar doğru çıkar ama canlıda eski kararlar duruyor; asıl soru onların düzelip düzelmediği.

> Soru 1: "Testlerim yeşildi ama üretimde çalışmadı" hikâyesini mülakatta nasıl anlatırsın? Ne değiştirdin?

## 1. Metin temizliği — `kaynaklar/kariyer_sayfasi.py` → `ilan_metni`
Sıra: `<main>`, en uzun `<article>`; ikisi de yoksa nav/header/footer/aside atılır, başlığın son geçtiği yerden başlanır.
`<main>` içinde aside kalır: Beakwise'ın "Application Deadline" bilgisi orada. Kariyer sayfası okuyucusu bunu kullanmaz, onun
sayfanın tamamına ihtiyacı var.

## 2. Tür ve rol — `isleme/kategori.py`, `yz/ayrinti_cikarici.py`
- **Tür:** iş, eğitim, yarışma, genel başvuru. Önce kural (başlıkta "Camp", "League"), sonra model. Kartta "Staj" yerine
  "Eğitim programı" / "Yarışma" yazar; genel CV sayfası yayından düşer. CV cümlesi metnin **başında** aranır: gerçek ilanların
  altında da "aradığını bulamadın mı?" kutusu olabilir.
- **Rol:** sınıflandırıcı kariyer sayfası ilanlarında yalnızca başlığı görür. Metnin tamamını gören ayrıntı çıkarıcı rolü
  düzeltir (`depo.rol_guncelle`). "Hotel WD Staj" görevleri satış ve kurulum: yayından düştü. Eğitim ve yarışmada rol
  düzeltilmez (Cloud Camp düşmesin diye; ilk canlı denemede tam bu hata çıktı).
- `AYRINTI_SURUMU` 3 oldu: aktif ilanlar bir kez yeniden çıkarılır, sonra bir daha gönderilmez.

Değerlendirme seti 37 örnek. Eski istem: rol 0,973, "uygun" isabeti 0,929. Yeni istem: ikisi de 1,0. Seviye 0,968 → 0,935
(fark eden ek hata teknik olmayan bir ilanda; yayın kararını etkilemiyor). Set küçük: 1 örnek ~%3 oynatır, abartma.

> Soru 2: Neden Türk SEM'i düzeltmek için sınıflandırıcıyı değil ayrıntı çıkarıcıyı kullandık?

## 3. Etiketler — `isleme/kategori.py`
- **Savunma:** savunmakariyer listesinden gelmek yetmez. Başlıkta kanıt, elle doğrulanmış etiket (`savunma_dogrulandi`)
  ya da "savunma" etiketi + metinde kanıt gerekir.
- **Girişim:** kural bilerek dar: `girisim` etiketi ya da turkiye.ai. Teknopark kiracısı olmak, Lever kullanmak kanıt değil;
  onlar "aday". Liste: `docs/GIRISIM_LISTESI_30_10.csv` (226 evet, 658 aday). **Senin kararın:** gerçek girişimleri
  `veri/firmalar.csv`'de `girisim` etiketiyle ekle. `firma_listesini_esitle` dosya değişince sabah işinde kendisi aktarır.
- **Marka adı:** `yayin/__init__.py` → `MARKA_ADI` (Nova Spark X → Patika Global). Adaylar: `docs/MARKA_ADAYLARI_30_10.csv`
  (firma adı ile alan adı uyuşmayanlar; bir kısmı marka farkı değil, yanlış web adresi olabilir).

> Soru 3: Girişim kuralını daraltmanın bedeli ne? (İpucu: "yalnızca girişimler" seçen kaç ilan görür?)

## 4. Avature — `kaynaklar/ats.py` → `avature`, `avature_detay_ayristir`
Eskiden arama terimi ("Turkey") konum diye yazılıyordu; Gebze'deki ilan "Turkey" görünüyor, Slovakya ilanı da araya
karışabiliyordu. Artık konum, tarih, iş türü, çalışma modeli detay sayfasından okunur; Türkiye dışı elenir. Sayfalar ağır
(~1 MB), yalnızca öğrenci başlıklı adaylar açılır. Kalkmış ilan (404) atlanır; başka hata firmanın taramasını başarısız sayar,
var olan ilanlar kapanmaz.

## 5. Sıralama ve kota — `isleme/guncellik.py` → `siralama_anahtari`, `bulten/secim.py` → `bulten_sec`
Eskiden 15'lik kesim alfabetikti, Skymod dışarıda kalıyordu. Artık önce yeni, aynı tazelikte iş → girişim → ücretli, tarihsiz
ve sürekli açık geride. Bir e-postada firma başına en fazla 2 ilan; seçilmeyen "gönderildi" sayılmadığı için sonraki bültene kalır.

## 6. Sabah saati — `api.py` → `/api/cron/gunluk`, `vercel.json`, `gunluk.yml`
GitHub zamanlaması 6,5 saat gecikti. Vercel Cron korumalı ucu çağırır, uç GitHub'da işi başlatır; GitHub zamanlaması yedek
(09:37). Yedek çalışma, iş bugün bittiyse tarama yapmadan biter. Aynı Türkiye gününde abone tek bülten alır.
**Yapman gerekenler:** `docs/KURULUM_UCRETSIZ.md` → Bölüm 10.

> Soru 4: Saldırgan `/api/cron/gunluk`'u bulsa ne olur? Hangi satır korur, neden `==` değil `compare_digest`?
> Soru 5: Vercel ve GitHub aynı gün iki kez çalışırsa tarama, yapay zekâ harcaması ve bülten için ayrı ayrı ne olur?

## 7. Hoş geldin e-postası — `bulten/gonderim.py` → `hos_geldin_gonder`, `api.py` → `onayla`
Kişi kaydolunca motive olsun diye: e-postasını onayladığı anda hazır veriden (yapay zekâ yok) uyan ilanlar gider.
- **Atomik onay** (`depo.aboneyi_onayla`): `UPDATE ... WHERE durum='bekliyor'`. İki sekmeden aynı anda tıklansa bile veritabanı
  yalnızca birine "1 satır değişti" der; ikinci e-posta böyle önlenir. Önce oku-sonra yaz yapsaydık ikisi de "bekliyor" görürdü.
- **Sıra önemli:** önce onay kaydedilir, sonra e-posta denenir. E-posta patlasa da abonelik başlamıştır; kullanıcıya hata gösterilmez.
- **Yakın ilanlar** (`secim.py` → `yakin_ilanlar`): tam uyan yoksa tercihler teker teker gevşetilir, alan en son. "Yakın" olduğu
  e-postada açıkça yazar. Yakın ilan bülten sayılmaz: tam uyan ilan çıkarsa ilk sabah gider.
- **Bütçe:** Brevo günde 300 → 200 bülten + 50 onay + 50 hoş geldin. Dolarsa hoş geldin atlanır, sabah bülteni kapatır.

> Soru 6: Onay ve e-postayı tek veritabanı işleminde yapsaydık SMTP takıldığında ne olurdu?

## 8. Hızlı test — `bulten/gonderim.py` → `deneme_gonder`, `.github/workflows/test_bulten.yml`
Her deneme için sabahı beklemek yerine: Actions → Test bülteni → Run. Kayıt yazmaz, korumalara takılmaz, konu `[TEST]` ile başlar.
Depo herkese açık: adres girdi olarak alınmaz, gizli değerden gelir ve kayıtlara yazılmaz. Hata metni bile yazdırılmaz (SMTP
hatası adresi içerebilir). Çıkış bağlantısı olmayan abone (0) için imzalanır, tıklasan da aboneliğin silinmez.

> Soru 7: Workflow girdisine e-posta alanı koysaydık kim görürdü?

## 9. Ara tarama — `boru.py` → `tara(yalnizca_ats=True)`, `.github/workflows/ara_tarama.yml`
Staj ilanları saatlik değişmez ve kariyer sayfaları yapay zekâyla okunur; tam taramayı sıklaştırmak krediyi eritir. Bu yüzden 6 saatte
bir yalnızca ilan sistemleri taranır (API, ucuz). İki tuzak:
- Kariyer sayfası ilanı "görülmedi" diye kapanmamalı: `sayfa_ilanlari_korunsun`.
- Her commit bir Vercel dağıtımı: `guncelleme` damgası her turda değişir, tek başına commit doğurmamalı (`icerik_degisti`).
Ayrıntı çıkarma da ATS ilanları için çalışır: yeni ilan özetsiz ve rolü doğrulanmamış yayına girmesin. Maliyet artmaz, sabaha göre öne alınır.

> Soru 8: `icerik_degisti` olmasaydı ayda kaç gereksiz dağıtım olurdu?

## 10. Tıklama ölçümü — `bulten/tiklama.py`, `api.py` → `tikla`, `depo/tiklamalar.py`
İlk soru şu: "kaç kişi gerçekten kullanıyor?" E-postadaki "Başvur" önce `/api/t/<jeton>` adresine gelir, kaydedilir, ilana yönlenir.
- **Adres jetonda, imzalı:** Neon kapalı olsa da öğrenci ilana gider; yalnızca ölçüm kaybolur. İmza olmasa bu uç herkesin kullanabileceği bir
  yönlendirici olurdu (open redirect). `INTERNREADER_GIZLI_ANAHTAR` değişirse eski e-postalardaki düğmeler ana sayfaya gider.
- **Kayıtta adres yok:** e-posta, abone no, IP, tarayıcı tutulmaz. `kisi` her hafta değişen imzalı bir kod: "bu hafta kaç farklı kişi?" sayılır, haftalar
  arasında kişi izlenemez. 180 gün sonra silinir. Bu bir takma addır, anonim değildir: gizli anahtarı bilen, o haftanın kodunu yeniden üretebilir.
- **Tarayıcılar elenir:** Outlook gibi güvenlik tarayıcıları bağlantıları kendiliğinden açar. Bot adı, e-postadan 30 sn içinde açılış ve 10 sn içinde 3 farklı
  ilan "şüpheli" sayılır; HEAD hiç sayılmaz. Eleme kusursuz değil: rakamı kesin değil, en iyi tahmin olarak oku.
- **Nerede görülür:** Actions → Günlük çalışma → Summary → `tiklama_son_7_gun`. Test e-postası tıklamaları `deneme` satırında ayrı sayılır.
- **Ölçmediği şey:** e-postanın açılması, sitedeki tıklamalar, düz metin sürümündeki bağlantılar.

> Soru 9: `tiklama_kaydet` neden `supheli` değerini de benzersizlik anahtarına katıyor? Katmasaydık hangi tıklama kaybolurdu?
> Soru 10: Jetonun içine abone numarasını yazsaydık ne olurdu? (İpucu: adres sunucu kayıtlarında görünür.)

## 11. Kapsam büyütme — `veri/firmalar.csv`
`firmalar.csv`'de taranacak şirket 280'den 374'e çıktı (canlıda keşifle bulunmuş birkaç firma daha var: 29.10'da 293 taranıyordu). Gerçek ölçüm (yalnızca eklenenler, gerçek yapay zekâ, 0,11 $): 113 firma tarandı, 12 uygun ilan çıktı, bunların **5'i canlıda
yoktu** (20 → ~25). Ders: listeye şirket eklemek ilan getirmiyor; yalnızca öğrenci alan şirketi eklemek getiriyor.
- **İşe yarayan:** bilinen işverenleri ilan sistemlerinde adlarıyla yoklamak. İlk ~100 adda 17 pano (çoğu zaten listedeydi), ikinci 138 adda 3, web adresi
  olmayan 319 firmada 2: doygunluk. Toplamda 9 yeni pano, ~100 yeni kariyer sayfası.
- **İşe yaramayan:** teknokent ve yatırımcı rehberleri. ODTÜ, ARI, Hacettepe sayfaları açıldı ama firma bağlantısı çıkmadı (büyük olasılıkla JavaScript ile
  doluyor). Yalnızca Yıldız, Marmara ve Collective Spark okunabildi.
- **Hâlâ taranamayan:** Hepsiburada, Getir, Papara, Akbank, Aselsan, Ford Otosan gibi 41 işveren. Bir kısmı botları engelliyor; bu engeller aşılmaz.
- **Maliyet sınır değil:** 244 sayfanın 48'i 12 günde değişti (günde ~4); 255 sayfanın 4'ü yarım saatte bile değişti (her gün yeniden okunur). Sayfa başına
  0,0007 $ ile ayda ~0,2 $; tavan 2 $. Bu bir tahmin: gerçek rakam canlıda Summary'deki harcamadan okunacak. Tek seferlik ilk okuma ~0,11 $.
- **Sıradaki en büyük kaldıraç:** `SERPER_API_KEY`. Haftalık arama, ilan açan ama listede olmayan firmaları ve 319 firmanın web adresini bulur. Kuruluş: `.env.example`.

> Soru 11: Bu ölçümü neden boş bir veritabanında ve yalnızca yeni firmalarla yaptık? Tüm listeyle yapsak hangi rakam yanıltıcı olurdu?

## Elle dene

```bash
.venv/Scripts/python -m pytest -q tests/test_kalite.py tests/test_hos_geldin.py tests/test_bulten_dene.py tests/test_ara_tarama.py
.venv/Scripts/python -m internreader bulten-dene ben@ornek.com --hos-geldin --gonderme
```

`secim.py`'de `FIRMA_BASINA_AZAMI`'yı 1 yap, testi çalıştır, hangi testin neden kırıldığını oku, geri al.
