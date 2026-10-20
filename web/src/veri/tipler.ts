// Python tarafının ürettiği herkese açık JSON dosyalarının tipleri (cikti/ilanlar.json, cikti/istatistik.json).
// Sözleşme: alan kaldırmak "surum"u artırır, alan eklemek artırmaz. Değişiklik internreader/yayin/ ile birlikte yapılır.

export type Seviye = "staj" | "uzun_donem_staj" | "yari_zamanli" | "junior" | "yeni_mezun";
export type Rol = "yazilim" | "yapay_zeka" | "veri";
export type YapayZeka = "ozunde" | "arti" | "yok";

/** Yapay zekânın ilan metninden çıkardığı, koddaki denetimden geçmiş bilgiler (yalnızca öğrenciye uygun ilanlarda). */
export interface IlanAyrintisi {
  ozet: string; // boş olabilir: metinde işin ne olduğu yazmıyorsa
  son_basvuru: string | null; // YYYY-AA-GG
  hedef: string | null;
  calisma_modeli: "ofis" | "hibrit" | "uzaktan" | "belirsiz";
  ucretli: "evet" | "hayir" | "belirsiz";
  teknolojiler: string[];
}

export interface Ilan {
  kimlik: string;
  firma: string;
  firma_gorunen: string;
  baslik: string;
  url: string;
  konum: string;
  kaynak: string;
  yayin_tarihi: string;
  ilk_gorulme: string;
  seviye: Seviye;
  rol: Rol;
  yapay_zeka: YapayZeka;
  sehirler: string[];
  uzaktan: boolean;
  ayrinti?: IlanAyrintisi | null; // eski JSON'da yok
}

export interface IlanListesi {
  surum: number;
  guncelleme: string;
  sayi: number;
  ilanlar: Ilan[];
}

export interface Karar {
  baslik: string;
  firma: string;
  seviye: string;
  rol: string;
  gerekce: string;
  uygun: boolean;
}

export interface Istatistik {
  surum: number;
  guncelleme: string;
  takip_edilen_firma: number; // listedeki tüm firmalar (ayda bir keşif)
  taranan_firma: number; // ilan sayfası bilinen, her sabah okunanlar
  aktif_ilan: number;
  ogrenci_ilani: number;
  sehirler: Record<string, number>;
  firmalar: string[];
  kararlar: Karar[];
}
