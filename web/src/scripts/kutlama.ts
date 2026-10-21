// Kısa kutlama: kayıt isteği alındığında ve abonelik onaylandığında iki yandan konfeti. Renkler temadan okunur
// (gece modunda da uyumlu). Yalnızca o anda yüklenir (dinamik import); "hareketi azalt" tercihinde çalışmaz.
import confetti from "canvas-confetti";

export function kutla() {
  const stil = getComputedStyle(document.documentElement);
  // canvas-confetti yalnızca #rrggbb anlar; rgba gibi değerler yanlış renge (pembe) dönüşüyordu
  const renkler = ["--fosfor", "--murekkep", "--murekkep-2"]
    .map((ad) => stil.getPropertyValue(ad).trim())
    .filter((r) => /^#[0-9a-f]{6}$/i.test(r));
  if (renkler.length === 0) renkler.push("#ecdb3d", "#16171a");
  const ortak = { colors: renkler, disableForReducedMotion: true, ticks: 220, scalar: 0.9, zIndex: 60 };
  confetti({ ...ortak, particleCount: 60, spread: 65, angle: 60, origin: { x: 0, y: 0.75 } });
  confetti({ ...ortak, particleCount: 60, spread: 65, angle: 120, origin: { x: 1, y: 0.75 } });
}
