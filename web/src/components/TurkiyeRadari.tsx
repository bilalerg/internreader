import { useEffect, useMemo, useRef, useState } from "react";
import type { HaritaVerisi } from "../veri/harita";
import { sayi } from "../veri/etiketler";

// Hero simülasyonu: bir "okuma çizgisi" Türkiye'yi batıdan doğuya tarar. Geçtiği noktalar yanar, şehirler
// gerçek ilan sayılarıyla orantılı nabız atar, öğrenci ilanı olan şehirde gerçek bir ilan etiketi belirir.
// Canvas: ~1.800 nokta her karede çizilir; ekranda değilken ve sekme gizliyken durur.

export interface OrnekIlan {
  baslik: string;
  firma: string;
  seviye: string;
  sehir: string;
}

interface Props {
  harita: HaritaVerisi;
  ornekler: OrnekIlan[];
  toplam: { firma: number; ilan: number; ogrenci: number };
  gun: string; // "18 Ekim"
}

interface Etiket {
  kimlik: number;
  x: number;
  y: number;
  ilan: OrnekIlan;
}

const TARAMA_MS = 7200;
const BEKLEME_MS = 1400;
const ETIKET_MS = 3800;

function renkleriOku() {
  const s = getComputedStyle(document.documentElement);
  const al = (ad: string) => s.getPropertyValue(ad).trim();
  return { murekkep: al("--murekkep"), fosfor: al("--fosfor"), murekkep3: al("--murekkep-3") };
}

