import {
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type PointerEvent as IsaretciOlayi,
  type ReactNode,
} from "react";
import { AnimatePresence, MotionConfig, motion } from "motion/react";
import type { Ilan } from "../veri/tipler";
import {
  ALAN_ADI,
  ALAN_SECENEKLERI,
  CALISMA_MODELI_ADI,
  CALISMA_MODELI_SECENEKLERI,
  ROL_ADI,
  SEHIR_SECENEKLERI,
  SEVIYE_ADI,
  SEVIYE_SECENEKLERI,
  sehirAdi,
  tarihBilgisi,
  tarihSaat,
} from "../veri/etiketler";

// "Bülteni dene": filtreleri seç → bugünün gerçek ilanlarıyla e-posta önizlemesi → aynı tercihlerle abone ol.
// İlanlar derlemede gömülür; tarayıcıda /veri/ilanlar.json varsa (sunucuda her sabah güncellenir) onunla tazelenir.

interface Props {
  ilanlar: Ilan[];
  guncelleme: string;
}

type Durum =
  | { tur: "bos" }
  | { tur: "gonderiliyor" }
  | { tur: "tamam"; eposta: string }
  | { tur: "hata"; mesaj: string; alanlar: string[] };

const ONIZLEME_SINIRI = 6;
const FIRMA_BASINA_AZAMI = 2; // internreader/bulten/secim.py ile aynı: bir e-postada aynı firmadan en fazla 2 ilan

// Sıra JSON'dan gelir (yeni, girişim, ücretli önde). Firma kotasını aşan ilan sonraki bültene kalır.
function bultenListesi(uyanlar: Ilan[]) {
  const sayac = new Map<string, number>();
  return uyanlar.filter((i) => {
    const n = sayac.get(i.firma) ?? 0;
    sayac.set(i.firma, n + 1);
    return n < FIRMA_BASINA_AZAMI;
  });
}

interface Secimler {
  sehirler: Set<string>;
  alanlar: Set<string>;
  seviyeler: Set<string>;
  modeller: Set<string>; // boş = fark etmez
  sadeceGirisim: boolean;
}

// internreader/bulten/secim.py → eslesir ile AYNI kural: önizlemede görülen, e-postada gelen
function eslesir(ilan: Ilan, s: Secimler) {
  const model = ilan.calisma_modeli ?? "belirsiz";
  if (!(ilan.alanlar ?? [ilan.rol]).some((a) => s.alanlar.has(a)) || !s.seviyeler.has(ilan.seviye)) return false;
  if (s.modeller.size > 0 && !s.modeller.has(model)) return false; // belirtilmemiş model yalnızca "fark etmez"de
  if (s.sadeceGirisim && !ilan.girisim) return false;
  if (s.sehirler.size === 0) return true;
  // Uzaktan ilan her şehirden yapılabilir; konumu yazmayan Türk şirketi de dahil, "konum belirtilmemiş" etiketiyle
  return (
    ilan.uzaktan || model === "uzaktan" || ilan.sehirler.length === 0 || ilan.sehirler.some((x) => s.sehirler.has(x))
  );
}

function kaynakOku(): string {
  const ref = new URLSearchParams(location.search).get("ref") ?? "";
  return /^[a-z0-9_-]{1,40}$/.test(ref) ? ref : "site";
}

function Secim({ secili, onChange, children }: { secili: boolean; onChange: () => void; children: ReactNode }) {
  return (
    <label className="cursor-pointer select-none">
      <input type="checkbox" className="peer sr-only" checked={secili} onChange={onChange} />
      <span
        className={`inline-flex items-center gap-1.5 rounded-full border px-3.5 py-2 text-[0.9rem] transition-colors peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-murekkep ${
          secili
            ? "border-murekkep bg-murekkep text-kagit"
            : "border-cizgi bg-transparent text-murekkep-2 hover:border-murekkep-3 hover:text-murekkep"
        }`}
      >
        {secili && (
          <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
            <path
              d="m2.5 6.2 2.2 2.2 4.8-5"
              stroke="currentColor"
              strokeWidth="1.8"
              fill="none"
              strokeLinecap="round"
            />
          </svg>
        )}
        {children}
      </span>
    </label>
  );
}

