# Değerlendirme seti

`siniflandirma.jsonl`: sınıflandırıcının doğruluğunu ölçmek için elle etiketlenmiş gerçek ilanlar.

- Her satır: ilan (başlık, firma, konum, açıklama) + `beklenen_seviye` ve `beklenen_rol`.
- Beklenen alan `null` ise o alan puanlanmaz (insanın da emin olamadığı örnekler).
- İlk 30 örnek 18–19 Ekim 2026'da seçildi; etiketler ilanın kendisine bakılarak verildi, modelin kararına değil.
  **Bilal gözden geçirecek ve seti 50 örneğe tamamlayacak** (özellikle zor örnekler: "Engineer II", "All Levels",
  "Associate", Türkçe "Uzman Yardımcısı", teknik olmayan stajlar).

30.10.2026'da ilk gerçek bültenin elle denetiminden 7 örnek eklendi (37 örnek): rolü başlıktan anlaşılmayan ERP/satış
stajları, gerçek yazılım stajları, Siemens öğrenci ilanları. Eski istem rol 0,973, "uygun" isabeti 0,929; yeni istem 1,0 ve 1,0.

Çalıştırma (yaklaşık 0,002 $):

    python -m internreader degerlendir

Sonuç `cikti/degerlendirme_YYYY-AA-GG.json` dosyasına da yazılır; prompt ya da model değişince eski sonuçla kıyasla.

> Not: `siniflandirma.jsonl` gerçek ilan metinleri içerdiği için repoda yok (ilan metni yayınlanmaz kuralı); yalnızca yerelde tutulur.
