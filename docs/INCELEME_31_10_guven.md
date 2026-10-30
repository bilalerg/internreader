# İnceleme rehberi — 31 Ekim 2026: pilottan önce güven

Okulda 10–20 kişilik pilot başlıyor. Tek kaygı şu: ilk aboneler boş, tekrar eden ya da yanlış ilanlı bir e-posta alırsa güven
baştan gider. Bu turdaki beş değişiklik bunun için. Kodu ben yazdım; senin işin sırayla okumak ve soruları kendi cümlenle
cevaplamak. ~35 dk.

## Önce: testler yeşil, peki gerçek veriyle?

Bu projede test geçip canlıda çalışmayan hata oldu (30.10, Yeditek). Bu yüzden testlerden ayrı bir deneme yapıldı:
- `web/public/veri/ilanlar.json`'daki 20 gerçek ilan (özet, tarih, tür dahil) + `veri/firmalar.csv`'deki gerçek firma listesi
  (374'ü taranıyor) + 200 abone (rastgele ama gerçekçi tercihler, %25 haftalık, bir kısmının son günlerde bülten geçmişi).
- Bilinen sorunu taklit eden 5 sentetik kopya: Binance Accelerator Program üç adreste, Siemens ilanı ikinci şehirde,
  "JUNIOR GAME DEVELOPER" büyük harfle. 30 aboneye programın eski adresi geçen ay gitmiş.
- Elle onay modunda 8 gün: sabah hazırlık → önizleme → yanlış ilanı gizleme → önizlemeden sonra ara tarama → Bülteni gönder
  → hoş geldin; perşembe göndermeyi "unutma", pazartesi düğmeye iki kez basma.
- Her e-posta 16 kurala karşı denetlendi (boş e-posta, aynı e-postada tekrar, aynı kişiye ikinci kez, gizli ilan, günde iki
  bülten, haftalığa pazartesi dışında bülten, sessizliğin beş kuralı, önizlenmemiş ilan, kota sayacı...).

Sonuç: SQLite'ta ve Postgres'te **0 ihlal**; 8 günde 208 abonenin hepsi en az bir e-posta aldı. Denetçinin boş geçmediğini görmek
için kurallar tek tek kasıtlı bozuldu: tekrar engeli kapatılınca 458, önizleme sınırı kapatılınca 51, sessizlik kuralı
kapatılınca 1.787 ihlal yakalandı.

> Soru 0: Denetçiyi neden kasıtlı bozduk? Bozmasaydık "0 ihlal" neyi kanıtlamazdı?

## 1. Aynı ilan kişi başına bir kez — `isleme/tekillestirme.py` → `ilan_anahtari`, `bulten/secim.py` → `bulten_sec`, `depo/bulten.py` → `gonderilen_kimlikler`

**Neden:** Tekrar yalnızca URL'den türeyen `kimlik` ile engelleniyordu. Aynı ilan farklı adreslerle yayınlanınca (yerelde
1.300 ilanda 51 grup) aynı e-postada iki kez çıkabiliyordu; Workday aynı ilanı yeni adresle yeniden yayınlayınca ertesi gün
yeniden gidiyordu.

**Ne yapıldı:**
- Anahtar firma + başlık. Türkçe küçük harf; İ, I, ı, i tek harf sayılır (başlıklar iki dilde yazılıyor, büyük "I"nın küçüğü
  belirsiz); şapka ve noktalar düşer (Yazılım = yazilim); noktalama ve boşluk silinir (Front-End = Frontend). Firma
  farklıysa anahtar farklı: başka firmanın aynı başlıklı ilanı gitmeye devam eder.
- Seçimde anahtar yalnızca **seçilen** ilan için ayrılır: İstanbul kopyası uymayan Ankaralıya Ankara kopyası gider.
- Kopya firma kotasını (firma başına 2) harcamaz.
- Daha önce gidenlerin anahtarı `Gonderim` → `IlanKaydi` birleştirmesinden gelir. **Dikkat:** gönderim kaydı ilana CASCADE ile
  bağlı; ilan silinirse kayıt da anahtar da kaybolur. Bugün ilan silinmiyor (kapanınca `aktif=False`). İlan silen bir bakım
  eklersen anahtarı gönderim tablosuna taşıman gerekir.
- Bülten, hoş geldin, yakın ilanlar ve sitedeki "Bülteni dene" önizlemesi (`web/src/components/Bulten.tsx`) aynı kuralı kullanır.
- Yapılmayan: sitedeki ilan listesi kopyaları hâlâ ayrı satırda gösterir (tasarım kararı, bu turun kapsamı dışında).

