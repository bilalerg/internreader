import { useEffect, useRef, useState } from "react";
import type { Karar } from "../veri/tipler";
import { ROL_ADI, SEVIYE_ADI, sayi } from "../veri/etiketler";

// "Nasıl çalışır": bir sabahın dört adımı, her biri gerçek veriyle küçük bir simülasyon.
// Masaüstünde kaydırmayla anlatılır (bölüm ekrana yapışır, saat döner); telefonda sekmeler
// kendiliğinden ilerler. Hareketler CSS animasyonu: adım değişince sahne yeniden kurulur (key), animasyonlar baştan oynar.

interface Props {
  firmalar: string[];
  kararlar: Karar[];
  taranan: number;
}

const ADIM_SURESI = 8; // saniye

const ADIMLAR = [
  {
    saat: "07:00",
    ad: "Tara",
    baslik: "Şirketlerin kendi sayfaları taranır",
    metin: (t: number) =>
      `${sayi(t)} şirketin kariyer sayfası ve Lever, Greenhouse, Workday gibi 8 ilan sistemi okunur. Dünden beri değişmeyen sayfa tekrar okunmaz; ulaşılamayan site ertesi sabah yeniden denenir.`,
    not: "LinkedIn, Kariyer.net gibi platformlardan veri çekilmez; sitelerin robots.txt kurallarına uyulur.",
  },
  {
    saat: "07:05",
    ad: "Oku",
    baslik: "Yapay zekâ sayfayı bir insan gibi okur",
    metin: () =>
      "Her kariyer sayfası farklı tasarlanmıştır. Yapay zekâ sayfadaki açık pozisyonları çıkarır; “Bize katılın”, “Genel başvuru” gibi ifadeleri pozisyon saymaz.",
    not: "Bulunan her başlık sayfada birebir aranır. Sayfada yazmıyorsa listeye girmez: uydurma ilan olamaz.",
  },
  {
    saat: "07:08",
    ad: "Ayıkla",
    baslik: "Öğrenciye uygun olanlar ayrılır",
    metin: () =>
      "Her ilan seviyesine (staj, yeni mezun, junior… ya da deneyimli) ve alanına (yazılım, yapay zekâ, veri… ya da başka) göre sınıflandırılır. Senior ilanlar, satış ve idari işler elenir.",
    not: "Sağdaki kararlar ve gerekçeler, sistemin bu sabahki gerçek kararlarıdır.",
  },
  {
    saat: "07:10",
    ad: "Gönder",
    baslik: "Sana uyanlar e-postana gelir",
    metin: () =>
      "Seçtiğin şehir, alan ve seviyeye uyan yeni ilanlar tek bir e-postada toplanır. Her ilan, şirketin kendi başvuru sayfasına gider.",
    not: "Yeni ilan yoksa e-posta da gelmez. Daha önce gönderilen ilan tekrar gelmez.",
  },
];

