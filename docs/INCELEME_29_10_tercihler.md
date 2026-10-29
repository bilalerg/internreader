# İnceleme rehberi — 29 Ekim 2026 (2): kişiye özel bülten tercihleri

Bu turda kodu ben yazdım. Senin işin: sırayla oku, her bölümün sonundaki soruyu kendi cümlenle cevapla.
Toplam ~45–60 dk. Cevaplayamadığın soru = bana sorulacak soru. (Aynı günün ilk rehberi: `INCELEME_29_10.md`.)

## Neden bu iş yapıldı? (önce bunu anla)

Vizyon "öğrenciyi Vodafone/Turkcell'e değil, yeni girişimlere yönlendirmek". Ama bülten şimdiye kadar yalnızca üç şey
soruyordu: şehir, alan (yazılım / yapay zekâ / veri), seviye. Oyun stüdyosu isteyen, savunmada çalışmak isteyen, uzaktan
çalışmak isteyen ya da yalnızca girişim görmek isteyen öğrenci bunu söyleyemiyordu.

Bu turda eklenenler:

| Tercih | Seçenekler | Boş bırakılırsa |
|---|---|---|
| Alan | yazılım, yapay zekâ, veri, **oyun**, **savunma/siber/havacılık** | hepsi |
| Çalışma modeli (yeni) | uzaktan, hibrit, yerinde (ofiste) | fark etmez |
| Yalnızca girişimler (yeni) | evet / hayır | hayır |
| Seviye | staj, uzun dönem staj, yarı zamanlı, junior, yeni mezun (değişmedi) | hepsi |
| Haftalık bülten | artık **her pazartesi 07:00** (eskiden "son bültenden 7 gün sonra") | — |

En önemli tasarım kararı: **yapay zekâya yeni soru sormadık.** Kategoriler elimizdeki bilgiden kurallarla çıkıyor
(firma etiketi, sınıflandırıcının kararı, konum, ayrıntı çıkarıcının bulduğu çalışma modeli). Maliyet değişmedi
(tavanlar aynı: çalıştırma 0,50 $, ay 2 $), değerlendirme setine dokunmak gerekmedi.

> Soru 1: "Neden yapay zekâya 'bu ilan oyun mu?' diye sormadın?" sorusuna iki gerekçeyle cevap ver.

## 1. Kavram: "çok etiketli" sınıflama

Eskiden bir ilanın tek bir "rol"ü vardı. Şimdi bir ilan **birden çok alana** girebilir: Aselsan'daki gömülü yazılım
stajı hem `yazilim` hem `savunma`; oyun şirketindeki LLM işi hem `yapay_zeka` hem `oyun`.
Abone eşleşmesi "kesişim" ile yapılır: abonenin seçtiği alanlardan **biri** ilanda varsa ilan gider.

Dosya: `internreader/isleme/kategori.py` → `alanlari_bul`. Kurallar:
- `yapay_zeka`: rol yapay zekâ **ya da** sınıflandırıcı "yapay zekâ işin özünde" (`ozunde`) dediyse. "artı" sayılmaz.
- `oyun`: firma adında games/gaming/oyun, başlıkta game/oyun/unity/unreal, ya da firma etiketi `oyun`.
- `savunma`: firma etiketi `savunma/siber/havacilik` ya da başlıkta savunma, siber, cyber, havacılık, radar...

> Soru 2: Bir öğrenci yalnızca "Yazılım"ı seçti. Dream Games'in yazılım ilanını alır mı? Neden? (İpucu: kesişim.)

## 2. Kavram: belirleyici kuralın sırası — çalışma modeli

`calisma_modeli` fonksiyonu önce **konuma** bakar (ilan sisteminin kendi alanı: "Türkiye, Remote", "Istanbul Hybrid"),
konum bir şey söylemiyorsa **ayrıntı çıkarıcının** kararını kullanır (ofis → yerinde). İkisi de yoksa `belirsiz`.
Başlığa bilerek bakılmıyor: "Hybrid App Developer" (hibrit mobil uygulama) ya da "Remote Sensing" (uzaktan algılama)
yanıltır.

Kural: abone bir çalışma modeli seçtiyse `belirsiz` ilanlar **gelmez** ("uzaktan seçen yalnız uzaktan alır").

