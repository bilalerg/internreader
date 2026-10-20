// Türkiye nokta haritası: derleme sırasında gerçek ülke sınırından (Natural Earth, world-atlas) hesaplanır.
// Tarayıcıya yalnızca noktaların koordinatları gider (birkaç KB); harita kütüphanesi istemciye yüklenmez.

import fs from "node:fs";
import { createRequire } from "node:module";
import { geoContains, geoMercator } from "d3-geo";
import type { Feature, Geometry } from "geojson";
import { feature } from "topojson-client";
import type { GeometryCollection, Topology } from "topojson-specification";
import { SEHIRLER } from "./etiketler";

const TURKIYE_KODU = "792"; // ISO 3166-1 sayısal

export interface HaritaVerisi {
  genislik: number;
  yukseklik: number;
  noktalar: number[]; // [x0, y0, x1, y1, ...]
  sehirler: { anahtar: string; ad: string; x: number; y: number; sayi: number }[];
}

export function turkiyeHaritasi(sehirSayilari: Record<string, number>, genislik = 960, aralik = 11): HaritaVerisi {
  const require = createRequire(import.meta.url);
  const topoloji = JSON.parse(fs.readFileSync(require.resolve("world-atlas/countries-50m.json"), "utf-8")) as Topology;
  const ulkeler = feature(topoloji, topoloji.objects.countries as GeometryCollection) as unknown as {
    features: Feature<Geometry>[];
  };
  const turkiye = ulkeler.features.find((f) => String(f.id) === TURKIYE_KODU);
  if (!turkiye) throw new Error("Türkiye sınırı bulunamadı");

  // Önce genişliğe göre ölçekle, yüksekliği ülkenin oranından hesapla
  const deneme = geoMercator().fitWidth(genislik, turkiye);
  const [[, y0], [, y1]] = [deneme([26, 42.2])!, deneme([26, 35.7])!];
  const yukseklik = Math.ceil(y1 - y0) + aralik * 2;
  const izdusum = geoMercator().fitExtent(
    [
      [aralik, aralik],
      [genislik - aralik, yukseklik - aralik],
    ],
    turkiye,
  );

  const noktalar: number[] = [];
  for (let y = aralik / 2; y < yukseklik; y += aralik) {
    // Satırları yarım aralık kaydırarak (altıgen düzen) daha doğal bir doku
    const kayma = (Math.round(y / aralik) % 2) * (aralik / 2);
    for (let x = aralik / 2 + kayma; x < genislik; x += aralik) {
      const yer = izdusum.invert?.([x, y]);
      if (yer && geoContains(turkiye, yer)) noktalar.push(Math.round(x * 10) / 10, Math.round(y * 10) / 10);
    }
  }

  const sehirler = Object.entries(SEHIRLER).map(([anahtar, { ad, konum }]) => {
    const [x, y] = izdusum(konum)!;
    return { anahtar, ad, x: Math.round(x), y: Math.round(y), sayi: sehirSayilari[anahtar] ?? 0 };
  });

  return { genislik, yukseklik, noktalar, sehirler };
}
