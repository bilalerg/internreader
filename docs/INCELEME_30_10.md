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

## Elle dene

```bash
.venv/Scripts/python -m pytest -q tests/test_kalite.py tests/test_guncellik.py tests/test_ats.py
```

`secim.py`'de `FIRMA_BASINA_AZAMI`'yı 1 yap, testi çalıştır, hangi testin neden kırıldığını oku, geri al.