// ------------------------------------------------------------------ sahneler
function TaramaSahnesi({ firmalar, taranan }: { firmalar: string[]; taranan: number }) {
  const durumlar = [
    { durum: "değişmedi", ek: "önbellekten", sinif: "text-murekkep-3" },
    { durum: "yeni içerik", ek: "okunacak", sinif: "text-murekkep font-medium" },
    { durum: "değişmedi", ek: "önbellekten", sinif: "text-murekkep-3" },
    { durum: "ilan sistemi", ek: "API", sinif: "text-murekkep" },
    { durum: "değişmedi", ek: "önbellekten", sinif: "text-murekkep-3" },
    { durum: "erişilemedi", ek: "yarın tekrar", sinif: "text-kirmizi" },
  ];
  const satirlar = firmalar.slice(0, 24).map((firma, i) => ({ firma, ...durumlar[(i * 7) % durumlar.length] }));
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-baseline justify-between border-b border-cizgi pb-3 font-mono text-[0.72rem] text-murekkep-2">
        <span>kaynak</span>
        <span>{sayi(taranan)} şirket · 8 ilan sistemi</span>
      </div>
      <div className="relative mt-2 flex-1 overflow-hidden [mask-image:linear-gradient(transparent,black_12%,black_88%,transparent)]">
        <ul className="akan">
          {[...satirlar, ...satirlar].map((s, i) => (
            <li
              key={i}
              className="flex items-center justify-between gap-4 border-b border-dashed border-cizgi py-2.5 text-[0.9rem]"
            >
              <span className="truncate">{s.firma}</span>
              <span className={`shrink-0 font-mono text-[0.72rem] ${s.sinif}`}>
                {s.durum === "yeni içerik" ? <span className="fosfor fosfor-hemen">{s.durum}</span> : s.durum}
                <span className="text-murekkep-3"> · {s.ek}</span>
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function OkumaSahnesi({ kararlar }: { kararlar: Karar[] }) {
  // Sayfadaki pozisyonlar: uygun olan da olmayan da (ayıklama bir sonraki adımda)
  const uygun = kararlar.filter((k) => k.uygun);
  const elenen = kararlar.filter((k) => !k.uygun);
  const pozisyonlar = [uygun[0], elenen[0], uygun[1], elenen[1]].filter(Boolean).map((k) => k.baslik);
  const satirlar: { tur: "dolgu" | "baslik" | "pozisyon" | "degil"; metin?: string; genislik?: string }[] = [
    { tur: "baslik", metin: "Kariyer · Açık Pozisyonlar" },
    { tur: "dolgu", genislik: "88%" },
    { tur: "dolgu", genislik: "64%" },
    { tur: "degil", metin: "Bize katılın, geleceği birlikte inşa edelim!" },
    ...pozisyonlar.slice(0, 2).map((metin) => ({ tur: "pozisyon" as const, metin })),
    { tur: "dolgu", genislik: "72%" },
    ...pozisyonlar.slice(2).map((metin) => ({ tur: "pozisyon" as const, metin })),
    { tur: "degil", metin: "Genel başvuru için CV'ni gönder" },
    { tur: "dolgu", genislik: "50%" },
  ];
  let sira = 0;
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-cizgi pb-3 font-mono text-[0.72rem] text-murekkep-3">
        <span className="h-2 w-2 rounded-full bg-cizgi" />
        <span className="h-2 w-2 rounded-full bg-cizgi" />
        <span className="ml-1 truncate">firma.com/kariyer</span>
      </div>
      <div className="mt-4 flex-1 space-y-3">
        {satirlar.map((s, i) => {
          if (s.tur === "dolgu")
            return <div key={i} className="h-2 rounded bg-cizgi/70" style={{ width: s.genislik }} />;
          if (s.tur === "baslik")
            return (
              <p key={i} className="baslik text-[1.25rem] font-[560]">
                {s.metin}
              </p>
            );
          const gecikme = 0.5 + sira++ * 0.75;
          if (s.tur === "degil")
            return (
              <p key={i} className="flex items-center justify-between gap-3 text-[0.9rem] text-murekkep-2">
                <span>{s.metin}</span>
                <span
                  className="belir shrink-0 font-mono text-[0.68rem] text-murekkep-3"
                  style={{ animationDelay: `${gecikme}s` }}
                >
                  pozisyon değil
                </span>
              </p>
            );
          return (
            <p key={i} className="flex items-center justify-between gap-3 text-[0.95rem] font-medium">
              <span className="isaretle rounded-[3px] px-1 -mx-1" style={{ animationDelay: `${gecikme}s` }}>
                {s.metin}
              </span>
              <span
                className="belir shrink-0 font-mono text-[0.68rem] text-yesil"
                style={{ animationDelay: `${gecikme + 0.3}s` }}
              >
                ✓ sayfada var
              </span>
            </p>
          );
        })}
      </div>
    </div>
  );
}

function AyiklamaSahnesi({ kararlar }: { kararlar: Karar[] }) {
  const uygun = kararlar.filter((k) => k.uygun).slice(0, 3);
  const elenen = kararlar.filter((k) => !k.uygun).slice(0, 3);
  const sutun = (liste: Karar[], baslangic: number, tur: "uygun" | "elendi") => (
    <ul className="space-y-3">
      {liste.map((k, i) => (
        <li
          key={k.baslik}
          className="belir relative rounded-lg border border-cizgi bg-kagit/60 p-3"
          style={{ animationDelay: `${baslangic + i * 0.9}s` }}
        >
          <p className="pr-16 text-[0.88rem] font-medium leading-snug">{k.baslik}</p>
          <p className="mt-1 font-mono text-[0.68rem] text-murekkep-3">
            {k.firma} · {SEVIYE_ADI[k.seviye] ?? k.seviye} · {ROL_ADI[k.rol] ?? k.rol}
          </p>
          <p className="mt-1.5 text-[0.8rem] italic leading-snug text-murekkep-2">“{k.gerekce}”</p>
          <span
            className={`damga absolute right-2.5 top-2.5 rounded border-2 px-1.5 py-0.5 font-mono text-[0.62rem] font-medium uppercase tracking-wider ${
              tur === "uygun" ? "border-yesil text-yesil" : "border-kirmizi text-kirmizi"
            }`}
            style={{ animationDelay: `${baslangic + i * 0.9 + 0.35}s` }}
          >
            {tur}
          </span>
        </li>
      ))}
    </ul>
  );
  return (
    <div className="grid h-full grid-cols-1 gap-4 overflow-hidden sm:grid-cols-2">
      <div>
        <p className="etiket mb-3">Sana uygun</p>
        {sutun(uygun, 0.3, "uygun")}
      </div>
      <div className="hidden sm:block">
        <p className="etiket mb-3">Elendi</p>
        {sutun(elenen, 0.75, "elendi")}
      </div>
    </div>
  );
}

function GonderimSahnesi({ kararlar }: { kararlar: Karar[] }) {
  const ilanlar = kararlar.filter((k) => k.uygun).slice(0, 3);
  return (
    <div className="flex h-full flex-col items-center justify-center">
      <div
        className="belir w-full max-w-sm rounded-2xl border border-cizgi bg-kagit p-4 shadow-kagit"
        style={{ animationDelay: "0.3s" }}
      >
        <div className="flex items-center justify-between font-mono text-[0.7rem] text-murekkep-3">
          <span>Gelen kutusu</span>
          <span>sabah</span>
        </div>
        <p className="mt-3 text-[0.82rem] text-murekkep-2">InternReader</p>
        <p className="font-semibold">Bugün sana uygun {ilanlar.length} yeni ilan</p>
        <ul className="mt-3 space-y-2.5">
          {ilanlar.map((k, i) => (
            <li
              key={k.baslik}
              className="belir border-t border-cizgi pt-2.5"
              style={{ animationDelay: `${0.9 + i * 0.45}s` }}
            >
              <p className="text-[0.88rem] font-medium leading-snug">{k.baslik}</p>
              <p className="mt-0.5 flex justify-between font-mono text-[0.68rem] text-murekkep-3">
                <span>
                  {k.firma} · {SEVIYE_ADI[k.seviye] ?? k.seviye}
                </span>
                <span className="text-murekkep">Başvur →</span>
              </p>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ saat
function Saat({ dakika }: { dakika: number }) {
  const dakikaAcisi = (dakika / 60) * 360;
  const saatAcisi = ((7 + dakika / 60) / 12) * 360;
  return (
    <div className="flex items-center gap-3" aria-hidden="true">
      <svg width="52" height="52" viewBox="0 0 52 52">
        <circle cx="26" cy="26" r="24" fill="var(--yuzey)" stroke="var(--murekkep)" strokeWidth="1.5" />
        {Array.from({ length: 12 }, (_, i) => (
          <line
            key={i}
            x1="26"
            y1="4.5"
            x2="26"
            y2={i % 3 ? 7.5 : 9.5}
            stroke="var(--murekkep-3)"
            strokeWidth={i % 3 ? 1 : 1.8}
            transform={`rotate(${i * 30} 26 26)`}
          />
        ))}
        <line
          x1="26"
          y1="26"
          x2="26"
          y2="14"
          stroke="var(--murekkep)"
          strokeWidth="2.6"
          strokeLinecap="round"
          transform={`rotate(${saatAcisi} 26 26)`}
        />
        <line
          x1="26"
          y1="26"
          x2="26"
          y2="8"
          stroke="var(--murekkep)"
          strokeWidth="1.6"
          strokeLinecap="round"
          transform={`rotate(${dakikaAcisi} 26 26)`}
        />
        <circle cx="26" cy="26" r="2.8" fill="var(--fosfor)" stroke="var(--murekkep)" strokeWidth="1" />
      </svg>
      <span className="font-mono text-[0.8rem] tabular-nums text-murekkep-2">her sabah</span>
    </div>
  );
}

// ------------------------------------------------------------------ ana bileşen
const sinirla = (v: number) => Math.min(1, Math.max(0, v));

export default function BoruHatti({ firmalar, kararlar, taranan }: Props) {
  const [etkin, setEtkin] = useState(0);
  const [tur, setTur] = useState(0); // her adım değişiminde sahneyi baştan kurmak için
  // Masaüstünde "sabit" mod: bölüm ekrana yapışır, kaydırdıkça adımlar ilerler, saat döner.
  // Telefonda ve "hareketi azalt" tercihinde sekme modu: ekrandayken adımlar kendiliğinden ilerler.
  const [sabit, setSabit] = useState(false);
  const [ilerleme, setIlerleme] = useState(0);
  const [oynuyor, setOynuyor] = useState(false);
  const [duraklat, setDuraklat] = useState(false);
  const kapRef = useRef<HTMLDivElement>(null);
  const etkinRef = useRef(0);

  const sec = (i: number) => {
    etkinRef.current = i;
    setEtkin(i);
    setTur((t) => t + 1);
  };

  useEffect(() => {
    const genis = matchMedia("(min-width: 1024px) and (min-height: 640px)");
    const azalt = matchMedia("(prefers-reduced-motion: reduce)");
    const ayarla = () => setSabit(genis.matches && !azalt.matches);
    ayarla();
    genis.addEventListener("change", ayarla);
    return () => genis.removeEventListener("change", ayarla);
  }, []);

  // Sekme modu: ekrandayken kendiliğinden ilerle
  useEffect(() => {
    if (sabit || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const gozcu = new IntersectionObserver(([g]) => setOynuyor(g.isIntersecting), { threshold: 0.35 });
    gozcu.observe(kapRef.current!);
    return () => gozcu.disconnect();
  }, [sabit]);

  // Sabit mod: kaydırma ilerlemesi → etkin adım (kare başına bir hesap)
  useEffect(() => {
    if (!sabit) return;
    const kap = kapRef.current!;
    let bekliyor = false;
    const guncelle = () => {
      bekliyor = false;
      const toplam = Math.max(1, kap.offsetHeight - window.innerHeight);
      const p = sinirla(-kap.getBoundingClientRect().top / toplam);
      setIlerleme(Math.round(p * 400) / 400);
      const yeni = Math.min(ADIMLAR.length - 1, Math.floor(p * ADIMLAR.length));
      if (yeni !== etkinRef.current) sec(yeni);
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
  }, [sabit]);

  // Sekmeye tıklama: sabit modda sayfa o adımın kaydırma konumuna kayar
  const tikla = (i: number) => {
    if (!sabit) return sec(i);
    const kap = kapRef.current!;
    const toplam = kap.offsetHeight - window.innerHeight;
    const ust = window.scrollY + kap.getBoundingClientRect().top;
    window.scrollTo({ top: ust + ((i + 0.1) / ADIMLAR.length) * toplam, behavior: "smooth" });
  };

  const adim = ADIMLAR[etkin];
  // Saat, sekmelerdeki saatlerle tutarlı: her adımın içinde o adımın saatinden bir sonrakine ilerler
  const dakikalar = ADIMLAR.map((a) => Number(a.saat.slice(3)));
  const konum = ilerleme * ADIMLAR.length;
  const sonraki = dakikalar[etkin + 1] ?? dakikalar[etkin];
  const dakika = sabit ? dakikalar[etkin] + (sonraki - dakikalar[etkin]) * sinirla(konum - etkin) : dakikalar[etkin];

  return (
    <div
      ref={kapRef}
      style={sabit ? { height: `${ADIMLAR.length * 80 + 20}vh` } : undefined}
      onMouseEnter={() => setDuraklat(true)}
      onMouseLeave={() => setDuraklat(false)}
    >
      <div className={sabit ? "sticky top-16 flex h-[calc(100vh-4rem)] flex-col justify-center py-6" : ""}>
        <div role="tablist" aria-label="Bir sabahın adımları" className="grid grid-cols-4 gap-2 md:gap-4">
          {ADIMLAR.map((a, i) => (
            <button
              key={a.ad}
              role="tab"
              id={`adim-${i}`}
              aria-selected={i === etkin}
              aria-controls="adim-paneli"
              onClick={() => tikla(i)}
              className={`group text-left transition-colors ${i === etkin ? "text-murekkep" : "text-murekkep-3 hover:text-murekkep-2"}`}
            >
              <span className="relative block h-[3px] overflow-hidden rounded-full bg-cizgi">
                {sabit ? (
                  <span
                    className="absolute inset-0 origin-left bg-murekkep"
                    style={{ transform: `scaleX(${sinirla(ilerleme * ADIMLAR.length - i)})` }}
                  />
                ) : (
                  <>
                    {i < etkin && <span className="absolute inset-0 bg-murekkep" />}
                    {i === etkin && (
                      <span
                        key={tur}
                        className="ilerleme-cubugu absolute inset-0 bg-murekkep"
                        style={{
                          animationDuration: `${ADIM_SURESI}s`,
                          animationPlayState: oynuyor && !duraklat ? "running" : "paused",
                        }}
                        onAnimationEnd={() => sec((etkin + 1) % ADIMLAR.length)}
                      />
                    )}
                  </>
                )}
              </span>
              <span className="mt-3 block font-mono text-[0.7rem]">her sabah</span>
              <span className="baslik mt-0.5 block text-[1.15rem] font-[560] md:text-[1.45rem]">
                {i + 1}. {a.ad}
              </span>
            </button>
          ))}
        </div>

        <div
          id="adim-paneli"
          role="tabpanel"
          aria-labelledby={`adim-${etkin}`}
          className="mt-8 grid gap-8 md:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] md:gap-12"
        >
          <div key={`metin-${tur}`} className="belir">
            <Saat dakika={dakika} />
            <h3 className="baslik mt-5 text-[1.9rem] font-[540] leading-[1.08] md:text-[2.3rem]">{adim.baslik}</h3>
            <p className="mt-5 text-[1.04rem] leading-[1.7] text-murekkep-2">{adim.metin(taranan)}</p>
            <p className="mt-5 border-l-2 border-fosfor pl-4 text-[0.95rem] leading-relaxed">{adim.not}</p>
            {sabit && (
              <p className="mt-8 font-mono text-[0.7rem] text-murekkep-3">
                {etkin < ADIMLAR.length - 1 ? "Kaydırmaya devam et ↓" : "Sabah bitti. Sıra bültenini kurmakta ↓"}
              </p>
            )}
          </div>
          <div
            key={`sahne-${tur}`}
            className={`kart overflow-hidden p-5 md:p-6 ${sabit ? "h-[min(420px,calc(100vh-17rem))]" : "h-[420px]"}`}
            aria-hidden="true"
          >
            {etkin === 0 && <TaramaSahnesi firmalar={firmalar} taranan={taranan} />}
            {etkin === 1 && <OkumaSahnesi kararlar={kararlar} />}
            {etkin === 2 && <AyiklamaSahnesi kararlar={kararlar} />}
            {etkin === 3 && <GonderimSahnesi kararlar={kararlar} />}
          </div>
        </div>
      </div>
    </div>
  );
}