/** Sayı değişince eski değerden yenisine yumuşakça akar (yaklaşık 0,45 sn). */
function AkanSayi({ deger }: { deger: number }) {
  const [gorunen, setGorunen] = useState(deger);
  const onceki = useRef(deger);
  useEffect(() => {
    const bas = onceki.current;
    onceki.current = deger;
    if (bas === deger || matchMedia("(prefers-reduced-motion: reduce)").matches) return setGorunen(deger);
    const t0 = performance.now();
    let kare = 0;
    const adim = (an: number) => {
      const p = Math.min(1, (an - t0) / 450);
      setGorunen(Math.round(bas + (deger - bas) * (1 - Math.pow(1 - p, 3))));
      if (p < 1) kare = requestAnimationFrame(adim);
    };
    kare = requestAnimationFrame(adim);
    return () => cancelAnimationFrame(kare);
  }, [deger]);
  return <span className="tabular-nums">{gorunen}</span>;
}

/** İmlecin altında parlama (.isik): konum CSS değişkenleriyle verilir, React yeniden çizmez. */
function isikTakip(o: IsaretciOlayi<HTMLElement>) {
  const r = o.currentTarget.getBoundingClientRect();
  o.currentTarget.style.setProperty("--mx", `${o.clientX - r.left}px`);
  o.currentTarget.style.setProperty("--my", `${o.clientY - r.top}px`);
}

function degistir(kume: Set<string>, deger: string): Set<string> {
  const yeni = new Set(kume);
  if (yeni.has(deger)) yeni.delete(deger);
  else yeni.add(deger);
  return yeni;
}

