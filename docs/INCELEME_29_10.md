# İnceleme rehberi — 29 Ekim 2026: kapsam genişletme

Bu turda kodu ben yazdım. Senin işin: aşağıdaki sırayla oku, her bölümün sonundaki soruyu kendi cümlenle cevapla.
Toplam ~60–90 dk. Cevaplayamadığın soru = bana sorulacak soru.

## Neden bu iş yapıldı? (önce bunu anla)

28.10'da LinkedIn'de gördüğümüz 3 gerçek ilanın (Siemens, Kaizen Loyalty, Playable Factory) **hiçbiri** InternReader'da
yoktu. Teşhis (ölçerek, tahminle değil):

| Bulgu | Sayı |
|---|---|
| Listedeki firma | 1.304 |
| İlan sistemi (ATS) bilinen | 42 |
| Kariyer sayfası bilinen | 278 |
| **İkisi de bilinmeyen (hiç okunmayan)** | **986** |
| Web adresi bile olmayan (yalnızca adı var) | 291 |

- Siemens: listede yalnızca adı vardı → hiç okunmuyordu. Kariyer sitesi **Avature** adlı bir sistemde.
- P.I. Works: web adresi vardı ama ilanları **BambooHR**'da; keşif BambooHR'ı tanımıyordu.
- Kaizen, Playable, Nephos: ilanlarını **yalnızca LinkedIn'de** yayınlıyorlar → kuralımız gereği alamayız (bu bir sınır,
  hata değil).

Üç çözüm yazıldı: (1) yeni ilan sistemleri, (2) arama motoruyla firma keşfi, (3) canlı öncesi zorunlular.

> Soru 1: "986 firma hiç okunmuyordu" cümlesini bir mülakatta nasıl anlatırsın? Hangi ölçümle buldun?

## 1. Yeni ilan sistemleri — `internreader/kaynaklar/ats.py`

Oku: `bamboohr_ayristir`, `teamtailor_ayristir`, `personio_ayristir`, `avature_ayristir`, sonra en alttaki `avature` ve
`TOPLAYICILAR`.

**Kavram — ayrıştırıcı ile toplayıcıyı ayırmak:** `*_ayristir` fonksiyonları ağa çıkmaz; JSON/XML metni alır, `Ilan`
listesi döndürür. Toplayıcı (`bamboohr`, `avature`...) yalnızca isteği atar ve ayrıştırıcıya verir. Böylece testler
internete çıkmadan örnek veriyle çalışır (`tests/test_ats.py`).

**Kavram — JSON API ve RSS/XML:** BambooHR JSON verir (`json_al`). Teamtailor, Personio ve Avature XML akışı verir;
XML'i `xml.etree.ElementTree` ile okuyoruz (`ET.fromstring`, `.iter("item")`, `.findtext("title")`).

