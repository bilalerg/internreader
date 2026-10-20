import { useEffect, useRef } from "react";
import { sayi } from "../veri/etiketler";

// "Sorun" bölümünün görseli: dağınık ilan kaynakları, sayfa kaydırıldıkça uçup tek bir e-postada birleşir.
// Kaydırmaya bağlı (scroll-linked) animasyon: ilerleme kare başına bir kez hesaplanır ve kartların stili doğrudan
// güncellenir (React her karede yeniden çizmez). "Hareketi azalt" tercihinde kartlar dağınık hâlde sabit kalır.

interface Props {
  taranan: number;
  aktifIlan: number;
  ogrenciIlani: number;
}

const KAYNAKLAR = [
  { ad: "firma.com/kariyer", tur: "kariyer sayfası" },
  { ad: "jobs.lever.co", tur: "Lever" },
  { ad: "boards.greenhouse.io", tur: "Greenhouse" },
  { ad: "firma.com.tr/insan-kaynaklari", tur: "kariyer sayfası" },
  { ad: "myworkdayjobs.com", tur: "Workday" },
  { ad: "jobs.ashbyhq.com", tur: "Ashby" },
  { ad: "apply.workable.com", tur: "Workable" },
  { ad: "careers.firma.com", tur: "kariyer sayfası" },
  { ad: "firma.recruitee.com", tur: "Recruitee" },
];

// Başlangıç yerleşimi (kutunun yüzdesi olarak sol/üst) ve eğim: elle dağıtılmış, rastgele değil (her açılışta aynı)
const DAGINIK = [
  { x: 0, y: 2, r: -5 },
  { x: 35, y: 0, r: 3 },
  { x: 67, y: 4, r: -2 },
  { x: 4, y: 24, r: 4 },
  { x: 38, y: 21, r: -3 },
  { x: 66, y: 27, r: 5 },
  { x: 1, y: 46, r: -3 },
  { x: 35, y: 44, r: 2 },
  { x: 68, y: 49, r: -4 },
];
const HEDEF = { x: 34, y: 74 }; // e-postanın ortası

const sinirla = (v: number) => Math.min(1, Math.max(0, v));
const yumusak = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

export default function DaginikKaynaklar({ taranan, aktifIlan, ogrenciIlani }: Props) {
  const kapRef = useRef<HTMLDivElement>(null);
  const kartRef = useRef<(HTMLLIElement | null)[]>([]);
  const zarfRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const kap = kapRef.current!;
    let bekliyor = false;

    const guncelle = () => {
      bekliyor = false;
      const r = kap.getBoundingClientRect();
      const vh = window.innerHeight;
      // Kutunun üstü ekranın %78 hizasındayken başlar, %12 hizasına gelince biter: birleşme ekranın ortasında izlenir
      const p = sinirla((vh * 0.78 - r.top) / (vh * 0.66));
      kartRef.current.forEach((kart, i) => {
        if (!kart) return;
        const k = yumusak(sinirla((p - i * 0.035) / 0.62));
        const d = DAGINIK[i];
        const dx = ((HEDEF.x - d.x) / 100) * r.width * k;
        const dy = ((HEDEF.y - d.y) / 100) * r.height * k;
        kart.style.transform = `translate(${dx}px, ${dy}px) rotate(${d.r * (1 - k)}deg) scale(${1 - 0.6 * k})`;
        kart.style.opacity = String(1 - sinirla((k - 0.72) / 0.28));
      });
      const z = sinirla((p - 0.55) / 0.45);
      const zarf = zarfRef.current!;
      zarf.style.transform = `scale(${0.94 + 0.06 * z})`;
      zarf.style.setProperty("--parilti", String(z));
      zarf.dataset.dolu = p > 0.92 ? "evet" : "hayir";
    };
    const tetikle = () => {
      if (!bekliyor) {
        bekliyor = true;
        requestAnimationFrame(guncelle);
      }
    };
    guncelle();
    window.addEventListener("scroll", tetikle, { passive: true });
    window.addEventListener("resize", tetikle);
    return () => {
      window.removeEventListener("scroll", tetikle);
      window.removeEventListener("resize", tetikle);
    };
  }, []);

  return (
    <div
      ref={kapRef}
      className="relative h-[470px] sm:h-[440px]"
      aria-label="Dağınık ilan kaynakları tek e-postada toplanır"
    >
      <ul>
        {KAYNAKLAR.map((k, i) => (
          <li
            key={k.ad}
            ref={(el) => {
              kartRef.current[i] = el;
            }}
            className="kart absolute w-[31%] px-3 py-2.5 will-change-transform"
            style={{ left: `${DAGINIK[i].x}%`, top: `${DAGINIK[i].y}%`, transform: `rotate(${DAGINIK[i].r}deg)` }}
          >
            <span className="block truncate font-mono text-[0.7rem] text-murekkep">{k.ad}</span>
            <span className="mt-0.5 block truncate text-[0.72rem] text-murekkep-3">{k.tur}</span>
          </li>
        ))}
      </ul>

      <div
        ref={zarfRef}
        data-dolu="hayir"
        className="zarf kart absolute inset-x-0 bottom-0 mx-auto flex max-w-md items-center gap-4 px-5 py-4 will-change-transform"
      >
        <span className="zarf-simge grid h-11 w-11 shrink-0 place-items-center rounded-full bg-fosfor text-fosfor-yazi">
          <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
            <rect x="2" y="4" width="14" height="10" rx="2" stroke="currentColor" strokeWidth="1.6" fill="none" />
            <path d="m3 5 6 5 6-5" stroke="currentColor" strokeWidth="1.6" fill="none" />
          </svg>
        </span>
        <div>
          <p className="font-semibold">1 e-posta · 07:00</p>
          <p className="text-[0.88rem] text-murekkep-2">
            {sayi(taranan)} şirket, {sayi(aktifIlan)} ilan okundu → sana uyanlar ({sayi(ogrenciIlani)} öğrenci ilanı
            açık)
          </p>
        </div>
      </div>
    </div>
  );
}