> Soru 1: Neden anahtarı yalnızca seçilen ilan için ayırıyoruz? Uymayan ilanın anahtarını da ayırsaydık hangi öğrenci neyi kaçırırdı?
> Soru 2: "Data Intern" ile "Data Engineer Intern" neden farklı anahtar olmalı? Başlıktaki yılı da silseydik ne bozulurdu?

## 2. Açık ilanın gönderim kaydı silinmez — `depo/bulten.py` → `eski_gonderimleri_sil`, `bakim.py`

**Neden:** Bakım 180 günden eski bütün gönderim kayıtlarını siliyordu. Bazı ilanlar aylarca açık kalıyor (Dream Games'in
2022 tarihli "sürekli açık" ilanları); kayıt silinince aynı ilan aynı kişiye yeniden giderdi.

**Ne yapıldı:** Yalnızca kapanmış ilanların eski kayıtları silinir. Kapanmış ama aynı firma + başlıkla hâlâ açık kopyası olan
ilanın kaydı da kalır: kopyayı o kayıt durduruyor (bölüm 1).

> Soru 3: Gönderim kayıtlarını hiç silmesek ne olurdu? Bunu KVKK'nın "en az veri" ilkesiyle nasıl dengeliyoruz?

## 3. Boş hoş geldin gitmez — `bulten/gonderim.py` → `hos_geldin_gonder`, `web/src/pages/onay.astro`

**Neden:** Hiç ilan yokken hoş geldin "şu an ilan yok" diyen, listesiz bir e-postaydı ve kota harcıyordu.

**Ne yapıldı:** Sonuç `bos` ise e-posta gitmez, kota ayrılmaz, kayıt yazılmaz; API yine `bos` döndürür. Onay sayfası eskiden
"çıkınca ilk sen öğreneceksin" diyordu ama e-posta gönderilmediğini söylemiyordu; kişi gelen kutusunu beklerdi. Şimdi:
"Şu an seçimlerine uyan ilan yok, bu yüzden şimdilik e-posta göndermedik. İlk uyan ilan çıkınca sana yazacağız."
Ne zaman olur: neredeyse hiç; yakın ilanlar en son alanı da gevşetir. Yalnızca yayında hiç ilan yokken.
`bulten-dene --hos-geldin` de aynı durumda e-posta üretmez.

> Soru 4: `bos` bu kadar nadirse neden uğraştık? (İpucu: veritabanı boşken ya da yayın bozulduğu sabah kaydolan ilk kişiler.)

## 4. Sessizlik e-postası — `depo/bulten.py` → `sessiz_aboneler`, `bulten/gonderim.py` → `_sessizlik_gonder`, `bulten/sablon.py` → `sessizlik_epostasi`

**Neden:** Denemede 156 günlük abonenin 145'i bir gün hiç e-posta almadı. Uyan ilan çıkmayan biri haftalarca hiçbir şey
duymazsa "bu çalışıyor mu?" der, unutur ya da çıkar.

**Kurallar:**
- Pazartesi, bültenden sonra. Onaylı, en az 7 gündür abone ve son 7 günde hiç e-posta almamış kişiye.
- İçerik: "Bu hafta sana uyan yeni ilan çıkmadı", kaç şirket tarandığı, en çok 5 yakın ilan (daha önce gönderilmemiş).
  **Yakın ilan yoksa gitmez.** Tercihsiz (her şeyi isteyen) abone de almaz: gevşetilecek tercih yok.
- Günler Türkiye takvimiyle sayılır: "bugün + önceki 6 gün". 7 × 24 saat sayılsaydı iş bir pazartesi 09:37'de, ertesi
  pazartesi 07:05'te çalışınca geçen haftanın e-postası "7 günden yeni" görünür, kişi bir hafta atlanırdı.
- Haftada en fazla bir: sessizlik e-postası da "alınan e-posta" sayılır; düğmeye iki kez basılsa da ikincisi gitmez.
- Kota: bültenden sonra, bültenin 250'lik payından kalanla. Bülten durduysa (kota, art arda hata) hiç başlamaz.
- `Bulten.durum` ve tıklama türü `sessizlik`; tıklama raporunun `gonderilen_eposta` sayısına girer. Bülten raporunda
  `sessizlik` (giden) ve `sessizlik_bos` (aday ama yakın ilanı yok) sayıları var.
- Yakın ilanlar "gönderildi" sayılır (bir daha önerilmez) ama bülten sayılmaz: `son_bulten` değişmez.

**Denemede çıkan bulgu (karar senin):** 200 abonede pazartesi 140 bülten + 44 sessizlik = 184 e-posta. Hoş geldin sayaç
150'yi geçince duruyor (yer onay e-postalarına kalsın diye), bu yüzden o pazartesi öğleden sonra onaylayan 5 kişi hoş geldin
alamadı; ilanları ertesi bültende gelir. Pilotta (10–20 kişi) sorun değil. 150 aboneyi geçince seç: sessizliği hoş geldin
eşiğinin altında durdurmak ya da hoş geldin eşiğini yükseltmek.

