import type { Ilan } from "./tipler";

// Ekranda görünen Türkçe adlar ve şehir koordinatları (anahtarlar Python'daki internreader/isleme/sehir.py ile aynı).

export const SEVIYE_ADI: Record<string, string> = {
  staj: "Staj",
  uzun_donem_staj: "Uzun dönem staj",
  yari_zamanli: "Yarı zamanlı",
  junior: "Junior",
  yeni_mezun: "Yeni mezun",
  deneyimli: "Deneyimli",
  belirsiz: "Seviye belirsiz",
};

export const ROL_ADI: Record<string, string> = {
  yazilim: "Yazılım",
  yapay_zeka: "Yapay zekâ",
  veri: "Veri",
  diger_teknik: "Diğer mühendislik",
  teknik_degil: "Teknik değil",
};

// [boylam, enlem]
export const SEHIRLER: Record<string, { ad: string; konum: [number, number] }> = {
  istanbul: { ad: "İstanbul", konum: [28.98, 41.01] },
  ankara: { ad: "Ankara", konum: [32.85, 39.93] },
  izmir: { ad: "İzmir", konum: [27.14, 38.42] },
  kocaeli: { ad: "Kocaeli", konum: [29.92, 40.77] },
  bursa: { ad: "Bursa", konum: [29.06, 40.19] },
  eskisehir: { ad: "Eskişehir", konum: [30.52, 39.78] },
  antalya: { ad: "Antalya", konum: [30.71, 36.89] },
  konya: { ad: "Konya", konum: [32.49, 37.87] },
  kayseri: { ad: "Kayseri", konum: [35.49, 38.73] },
  adana: { ad: "Adana", konum: [35.32, 37.0] },
  gaziantep: { ad: "Gaziantep", konum: [37.38, 37.07] },
  sakarya: { ad: "Sakarya", konum: [30.4, 40.69] },
  tekirdag: { ad: "Tekirdağ", konum: [27.51, 40.98] },
  trabzon: { ad: "Trabzon", konum: [39.72, 41.0] },
  samsun: { ad: "Samsun", konum: [36.33, 41.29] },
};

export const ALAN_ADI: Record<string, string> = {
  yazilim: "Yazılım",
  yapay_zeka: "Yapay zekâ",
  veri: "Veri",
  oyun: "Oyun",
  savunma: "Savunma · siber · havacılık",
};

export const CALISMA_MODELI_ADI: Record<string, string> = {
  uzaktan: "Uzaktan",
  hibrit: "Hibrit",
  yerinde: "Ofiste",
};

// Bülten formundaki şehir seçenekleri (en çok ilan çıkan şehirler). "Uzaktan" artık çalışma modelinde seçiliyor.
export const SEHIR_SECENEKLERI = ["istanbul", "ankara", "izmir", "kocaeli", "bursa"] as const;
export const ALAN_SECENEKLERI = ["yazilim", "yapay_zeka", "veri", "oyun", "savunma"] as const;
export const CALISMA_MODELI_SECENEKLERI = ["uzaktan", "hibrit", "yerinde"] as const;
export const SEVIYE_SECENEKLERI = ["staj", "uzun_donem_staj", "yeni_mezun", "junior", "yari_zamanli"] as const;

export function sehirAdi(anahtar: string): string {
  return anahtar === "uzaktan" ? "Uzaktan" : (SEHIRLER[anahtar]?.ad ?? anahtar);
}

const AYLAR = [
  "Ocak",
  "Şubat",
  "Mart",
  "Nisan",
  "Mayıs",
  "Haziran",
  "Temmuz",
  "Ağustos",
  "Eylül",
  "Ekim",
  "Kasım",
  "Aralık",
];

/** "2026-10-18T19:52:39+03:00" → "18 Ekim, 19:52" (Türkiye saatiyle) */
export function tarihSaat(iso: string): string {
  const t = new Date(new Date(iso).getTime() + 3 * 3600_000); // Türkiye sabit UTC+3
  const saat = `${String(t.getUTCHours()).padStart(2, "0")}:${String(t.getUTCMinutes()).padStart(2, "0")}`;
  return `${t.getUTCDate()} ${AYLAR[t.getUTCMonth()]}, ${saat}`;
}

/** "2026-11-12" → "12.11.2026" */
export function noktaliTarih(tarih: string): string {
  const [yil, ay, gun] = tarih.slice(0, 10).split("-");
  return `${gun}.${ay}.${yil}`;
}

/** İlan kartının tarih satırı; internreader/yayin/__init__.py → tarih_bilgisi ile aynı (bülten de böyle yazar). */
export function tarihBilgisi(i: Ilan): string[] {
  const parcalar: string[] = [];
  if (i.surekli_acik) parcalar.push("Sürekli açık başvuru");
  else if (i.yayin) parcalar.push(`Yayın: ${noktaliTarih(i.yayin)}`);
  if (i.ayrinti?.son_basvuru) parcalar.push(`Son başvuru: ${noktaliTarih(i.ayrinti.son_basvuru)}`);
  return parcalar.length ? parcalar : ["Tarih belirtilmemiş"];
}

export const sayi = (n: number) => n.toLocaleString("tr-TR");
