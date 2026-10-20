# Değerlendirme seti

`siniflandirma.jsonl`: sınıflandırıcının doğruluğunu ölçmek için elle etiketlenmiş gerçek ilanlar.

- Her satır: ilan (başlık, firma, konum, açıklama) + `beklenen_seviye` ve `beklenen_rol`.
- Beklenen alan `null` ise o alan puanlanmaz (insanın da emin olamadığı örnekler).
- İlk 30 örnek 18–19 Ekim 2026'da seçildi; etiketler ilanın kendisine bakılarak verildi, modelin kararına değil.
  **Bilal gözden geçirecek ve seti 50 örneğe tamamlayacak** (özellikle zor örnekler: "Engineer II", "All Levels",
  "Associate", Türkçe "Uzman Yardımcısı", teknik olmayan stajlar).

Çalıştırma (yaklaşık 0,002 $):

    python -m internreader degerlendir

Sonuç `cikti/degerlendirme_YYYY-AA-GG.json` dosyasına da yazılır; prompt ya da model değişince eski sonuçla kıyasla.

> Not: `siniflandirma.jsonl` gerçek ilan metinleri içerdiği için repoda yok (ilan metni yayınlanmaz kuralı); yalnızca yerelde tutulur.
