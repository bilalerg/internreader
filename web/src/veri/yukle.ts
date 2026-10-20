// Derleme sırasında (sunucu tarafı) veriyi okur. Sıra: INTERNREADER_CIKTI ortam değişkeni → ../cikti → örnek veri.
// Örnek veri depoda durur; böylece CI'da ya da veritabanı olmayan bir bilgisayarda da site derlenebilir.
// Tarayıcıda adalar (island) her açılışta /veri/*.json'u tekrar okur: sunucuda her sabah güncellenen dosyalar.

import fs from "node:fs";
import path from "node:path";
import type { IlanListesi, Istatistik } from "./tipler";

const ADAYLAR = [
  process.env.INTERNREADER_CIKTI,
  path.resolve(process.cwd(), "../cikti"),
  path.resolve(process.cwd(), "src/veri/ornek"),
].filter((d): d is string => Boolean(d));

function oku<T>(dosya: string): T {
  for (const dizin of ADAYLAR) {
    const yol = path.join(dizin, dosya);
    if (fs.existsSync(yol)) return JSON.parse(fs.readFileSync(yol, "utf-8")) as T;
  }
  throw new Error(`${dosya} bulunamadı (${ADAYLAR.join(", ")})`);
}

export const istatistikOku = () => oku<Istatistik>("istatistik.json");
export const ilanlariOku = () => oku<IlanListesi>("ilanlar.json");