export default function TurkiyeRadari({ harita, ornekler, toplam, gun }: Props) {
  const kapRef = useRef<HTMLDivElement>(null);
  const tuvalRef = useRef<HTMLCanvasElement>(null);
  // 0..1, sayaçlar için. 1 ile başlar: sunucu çıktısında (arama motoru, JS kapalı) gerçek sayılar görünür
  const [ilerleme, setIlerleme] = useState(1);
  const [etiketler, setEtiketler] = useState<Etiket[]>([]);
  const [hareketsiz, setHareketsiz] = useState(false);
  const [yakinSehir, setYakinSehir] = useState<HaritaVerisi["sehirler"][number] | null>(null);

  // Şehre göre öğrenci ilanları (etiketlerde sırayla gösterilir)
  const sehirIlanlari = useMemo(() => {
    const m = new Map<string, OrnekIlan[]>();
    for (const o of ornekler) m.set(o.sehir, [...(m.get(o.sehir) ?? []), o]);
    return m;
  }, [ornekler]);

  useEffect(() => {
    const kap = kapRef.current!;
    const tuval = tuvalRef.current!;
    const ctx = tuval.getContext("2d")!;
    const azalt = matchMedia("(prefers-reduced-motion: reduce)").matches;
    setHareketsiz(azalt);

    const n = harita.noktalar.length / 2;
    const parlaklik = new Float32Array(n);
    const enBuyuk = Math.max(1, ...harita.sehirler.map((s) => s.sayi));
    const nabizlar: { x: number; y: number; r: number; baslangic: number }[] = [];
    const siradaki = new Map<string, number>(); // şehir başına hangi ilanın gösterileceği
    let renk = renkleriOku();
    let olcek = 1;
    let dar = false;
    let kare = 0;
    let gorunur = true;
    let dongu = performance.now();
    let oncekiX = -1;
    let etiketNo = 0;
    // İmleç merceği: imlecin altındaki noktalar yanar ve hafifçe kenara itilir (yalnızca fare olan cihazlar)
    const imlec = { x: 0, y: 0, aktif: false };
    const MERCEK = 64; // harita biriminde yarıçap
    const fareVar = matchMedia("(hover: hover) and (pointer: fine)").matches;
    let yakinSehirAnahtari = "";

    const boyutla = () => {
      const genislik = kap.clientWidth;
      const yukseklik = (genislik * harita.yukseklik) / harita.genislik;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      tuval.width = Math.round(genislik * dpr);
      tuval.height = Math.round(yukseklik * dpr);
      olcek = genislik / harita.genislik;
      dar = genislik < 480;
      ctx.setTransform(dpr * olcek, 0, 0, dpr * olcek, 0, 0);
    };

    const ciz = (an: number, taramaX: number | null) => {
      ctx.clearRect(0, 0, harita.genislik, harita.yukseklik);
      // Okuma çizgisinin arkasındaki fosfor ışığı
      if (taramaX !== null) {
        const isik = ctx.createLinearGradient(taramaX - 70, 0, taramaX + 6, 0);
        isik.addColorStop(0, "transparent");
        isik.addColorStop(1, renk.fosfor);
        ctx.globalAlpha = 0.22;
        ctx.fillStyle = isik;
        ctx.fillRect(taramaX - 70, 0, 76, harita.yukseklik);
        ctx.globalAlpha = 1;
      }
      // Noktalar
      for (let i = 0; i < n; i++) {
        let x = harita.noktalar[i * 2];
        let y = harita.noktalar[i * 2 + 1];
        if (taramaX !== null && Math.abs(x - taramaX) < 7) parlaklik[i] = 1;
        let b = parlaklik[i];
        if (imlec.aktif) {
          const dx = x - imlec.x;
          const dy = y - imlec.y;
          const d = Math.hypot(dx, dy);
          if (d < MERCEK) {
            const f = 1 - d / MERCEK;
            b = Math.max(b, f * 0.95);
            if (d > 0.01) {
              x += (dx / d) * f * f * 9; // merceğin kenarına doğru itilir: "büyüteç" hissi
              y += (dy / d) * f * f * 9;
            }
          }
        }
        ctx.globalAlpha = 0.27 + b * 0.55;
        ctx.fillStyle = b > 0.35 ? renk.fosfor : renk.murekkep;
        ctx.beginPath();
        ctx.arc(x, y, 1.7 + b * 0.9, 0, Math.PI * 2);
        ctx.fill();
        parlaklik[i] *= 0.955; // yalnızca taramanın bıraktığı iz söner; mercek etkisi her karede yeniden hesaplanır
      }
      // Şehir nabızları
      for (let k = nabizlar.length - 1; k >= 0; k--) {
        const p = nabizlar[k];
        const t = (an - p.baslangic) / 1700;
        if (t >= 1) {
          nabizlar.splice(k, 1);
          continue;
        }
        ctx.globalAlpha = (1 - t) * 0.7;
        ctx.strokeStyle = renk.murekkep;
        ctx.lineWidth = 1.2 / olcek;
        ctx.beginPath();
        ctx.arc(p.x, p.y, 4 + t * p.r, 0, Math.PI * 2);
        ctx.stroke();
      }
      // Şehir işaretleri (ilan sayısına göre boyut)
      ctx.globalAlpha = 1;
      for (const s of harita.sehirler) {
        if (!s.sayi) continue;
        const r = 2.6 + 5 * Math.sqrt(s.sayi / enBuyuk);
        ctx.fillStyle = renk.murekkep;
        ctx.beginPath();
        ctx.arc(s.x, s.y, r, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = renk.fosfor;
        ctx.beginPath();
        ctx.arc(s.x, s.y, r * 0.42, 0, Math.PI * 2);
        ctx.fill();
      }
      // Mercek halkası
      if (imlec.aktif) {
        ctx.globalAlpha = 0.4;
        ctx.strokeStyle = renk.murekkep;
        ctx.lineWidth = 1 / olcek;
        ctx.beginPath();
        ctx.arc(imlec.x, imlec.y, MERCEK * 0.92, 0, Math.PI * 2);
        ctx.stroke();
        ctx.globalAlpha = 1;
      }
      // Okuma çizgisi
      if (taramaX !== null) {
        ctx.globalAlpha = 0.55;
        ctx.fillStyle = renk.murekkep;
        ctx.fillRect(taramaX, 0, 1.2 / olcek, harita.yukseklik);
        ctx.globalAlpha = 1;
      }
    };

    const sehreUlasti = (an: number, s: HaritaVerisi["sehirler"][number]) => {
      if (!s.sayi) return;
      nabizlar.push({ x: s.x, y: s.y, r: 14 + 46 * Math.sqrt(s.sayi / enBuyuk), baslangic: an });
      const liste = sehirIlanlari.get(s.anahtar);
      if (!liste?.length) return;
      const sira = siradaki.get(s.anahtar) ?? 0;
      siradaki.set(s.anahtar, sira + 1);
      const etiket = { kimlik: ++etiketNo, x: s.x, y: s.y, ilan: liste[sira % liste.length] };
      // Geniş ekranda en fazla iki, telefonda tek etiket (küçük haritayı kapatmasın)
      setEtiketler((e) => (dar ? [etiket] : [...e.slice(-1), etiket]));
      window.setTimeout(() => setEtiketler((e) => e.filter((x) => x.kimlik !== etiket.kimlik)), ETIKET_MS);
    };

    const adim = (an: number) => {
      kare = requestAnimationFrame(adim);
      if (!gorunur || document.hidden) {
        dongu = an - (oncekiX > 0 ? (oncekiX / harita.genislik) * TARAMA_MS : 0);
        return;
      }
      const gecen = an - dongu;
      if (gecen > TARAMA_MS + BEKLEME_MS) {
        dongu = an;
        oncekiX = -1;
        return;
      }
      const t = Math.min(1, gecen / TARAMA_MS);
      const taramaX = gecen <= TARAMA_MS ? t * harita.genislik : null;
      if (taramaX !== null) {
        for (const s of harita.sehirler) if (oncekiX < s.x && s.x <= taramaX) sehreUlasti(an, s);
        oncekiX = taramaX;
      }
      setIlerleme(Math.round(t * 100) / 100); // aynı değerde React yeniden çizmez: tarama başına ~100 güncelleme
      ciz(an, taramaX);
    };

    boyutla();

    const fareHareket = (o: PointerEvent) => {
      const r = kap.getBoundingClientRect();
      imlec.x = ((o.clientX - r.left) / r.width) * harita.genislik;
      imlec.y = ((o.clientY - r.top) / r.height) * harita.yukseklik;
      imlec.aktif = true;
      // İlanı olan en yakın şehir imlece yakınsa bilgi kutusu (React yalnızca şehir değişince yeniden çizer)
      let enYakin: HaritaVerisi["sehirler"][number] | null = null;
      let enKisa = 28;
      for (const s of harita.sehirler) {
        const d = Math.hypot(s.x - imlec.x, s.y - imlec.y);
        if (s.sayi && d < enKisa) [enKisa, enYakin] = [d, s];
      }
      if ((enYakin?.anahtar ?? "") !== yakinSehirAnahtari) {
        yakinSehirAnahtari = enYakin?.anahtar ?? "";
        setYakinSehir(enYakin);
      }
      if (azalt) requestAnimationFrame(() => ciz(performance.now(), null));
    };
    const fareCikti = () => {
      imlec.aktif = false;
      yakinSehirAnahtari = "";
      setYakinSehir(null);
      if (azalt) ciz(performance.now(), null);
    };
    const tikla = () => {
      if (imlec.aktif) nabizlar.push({ x: imlec.x, y: imlec.y, r: 80, baslangic: performance.now() });
    };
    if (fareVar) {
      kap.addEventListener("pointermove", fareHareket);
      kap.addEventListener("pointerleave", fareCikti);
      kap.addEventListener("click", tikla);
    }

    const boyutGozcusu = new ResizeObserver(() => {
      boyutla();
      if (azalt) ciz(performance.now(), null);
    });
    boyutGozcusu.observe(kap);
    const gorunurlukGozcusu = new IntersectionObserver(([g]) => (gorunur = g.isIntersecting));
    gorunurlukGozcusu.observe(kap);
    const tema = matchMedia("(prefers-color-scheme: dark)");
    const temaDegisti = () => {
      renk = renkleriOku();
      if (azalt) ciz(performance.now(), null);
    };
    tema.addEventListener("change", temaDegisti);
    document.addEventListener("temadegisti", temaDegisti); // menüdeki gündüz/gece düğmesi

    if (azalt) {
      // Hareket istemeyen kullanıcı: tek sabit kare, sayaçlar son değerde, iki örnek etiket
      setIlerleme(1);
      ciz(performance.now(), null);
      const sabit = harita.sehirler
        .filter((s) => sehirIlanlari.get(s.anahtar)?.length)
        .slice(0, 2)
        .map((s, i) => ({ kimlik: i + 1, x: s.x, y: s.y, ilan: sehirIlanlari.get(s.anahtar)![0] }));
      setEtiketler(sabit);
    } else {
      ciz(performance.now(), null); // ilk kare hemen: döngü yavaş başlasa da harita boş görünmez
      kare = requestAnimationFrame(adim);
    }
    return () => {
      cancelAnimationFrame(kare);
      kap.removeEventListener("pointermove", fareHareket);
      kap.removeEventListener("pointerleave", fareCikti);
      kap.removeEventListener("click", tikla);
      boyutGozcusu.disconnect();
      gorunurlukGozcusu.disconnect();
      tema.removeEventListener("change", temaDegisti);
      document.removeEventListener("temadegisti", temaDegisti);
    };
  }, [harita, sehirIlanlari]);

  const sayac = (deger: number) => sayi(Math.round(deger * Math.min(1, ilerleme * 1.05)));
  const kutular = [
    { deger: sayac(toplam.firma), ad: "şirket okundu" },
    { deger: sayac(toplam.ilan), ad: "ilan incelendi" },
    { deger: sayac(toplam.ogrenci), ad: "öğrenciye uygun", vurgu: true },
  ];

  return (
    <figure className="kart m-0 overflow-hidden" aria-label="Türkiye haritası üzerinde ilan taraması simülasyonu">
      <div className="flex items-center justify-between border-b border-cizgi px-4 py-3 font-mono text-[0.7rem] uppercase tracking-[0.12em] text-murekkep-2 md:px-5">
        <span className="flex items-center gap-2">
          <span className={`inline-block h-1.5 w-1.5 rounded-full bg-kirmizi ${hareketsiz ? "" : "animate-pulse"}`} />
          Sabah taraması
        </span>
        <span>{gun} · 07:00</span>
      </div>

      <div className="px-3 pb-2 pt-6 md:px-6 md:pt-8">
        <div ref={kapRef} className="relative w-full [@media(hover:hover)]:cursor-crosshair">
          <canvas
            ref={tuvalRef}
            className="block h-auto w-full"
            style={{ aspectRatio: `${harita.genislik} / ${harita.yukseklik}` }}
            aria-hidden="true"
          />
          {yakinSehir && (
            <div
              className="pointer-events-none absolute z-20"
              style={{
                left: `${(yakinSehir.x / harita.genislik) * 100}%`,
                top: `${(yakinSehir.y / harita.yukseklik) * 100}%`,
              }}
            >
              <div
                className="whitespace-nowrap rounded-lg bg-murekkep px-3 py-2 text-kagit shadow-kagit"
                style={{
                  // batıdaki şehirde kutu sağa, doğudakinde sola uzar (kartın dışına taşmaz)
                  transform: `translate(${yakinSehir.x / harita.genislik < 0.34 ? "-14%" : yakinSehir.x / harita.genislik > 0.66 ? "-86%" : "-50%"}, calc(-100% - 16px))`,
                }}
              >
                <p className="baslik text-[1.1rem] font-[560]">{yakinSehir.ad}</p>
                <p className="mt-0.5 font-mono text-[0.68rem] opacity-80">
                  {sayi(yakinSehir.sayi)} ilan incelendi · {sehirIlanlari.get(yakinSehir.anahtar)?.length ?? 0}{" "}
                  öğrenciye uygun
                </p>
              </div>
            </div>
          )}
          {etiketler.map((e) => {
            // Batıdaki şehirde etiket sağa, doğudakinde sola uzar: kartın dışına taşmaz
            const oran = e.x / harita.genislik;
            const yatay = oran < 0.34 ? "-12%" : oran > 0.66 ? "-88%" : "-50%";
            const dikey = e.kimlik % 2 ? "-128%" : "28%";
            return (
              <div
                key={e.kimlik}
                className="radar-etiket pointer-events-none absolute z-10"
                style={{ left: `${oran * 100}%`, top: `${(e.y / harita.yukseklik) * 100}%` }}
              >
                <div
                  className="kart whitespace-nowrap px-3 py-2 text-[0.72rem] leading-tight sm:text-[0.78rem]"
                  style={{ transform: `translate(${yatay}, ${dikey})` }}
                >
                  <span className="font-mono text-[0.64rem] uppercase tracking-wider text-murekkep-3">
                    {e.ilan.seviye} · {e.ilan.firma}
                  </span>
                  <span className="mt-1 block max-w-[11rem] truncate font-medium sm:max-w-[14rem]">
                    {e.ilan.baslik}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
        <p className="mt-3 hidden text-center font-mono text-[0.68rem] text-murekkep-3 [@media(hover:hover)]:block">
          İmleci haritada gezdir, bir şehre yaklaş
        </p>
      </div>

      <figcaption className="grid grid-cols-3 border-t border-cizgi">
        {kutular.map((k, i) => (
          <div key={k.ad} className={`px-4 py-4 md:px-5 ${i > 0 ? "border-l border-cizgi" : ""}`}>
            <span className="baslik block text-[clamp(1.35rem,2.6vw,2rem)] font-[560] tabular-nums">
              {k.vurgu ? <span className="fosfor fosfor-hemen">{k.deger}</span> : k.deger}
            </span>
            <span className="mt-1 block font-mono text-[0.68rem] text-murekkep-3">{k.ad}</span>
          </div>
        ))}
      </figcaption>
    </figure>
  );
}
