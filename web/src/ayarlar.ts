// Sitenin değişebilen bilgileri tek yerde. Yayından önce boş olanlar doldurulmalı (bkz. README → Yayına hazırlık).

export const SITE = {
  ad: "InternReader",
  // Konum cümlesi (18.10.2026): rakiplerden farkımız teknoloji odağı + yapay zekâ okuyucu + kişiye özel sabah e-postası
  aciklama:
    "Yazılım, yapay zekâ ve veri stajları: şirketlerin kendi sayfalarından yapay zekâyla okunur, öğrenciye uygun olanlar her sabah e-postana gelir. Ücretsiz.",
  githubAdresi: "https://github.com/bilalerg/internreader",
  whatsappKanali: "", // kanal açılınca davet bağlantısı buraya
  iletisimEpostasi: "iletisim@internreader.me", // KVKK başvuruları ve geri bildirim için (yayından önce zorunlu)
  veriSorumlusu: "Bilal Eroğlu", // KVKK: veri sorumlusunun adı soyadı (yayından önce zorunlu)
  kvkkSurumu: "2026-10-29", // internreader/abonelik.py → KVKK_SURUMU ile aynı olmalı
};