Bir de şehirle ilgili küçük değişiklik (`internreader/bulten/secim.py`): **uzaktan ilan her şehir filtresinden geçer**
(İzmir'de oturan öğrenci uzaktan işi de yapabilir). Eski formdaki "Uzaktan" şehir seçeneği çalışma modeline taşındı;
eski aboneliklerde kayıtlıysa eskisiyle aynı sonucu verir.

> Soru 3: Bugünkü 21 ilanın 12'sinin çalışma modeli `belirsiz`. "Uzaktan" seçen bir öğrenci kaç ilan görür, bu bir
> sorun mu, nasıl iyileştirirsin?

## 3. Kavram: "girişim" ne demek? (açık kural)

`girisim_mi` sırayla bakar:
1. Firma etiketi `girisim` → evet (elle düzeltme her şeyi geçer).
2. Büyük kurum → hayır: etiket `kurumsal/banka/telekom`; ilan Workday, SuccessFactors, Avature, Oracle, Taleo gibi
   kurumsal bir sistemden geliyor; ya da firma `BUYUK_KURUMLAR` listesinde (Aselsan, Turkcell, Trendyol, bankalar,
   üniversiteler...).
3. Girişim ekosistemi → evet: firma `turkiye.ai` (yapay zekâ girişim haritası), teknopark listeleri
   (`teknopark_istanbul`, `budotek`, `dijitalpark`, `tpi`) ya da `ats_genis` listesinden gelip ilanını Lever, Ashby,
   Greenhouse, Workable, Recruitee gibi girişimlerin kullandığı bir sistemden yayınlıyor.
4. Gerisi → hayır.

Neden `ats_genis` tek başına yetmiyor? Ölçtüm: o listede Uber, Delivery Hero, Mercedes-Benz Türk de var. Kuralla
1.304 firmanın 785'i girişim sayılıyor. Kural kusursuz değil: yanlış firma `veri/firmalar.csv`'de `girisim` ya da
`kurumsal` etiketiyle düzeltilir (sonra `python -m internreader ice-aktar veri/firmalar.csv`).

> Soru 4: Neden "kurumsal ilan sistemi" (Workday) girişim olmamanın işareti? Bir karşı örnek düşünebilir misin?

## 4. Haftalık bülten = pazartesi

`internreader/depo/bulten.py` → `gonderime_hazir_aboneler`. Haftalık abone, Türkiye saatiyle **pazartesi** olan
çalıştırmada hazırdır (GitHub Actions 04:00 UTC = 07:00 TR). Aynı pazartesi elle ikinci kez çalıştırırsan haftalık
aboneye ikinci e-posta gitmez (`son_bulten` bugün mü diye bakılır). Günlük aboneler değişmedi.
Zaman dilimine dikkat: pazar 22:00 UTC, Türkiye'de pazartesi 01:00'dir (`test_haftalik_gun_turkiye_saatine_gore`).

## 5. Veri yolu: ilan nereden kategorisini alıyor?

`depo/ilanlar.py` → `yayinlanacak_ilanlar` her ilana üç alan ekler: `alanlar`, `calisma_modeli`, `girisim`.
Firma etiketi ve listeleri `_firma_profilleri` ile firma adından bulunur. Bu üç alan `ilanlar.json`'a da yazılır
(alan **eklemek** sözleşmede sürüm artırmaz); sitedeki önizleme (`web/src/components/Bulten.tsx` → `eslesir`) aynı
kuralı bu hazır alanlarla uygular. Eski JSON'da alanlar yoksa site `alanlar = [rol]`, model `belirsiz` sayar.

Veritabanı şeması değişmedi: tercihler zaten JSON sütununda (`aboneler.tercihler`), yeni anahtarlar oraya yazılıyor.
Bu yüzden göç (alembic) gerekmedi. Eksik anahtar = "hepsi": eski aboneler eskisi gibi her şeyi alır.
KVKK metnine yeni tercihler eklendi, `KVKK_SURUMU` 2026-10-29'a çıktı.

## 6. Testler: "matris" testi

`tests/test_tercihler.py` → `test_her_abone_yalnizca_tercihine_uyan_ilanlari_alir`. 7 ilan (AI girişimi, banka veri
stajı, oyun stüdyosu, Aselsan, uzaktan Sezzle, teknoparkta siber stajı, uzaktan LLM işi) ve 17 abone kurar, bülteni
gönderir, her abonenin aldığı ilanları **elle yazılmış** beklenen kümeyle karşılaştırır. Beklenen küme koddan
hesaplansaydı, kural yanlışken test de yanlış olup yine geçerdi.

```bash
.venv/Scripts/python -m pytest -q tests/test_tercihler.py tests/test_bulten.py
```

Bir kuralı bilerek boz (ör. `secim.py`'de `or uzak` kısmını sil), testi çalıştır, hangi abonenin neden kırıldığını oku,
geri al.

> Soru 5: `test_matriste_gunluk_sinir_ve_adil_sira_bozulmaz` neyi korur? E-posta sınırı 5 iken 16 abone varsa ne olur?

## Bugünkü arz (canlı ilanlar.json, 29.10, 21 ilan)

| Kategori | İlan | Not |
|---|---|---|
| Yazılım | 19 | arzın neredeyse tamamı |
| Oyun | 4 | yalnızca Dream Games ve Good Job Games |
| Savunma | 2 | ikisi de firma etiketinden (Mavvo ERP, Türk SEM) — gerçek savunma yazılımı değil |
| Yapay zekâ | 1 | Yeditek görüntü işleme |
| Veri | 1 | Obilet |
| Girişim | 10 | yarısı |
| Uzaktan / hibrit / yerinde / belirsiz | 4 / 1 / 4 / 12 | model çoğunlukla yazmıyor |

Zayıf alanlar: yapay zekâ, veri, savunma. Kaynak genişletme aşamasında öncelik bunlar olmalı.

## 7. Ek: bayat ilan denetimi (ilan güncelliği)

**Kavram.** "Sayfa hâlâ duruyor" ile "ilan açık" aynı şey değil. Yeditek'in 08 Mayıs 2023 tarihli staj ilanı, sayfası
silinmediği için yayındaydı. Kariyer sayfası ilanlarında ilan sistemi (ATS) gibi tarih alanı yok; tarih yalnızca metinde.

**Sinyaller ve kurallar** — `internreader/isleme/guncellik.py` (dosyanın başındaki açıklamayı oku):
- `ilan_tarihi`: ayrıntı çıkarıcı metinde yazan yayın tarihini bulur. **Uydurma koruması:** kod metindeki bütün
  tarihleri kendisi bulur (`metindeki_tarihler`: "08 Mayıs 2023", "08.05.2023", "May 8, 2023"...); modelin tarihi bu
  kümede yoksa ya da gelecekteyse atılır.
- Dönem yılları ("2025 Yaz Stajı", "2024-2025 dönemi") yapay zekâsız, düzenli ifadeyle bulunur. "2015'te kurulduk" ve
  "2026 mezunları" sayılmaz.
- Kaldırma: son başvuru geçmiş → her kaynakta; kariyer sayfası ilanında ilan tarihi 180 günden eski ya da bütün dönem
  yılları geçmiş (ileri bir son başvuru yoksa). ATS ilanı bu ikisiyle kalkmaz; 365 günden eskiyse kartta eski yıl yerine
  "Sürekli açık başvuru" yazar (Dream Games'in 2022'den beri açık ilanları).
- Kartta (site ve bülten aynı): "Yayın: GG.AA.YYYY", "Son başvuru: GG.AA.YYYY" ya da "Tarih belirtilmemiş"
  (`yayin/__init__.py` → `tarih_bilgisi`, sitede `etiketler.ts` → `tarihBilgisi`).

**Metin nereden geliyor?** `boru.py` → `ayrintilari_zenginlestir`. İlanın kendi sayfası varsa o okunur (zaten vardı).
Yeni: adresi `#` ile biten ilanlar (birçok ilan tek sayfada) için o sayfadan yalnızca ilanın bölümü kesilir
(`kaynaklar/kariyer_sayfasi.py` → `ilan_bolumu`: başlıktan bir sonraki ilan başlığına kadar). Aynı sayfa bir kez
indirilir, robots.txt'ye uyulur.

**Eski kayıtlar.** Göç `0003` ayrıntılara `ilan_tarihi`, `donem_yili`, `surum` ekler. Eski kayıtlar sürüm 1'dir;
tarihsiz kariyer sayfası ilanları ve tarihsiz ATS ilanları bir sonraki sabah işinde **bir kez** yeniden çıkarılır
(`depo/ayrintilar.py` → `ayrinti_bekleyenler`). 29.10 verisinde ~10 çağrı ≈ 0,004 $ (Haiku, ilan başına ~0,0004 $).

**29.10 etkisi (yapay zekâsız tahmin, 21 ilan):** 1 ilan düşer (Yeditek), 2 ilan "Sürekli açık başvuru" olur
(Dream Games), 18 ilan kalır; tarih alanı olmayan 8 kariyer sayfası ilanından 7'sinde metinde tarih yok.

> Soru 6: Model, tarihi olmayan bir metne "2026-10-01" yazarsa hangi satır onu atar? Testi bul
> (`tests/test_guncellik.py` → `test_uydurma_ilan_tarihi_reddedilir`) ve bilerek boz.

## Mülakat cümlesi

> "Bülteni kişiye özel yaptım: alan, çalışma modeli ve yalnızca girişimler. Kategorileri yapay zekâya yeni soru
> sormadan, elimdeki firma etiketleri ve sınıflandırıcı kararından kurallarla çıkardım; maliyet sıfır arttı.
> Doğruluğu 17 farklı tercih profilinin her birinin yalnızca kendi ilanlarını aldığını gösteren bir matris testiyle
> kanıtladım."