**Avature'ın iki tuhaflığı (ölçüldü):** akış her aramada en fazla 20 ilan veriyor ve sayfalamayı yok sayıyor → 5 farklı
arama yapıp birleştiriyoruz, aynı ilanı **kimliğiyle** (adresin son parçası) tekilleştiriyoruz. Akıştaki tarih yanlış
(27.10'da açılan ilanda 2023 yazıyor) → tarihi hiç yazmıyoruz. Yanlış veri, boş veriden kötüdür.

> Soru 2: Avature'da aynı ilan neden iki kez gelebilir, kod bunu nasıl engelliyor? (`kimlik` satırı)

## 2. Keşif desenleri — `internreader/kesif.py`

Oku: `ATS_DESENLERI` (en alttaki 4 yeni satır), `sayfadan_ats_bul`, `KARIYER_LINKI`.

**Kavram — düzenli ifade (regex) ile bağlantıdan sistem tanımak:** firmanın sitesindeki
`https://piworks.bamboohr.com/careers` bağlantısı → `("bamboohr", "piworks")`. Avature şirketin kendi alan adında çalıştığı
için kısa ad yerine `"jobs.siemens.com|en_US/externaljobs"` tutuluyor.

**Küçük düzeltme:** Kaizen'in sayfası `/why-join-us`; eski desen yalnızca `/join-us`'ı tanıyordu. Şimdi kısa bir ön ek
kabul ediliyor. `tests/test_kesif.py` → `test_on_ekli_kariyer_baglantisi_bulunur`.

> Soru 3: `www.bamboohr.com` bağlantısı neden pano sayılmıyor? (`GECERSIZ_SLUG`)

## 3. Arama keşfi ("Google taraması") — `internreader/arama.py` (en önemli dosya)

Sırayla oku: modülün başındaki açıklama → `sorgular` → `SIRKET_DEGIL` → `adaylari_ayir` → `turkiye_panosu_mu` →
`arama_kesfi` → `web_adresi_bul`.

**Akış:**
1. `site:jobs.lever.co Istanbul` gibi 24 ATS sorgusu + 8 genel sorgu ("yazılım stajyeri İstanbul kariyer").
2. Sonuçlardan **ilan siteleri en başta atılır** (LinkedIn, Kariyer.net, Youthall...): adresleri hiç açılmaz.
3. Adres bir ATS panosuysa → pano **doğrulanır** (en az bir ilanı Türkiye'de mi?) → firma taranabilir hâlde eklenir.
   Dünyada aynı kısa adı kullanan başka firmayı eklememek için bu doğrulama şart (`test_..._dunya`).
4. Değilse şirket sitesidir → web adresiyle eklenir → mevcut keşif kariyer sayfasını bulur.
5. Listede zaten web adresiyle duran firmanın panosu bulunursa yeni firma açılmaz, pano o firmaya yazılır
   (P.I. Works ↔ piworks.bamboohr.com). Çift kayıt önlenir.

**Kavram — sağlayıcı soyutlaması:** `ara()` Serper ya da Brave'e gider; geri kalan kod hangisi olduğunu bilmez.
Anahtar `.env`'den okunur, başlıkta gönderilir, hiçbir yerde yazdırılmaz (`ayar.py` → `repr=False`).

**Kavram — kota koruması:** 401/403 (geçersiz anahtar) gelirse kalan sorgular atılmaz. Web adresi bulunamayan firma 90 gün
tekrar sorgulanmaz (`YENIDEN_DENEME_GUNU`).

**Kavram — kuru çalıştırma:** `--kuru` hiçbir şey yazmadan ne bulacağını gösterir. Gerçek veriye dokunan her komutta
iyi bir alışkanlık.

> Soru 4: Arama sonucunda `tr.linkedin.com/jobs/view/...` çıkarsa ne olur? Hangi satır, neden?
> Soru 5: `ad_alanla_uyusuyor_mu("Nova Spark X Teknoloji", "patika.dev")` neden `False` olmalı?

## 4. Canlı öncesi zorunlular

- **Kişisel veri maskeleme** — `internreader/isleme/maske.py`, uygulandığı yer `depo/ilanlar.py` (`kisisel_veriyi_maskele`).
  İlan metnindeki kişisel e-posta ve telefon veritabanına yazılmadan maskelenir; `ik@`, `careers@` gibi kurumsal adresler
  korunur. Neden: KVKK'nın "en az veri" ilkesi; bu verilere ihtiyacımız yok.
- **"İlanımı kaldır"** — sitenin alt bilgisinde satır (`web/src/layouts/Taban.astro`), README'de satır,
  komut: `python -m internreader firma-kapat "Firma"` (`depo/firmalar.py` → `firmayi_kapat`). Kayıt silinmez, `aktif=False`
  olur; liste yeniden içe aktarılsa da geri gelmez (`tests/test_firma_kapat.py`).

> Soru 6: Firmayı silmek yerine neden `aktif=False` yapıyoruz?

## Kendin çalıştır (15 dk)

```bash
.venv/Scripts/python -m pytest -q tests/test_arama.py tests/test_ats.py tests/test_maske.py
.venv/Scripts/python -X utf8 -m internreader arama-kesif --kuru   # anahtar yoksa "anahtar-yok" der; bu da doğru davranış
.venv/Scripts/python -X utf8 -m internreader durum
```

Bir testi bilerek boz (ör. `maske.py`'de `ROL_ADRESI`'nden `ik`'yı sil), testi çalıştır, hangi testin neden kırıldığını
oku, geri al. Kodun nasıl korunduğunu en hızlı böyle öğrenirsin.

## Mülakat cümlesi

> "Kapsamı ölçtüm: 1.300 firmanın 986'sı hiç okunmuyordu ve aradığım gerçek ilanların hiçbiri sistemde yoktu.
> Dört yeni ilan sistemi okuyucusu ve arama API'siyle firma keşfi ekledim; her adayı Türkiye ilanı var mı diye
> doğrulayıp ekliyorum. Sonuç: [sayı] → [sayı] ilan."