> Soru 5: Neden "son 7 × 24 saat" değil "son 7 takvim günü"? Kendi örneğinle anlat.
> Soru 6: Sessizlik e-postası neden bültenden sonra gidiyor? Önce gitseydi kotada ne olurdu?

## 5. Elle onay modu — `ayar.py`, `__main__.py`, `bulten/gonderim.py` → `onizleme_gonder`, `depo/ilanlar.py` → `ilan_gizle`, göç `0007`, `.github/workflows/`

**Neden:** İlk elle denetimde 15 ilanın 4'ü yanlıştı. Kurallar düzeldi, ama pilotun ilk haftalarında senin görmediğin bir ilan
abonelere gitmemeli.

**Akış** (kurulumu `docs/KURULUM_UCRETSIZ.md`, bölüm 13):
1. Sabah işi (`calistir`) ilanları hazırlar, **hazırlık anını** `durum` tablosuna yazar (`bulten_hazirligi`), bülten göndermez.
2. İşin sonunda önizleme `TEST_EPOSTA`'ya: son gönderimden (`son_bulten_gonderimi`) hazırlık anına kadar ilk kez görülen bütün
   güncel ilanlar, adresleriyle. Tercih, 15 ilan ve firma sınırı yok. Eski tarihli olanlar "bültene girmez" diye işaretli
   (bültende gitmezler ama sessizlik e-postasında yakın ilan olabilirler). Yeni ilan yoksa önizleme gitmez.
3. Yanlış ilan → Actions → İlan gizle (girdi: ilan adresi; adres zaten sitede herkese açık). Aynı firma + başlıklı kopyalar da
   gizlenir. Gizli ilan `yayinlanacak_ilanlar`'a girmez; site, README, WhatsApp, bülten, hoş geldin, sessizlik ve önizleme
   oradan beslendiği için hepsinden düşer. Sitedeki örnek kararlara da girmez, yapay zekâ ayrıntısı çıkarılmaz. Tarama `gizli`
   alanına dokunmaz: ilan yeniden görülse de açılmaz. `geri_al` ile geri alınır.
4. Actions → Bülteni gönder (`bulten-gonder`): yalnızca hazırlık anına kadar görülen ilanlar. Neden: önizleme 07:40'ta geldi,
   sen 10:00'da bastın, arada 09:23 ara taraması yeni ilan buldu. Sınır olmasa o ilan senin görmediğin halde giderdi.
   Hazırlık yoksa (elle modda sabah işi hiç çalışmamışsa) komut reddeder. Önizlemenin başlangıç işareti hiç geri gitmez.
5. Kapatmak: Actions değişkeni `INTERNREADER_BULTEN_ELLE=0`. Kodda varsayılan kapalı; iş akışında değişken yoksa `'1'`.

**Bilinen boşluklar:**
- Hoş geldin otomatik (istenen buydu). Sabah işinden sonra, sen gizlemeden önce kaydolan kişinin hoş geldininde o sabahın henüz
  bakmadığın ilanı olabilir. API (Vercel) elle modu bilmiyor: Vercel'in ortam değişkenleri GitHub'dakilerden ayrı.
- Pazartesi yeni ilan yoksa önizleme gelmez, ama sessizlik e-postaları düğmeyle gider: pazartesi düğmeye yine bas.
- Gizleme anında var olan kopyalar gizlenir; sonradan başka adresle yeniden yayınlanan kopya yeni ilandır, yeniden gizlenmeli.

> Soru 7: Bülteni neden hazırlık anıyla sınırladık? Hangi senaryoda sınır olmasa görmediğin bir ilan giderdi?
> Soru 8: İlan gizle iş akışında adres neden `run:` satırına doğrudan `${{ inputs.adres }}` diye değil, `env:` ile geçiyor?
> Biri adres kutusuna `$(...)` ile başlayan bir metin yazsa iki durumda ne olurdu?

## Elle dene

```bash
.venv/Scripts/python -m pytest -q tests/test_tekrar.py tests/test_sessizlik.py tests/test_elle_onay.py tests/test_hos_geldin.py
.venv/Scripts/python -m internreader bulten-dene ben@ornek.com --yeni --gonderme
```

- `bulten/secim.py` → `bulten_sec`'te `anahtar in alinan` koşulunu sil, `tests/test_tekrar.py`'yi çalıştır: hangi test neden kırıldı?
- `depo/bulten.py`'de `SESSIZLIK_GUNU`'nu 3 yap, `tests/test_sessizlik.py`'yi çalıştır, kırılanı oku, geri al.