export default function Bulten({ ilanlar: gomulu, guncelleme: gomuluTarih }: Props) {
  const [ilanlar, setIlanlar] = useState(gomulu);
  const [guncelleme, setGuncelleme] = useState(gomuluTarih);
  const [sehirler, setSehirler] = useState<Set<string>>(new Set());
  const [alanlar, setAlanlar] = useState<Set<string>>(new Set(ALAN_SECENEKLERI));
  const [seviyeler, setSeviyeler] = useState<Set<string>>(new Set(SEVIYE_SECENEKLERI));
  const [modeller, setModeller] = useState<Set<string>>(new Set());
  const [sadeceGirisim, setSadeceGirisim] = useState(false);
  const [siklik, setSiklik] = useState<"gunluk" | "haftalik">("gunluk");
  const [eposta, setEposta] = useState("");
  const [kvkk, setKvkk] = useState(false);
  const [balKupu, setBalKupu] = useState("");
  const [durum, setDurum] = useState<Durum>({ tur: "bos" });
  const kimlik = useId();

  // Sunucudaki günlük veri derlemedekinden yeniyse onu kullan (site her sabah yeniden derlenmez)
  useEffect(() => {
    fetch("/veri/ilanlar.json", { cache: "no-cache" })
      .then((c) => (c.ok ? c.json() : null))
      .then((veri) => {
        if (veri?.ilanlar && veri.guncelleme > gomuluTarih) {
          setIlanlar(veri.ilanlar);
          setGuncelleme(veri.guncelleme);
        }
      })
      .catch(() => {}); // yerelde dosya yok: gömülü veriyle devam
  }, [gomuluTarih]);

  const uyanlar = useMemo(
    () => ilanlar.filter((i) => eslesir(i, { sehirler, alanlar, seviyeler, modeller, sadeceGirisim })),
    [ilanlar, sehirler, alanlar, seviyeler, modeller, sadeceGirisim],
  );
  const bultendekiler = useMemo(() => bultenListesi(uyanlar), [uyanlar]);
  const eksikSecim = alanlar.size === 0 || seviyeler.size === 0;
  // Seçim değişince önizleme listesi yeniden kurulur ve öğeler sırayla belirir
  const hataliMi = (alan: string) => durum.tur === "hata" && durum.alanlar.includes(alan);

  async function gonder(e: FormEvent) {
    e.preventDefault();
    if (eksikSecim) return;
    setDurum({ tur: "gonderiliyor" });
    try {
      const cevap = await fetch("/api/abone", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          eposta,
          sehirler: [...sehirler],
          alanlar: [...alanlar],
          seviyeler: [...seviyeler],
          calisma_modelleri: [...modeller],
          sadece_girisim: sadeceGirisim,
          siklik,
          kvkk_onay: kvkk,
          kaynak: kaynakOku(),
          web_sitesi: balKupu,
        }),
      });
      if (cevap.status === 202) {
        void import("../scripts/kutlama").then((m) => m.kutla());
        return setDurum({ tur: "tamam", eposta });
      }
      const govde = await cevap.json().catch(() => ({}));
      setDurum({
        tur: "hata",
        mesaj: govde.mesaj ?? "Bir şeyler ters gitti. Birazdan tekrar dene.",
        alanlar: govde.alanlar ?? [],
      });
    } catch {
      setDurum({
        tur: "hata",
        mesaj: "Sunucuya ulaşılamadı. İnternet bağlantını kontrol edip tekrar dene.",
        alanlar: [],
      });
    }
  }

  const grupBasligi = "mb-3 flex w-full items-baseline justify-between gap-3 font-medium"; // legend kendiliğinden tam genişlik almaz

  return (
    <div className="grid gap-10 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)] lg:gap-14">
      {/* ---------------- form ---------------- */}
      <div>
        {durum.tur === "tamam" ? (
          <div className="kart p-7 md:p-8" role="status">
            <div className="grid h-12 w-12 place-items-center rounded-full bg-fosfor text-fosfor-yazi">
              <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true">
                <path d="m5 11.5 4 4 8-9" stroke="currentColor" strokeWidth="2.2" fill="none" strokeLinecap="round" />
              </svg>
            </div>
            <h3 className="baslik mt-6 text-[2rem] font-[560]">Neredeyse tamam.</h3>
            <p className="mt-4 leading-relaxed text-murekkep-2">
              <strong className="text-murekkep">{durum.eposta}</strong> adresine bir onay bağlantısı gönderdik.
              Bağlantıya tıkladığında aboneliğin başlar ve seçimlerine uyan güncel ilanlar hemen e-postana gelir;
              sonraki bültenin {siklik === "gunluk" ? "yeni ilan çıktığı ilk sabah" : "pazartesi sabahı"} gelir.
            </p>
            <p className="mt-3 text-[0.92rem] text-murekkep-3">E-posta birkaç dakikada gelmezse spam klasörüne bak.</p>
            <button type="button" className="dugme dugme-ikincil mt-6" onClick={() => setDurum({ tur: "bos" })}>
              Başka bir adresle kaydol
            </button>
          </div>
        ) : (
          <form onSubmit={gonder} noValidate className="space-y-8">
            <fieldset>
              <legend className={grupBasligi}>
                <span>1. Nerede?</span>
                <span className="font-mono text-[0.72rem] font-normal text-murekkep-3">
                  {sehirler.size ? `${sehirler.size} seçili` : "hiçbiri = fark etmez"}
                </span>
              </legend>
              <div className="flex flex-wrap gap-2">
                {SEHIR_SECENEKLERI.map((s) => (
                  <Secim key={s} secili={sehirler.has(s)} onChange={() => setSehirler((k) => degistir(k, s))}>
                    {sehirAdi(s)}
                  </Secim>
                ))}
              </div>
            </fieldset>

            <fieldset>
              <legend className={grupBasligi}>
                <span>2. Hangi alan?</span>
                <span className="font-mono text-[0.72rem] font-normal text-murekkep-3">biri yeter</span>
              </legend>
              <div className="flex flex-wrap gap-2">
                {ALAN_SECENEKLERI.map((a) => (
                  <Secim key={a} secili={alanlar.has(a)} onChange={() => setAlanlar((k) => degistir(k, a))}>
                    {ALAN_ADI[a]}
                  </Secim>
                ))}
              </div>
              <p className="mt-2 text-[0.8rem] text-murekkep-3">
                Bir ilan birden çok alana girebilir: savunma şirketindeki yazılım stajı hem Yazılım hem Savunma.
              </p>
            </fieldset>

            <fieldset>
              <legend className={grupBasligi}>3. Hangi seviye?</legend>
              <div className="flex flex-wrap gap-2">
                {SEVIYE_SECENEKLERI.map((s) => (
                  <Secim key={s} secili={seviyeler.has(s)} onChange={() => setSeviyeler((k) => degistir(k, s))}>
                    {SEVIYE_ADI[s]}
                  </Secim>
                ))}
              </div>
            </fieldset>

            <fieldset>
              <legend className={grupBasligi}>
                <span>4. Nasıl çalışmak istersin?</span>
                <span className="font-mono text-[0.72rem] font-normal text-murekkep-3">
                  {modeller.size ? `${modeller.size} seçili` : "hiçbiri = fark etmez"}
                </span>
              </legend>
              <div className="flex flex-wrap gap-2">
                {CALISMA_MODELI_SECENEKLERI.map((m) => (
                  <Secim key={m} secili={modeller.has(m)} onChange={() => setModeller((k) => degistir(k, m))}>
                    {CALISMA_MODELI_ADI[m]}
                  </Secim>
                ))}
                <Secim secili={sadeceGirisim} onChange={() => setSadeceGirisim((d) => !d)}>
                  Yalnızca girişimler
                </Secim>
              </div>
              <p className="mt-2 text-[0.8rem] text-murekkep-3">
                Çalışma modelini yazmayan ilanlar yalnızca &ldquo;fark etmez&rdquo;de gelir. Girişim: elle doğrulanmış
                ya da yapay zekâ girişim haritasındaki firmalar; büyük ve köklü şirketler hariç. zekâ girişimi
                listelerindeki firmalar; bankalar ve büyük şirketler hariç.
              </p>
            </fieldset>

            {/* Telefonda önizleme formun altında kalır: seçimin sonucunu burada da göster */}
            <p className="rounded-xl bg-fosfor-zemin px-4 py-3 text-[0.92rem] lg:hidden" aria-live="polite">
              Bu sabah seçimlerine uyan{" "}
              <strong>
                <AkanSayi deger={uyanlar.length} />
              </strong>{" "}
              ilan var ·{" "}
              <a href="#onizleme" className="underline underline-offset-2">
                önizlemeye bak ↓
              </a>
            </p>

            <fieldset className="border-t border-cizgi pt-8">
              <legend className={grupBasligi}>5. Nereye, ne sıklıkla?</legend>
              <label htmlFor={`${kimlik}-eposta`} className="sr-only">
                E-posta adresin
              </label>
              <div className="flex flex-col gap-3 sm:flex-row">
                <input
                  id={`${kimlik}-eposta`}
                  type="email"
                  required
                  autoComplete="email"
                  inputMode="email"
                  placeholder="ad@ornek.com"
                  value={eposta}
                  onChange={(e) => setEposta(e.target.value)}
                  aria-invalid={hataliMi("eposta")}
                  className={`min-w-0 flex-1 rounded-full border bg-yuzey px-5 py-3.5 text-[1rem] outline-none transition-colors placeholder:text-murekkep-3 focus:border-murekkep ${
                    hataliMi("eposta") ? "border-kirmizi" : "border-cizgi"
                  }`}
                />
                <div className="flex rounded-full border border-cizgi p-1" role="radiogroup" aria-label="Sıklık">
                  {(["gunluk", "haftalik"] as const).map((s) => (
                    <button
                      key={s}
                      type="button"
                      role="radio"
                      aria-checked={siklik === s}
                      onClick={() => setSiklik(s)}
                      className={`rounded-full px-4 py-2.5 text-[0.9rem] transition-colors ${
                        siklik === s ? "bg-murekkep text-kagit" : "text-murekkep-2 hover:text-murekkep"
                      }`}
                    >
                      {s === "gunluk" ? "Her sabah" : "Pazartesileri"}
                    </button>
                  ))}
                </div>
              </div>

              {/* Bal küpü: insanlar görmez, botlar doldurur */}
              <div aria-hidden="true" className="absolute -left-[9999px] h-px w-px overflow-hidden">
                <label>
                  Web siteniz
                  <input
                    tabIndex={-1}
                    autoComplete="off"
                    value={balKupu}
                    onChange={(e) => setBalKupu(e.target.value)}
                  />
                </label>
              </div>

              <label
                className={`mt-5 flex cursor-pointer items-start gap-3 text-[0.9rem] leading-relaxed ${hataliMi("kvkk_onay") ? "text-kirmizi" : "text-murekkep-2"}`}
              >
                <input
                  type="checkbox"
                  checked={kvkk}
                  onChange={(e) => setKvkk(e.target.checked)}
                  className="mt-1 h-4 w-4 shrink-0 accent-[var(--murekkep)]"
                />
                <span>
                  <a
                    href="/kvkk"
                    className="underline underline-offset-2 hover:text-murekkep"
                    target="_blank"
                    rel="noopener"
                  >
                    Aydınlatma metnini
                  </a>{" "}
                  okudum; e-posta adresimin yalnızca ilan bülteni göndermek için işlenmesini kabul ediyorum.
                </span>
              </label>

              <button
                type="submit"
                disabled={durum.tur === "gonderiliyor" || eksikSecim || !kvkk || !eposta}
                className="dugme dugme-ana mt-6 w-full justify-center disabled:cursor-not-allowed disabled:opacity-45 sm:w-auto"
              >
                {durum.tur === "gonderiliyor" ? "Gönderiliyor…" : "Ücretsiz abone ol"}
              </button>
              <p aria-live="polite" className="mt-3 min-h-[1.5em] text-[0.9rem] text-kirmizi">
                {durum.tur === "hata" ? durum.mesaj : eksikSecim ? "En az bir alan ve bir seviye seç." : ""}
              </p>
            </fieldset>
          </form>
        )}
      </div>

      {/* ---------------- e-posta önizlemesi ---------------- */}
      <div id="onizleme" className="scroll-mt-24 lg:sticky lg:top-24 lg:self-start">
        <div className="kart isik relative overflow-hidden" onPointerMove={isikTakip}>
          <span className="cerceve-isigi" aria-hidden="true">
            <span />
          </span>
          <div className="space-y-1 border-b border-cizgi bg-kagit-koyu/60 px-5 py-4 font-mono text-[0.74rem] text-murekkep-2">
            <p>
              <span className="text-murekkep-3">Kimden </span>InternReader
            </p>
            <p>
              <span className="text-murekkep-3">Konu </span>
              <span className="text-murekkep">
                {bultendekiler.length ? (
                  <>
                    Bugün sana uygun <AkanSayi deger={bultendekiler.length} /> ilan
                  </>
                ) : (
                  "Bugün sana uygun ilan yok"
                )}
              </span>
            </p>
            <p>
              <span className="text-murekkep-3">Tarih </span>
              {tarihSaat(guncelleme)}
            </p>
          </div>

          <div className="px-5 py-5" aria-live="polite">
            {bultendekiler.length === 0 ? (
              <div className="py-10 text-center">
                <p className="baslik text-[1.5rem] font-[520]">Bu sabah sessiz.</p>
                <p className="mx-auto mt-3 max-w-xs text-[0.92rem] leading-relaxed text-murekkep-2">
                  Bugün bu seçimlere uyan açık ilan yok. Abone olursan ilk ilan çıktığı sabah e-postanda olur.
                </p>
              </div>
            ) : (
              <MotionConfig reducedMotion="user">
                <ul className="divide-y divide-cizgi">
                  <AnimatePresence mode="popLayout" initial={false}>
                    {bultendekiler.slice(0, ONIZLEME_SINIRI).map((i, sira) => (
                      <motion.li
                        key={i.kimlik}
                        layout
                        initial={{ opacity: 0, y: 16 }}
                        animate={{ opacity: 1, y: 0, transition: { delay: sira * 0.035 } }}
                        exit={{ opacity: 0, scale: 0.96, transition: { duration: 0.18 } }}
                        transition={{ type: "spring", stiffness: 380, damping: 32 }}
                        className="py-3.5 first:pt-0"
                      >
                        <a href={i.url} target="_blank" rel="noopener" className="group block">
                          <p className="font-mono text-[0.72rem] tracking-wide text-murekkep-3">{i.firma_gorunen}</p>
                          <p className="mt-1 font-medium leading-snug group-hover:underline group-hover:underline-offset-2">
                            {i.baslik}
                          </p>
                          <p className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-[0.8rem] text-murekkep-2">
                            <span>{i.seviye_etiketi ?? SEVIYE_ADI[i.seviye]}</span>
                            <span>{ROL_ADI[i.rol]}</span>
                            <span>
                              {i.sehirler.length
                                ? i.sehirler.map(sehirAdi).join(", ")
                                : i.uzaktan
                                  ? "Uzaktan"
                                  : "Konum belirtilmemiş"}
                            </span>
                            {(i.alanlar ?? [])
                              .filter((a) => a === "oyun" || a === "savunma")
                              .map((a) => (
                                <span key={a}>{ALAN_ADI[a]}</span>
                              ))}
                            {(i.calisma_modeli ?? i.ayrinti?.calisma_modeli) === "hibrit" && <span>Hibrit</span>}
                            {i.girisim && <span>Girişim</span>}
                            {tarihBilgisi(i).map((t) => (
                              <span key={t}>{t}</span>
                            ))}
                            {i.yapay_zeka !== "yok" && <span className="fosfor fosfor-hemen">yapay zekâ</span>}
                          </p>
                          {i.ayrinti?.ozet && (
                            <p className="mt-1.5 line-clamp-2 text-[0.82rem] leading-relaxed text-murekkep-2">
                              {i.ayrinti.ozet}
                            </p>
                          )}
                          {!!i.ayrinti?.teknolojiler.length && (
                            <p className="mt-2 flex flex-wrap gap-1.5">
                              {i.ayrinti.teknolojiler.slice(0, 4).map((t) => (
                                <span
                                  key={t}
                                  className="rounded-[3px] border border-cizgi px-1.5 py-px font-mono text-[0.66rem] text-murekkep-3"
                                >
                                  {t}
                                </span>
                              ))}
                            </p>
                          )}
                        </a>
                      </motion.li>
                    ))}
                  </AnimatePresence>
                </ul>
              </MotionConfig>
            )}
            {bultendekiler.length > ONIZLEME_SINIRI && (
              <p className="mt-2 border-t border-cizgi pt-3 font-mono text-[0.75rem] text-murekkep-3">
                + {bultendekiler.length - ONIZLEME_SINIRI} ilan daha
              </p>
            )}
          </div>
          <p className="border-t border-cizgi px-5 py-3 text-[0.75rem] text-murekkep-3">
            Bu bir önizleme: ilanlar bu sabahki gerçek tarama sonuçları. Bir e-postada aynı firmadan en fazla 2 ilan
            olur, kalanı sonraki bültene kalır. Her e-postanın altında tek tıkla çıkış bağlantısı olur.
          </p>
        </div>
      </div>
    </div>
  );
}
