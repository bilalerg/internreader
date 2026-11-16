import { useEffect, useState, type FormEvent } from "react";
import type { Ilan, IlanListesi } from "../veri/tipler";

type Durum = "basvuruldu" | "gorusme" | "teklif" | "olumsuz";
type Kayit = {
  kimlik: string;
  firma: string;
  baslik: string;
  url: string;
  tarih: string;
  cv: string;
  durum: Durum;
};

const ANAHTAR = "internreader-basvurular-v1";
const DURUMLAR: Record<Durum, string> = {
  basvuruldu: "Başvuruldu",
  gorusme: "Görüşme",
  teklif: "Teklif",
  olumsuz: "Olumsuz",
};

function guvenliAdres(adres: string): boolean {
  try {
    return ["http:", "https:"].includes(new URL(adres).protocol);
  } catch {
    return false;
  }
}

function kayitlariOku(): Kayit[] {
  try {
    const veri: unknown = JSON.parse(localStorage.getItem(ANAHTAR) || "[]");
    if (!Array.isArray(veri)) return [];
    return veri.filter(
      (i): i is Kayit =>
        typeof i === "object" &&
        i !== null &&
        typeof i.kimlik === "string" &&
        typeof i.firma === "string" &&
        typeof i.baslik === "string" &&
        typeof i.url === "string" &&
        guvenliAdres(i.url) &&
        typeof i.tarih === "string" &&
        typeof i.cv === "string" &&
        typeof i.durum === "string" &&
        i.durum in DURUMLAR,
    );
  } catch {
    return [];
  }
}

export default function BasvuruTakibi() {
  const [kayitlar, setKayitlar] = useState<Kayit[]>([]);
  const [ilanlar, setIlanlar] = useState<Ilan[]>([]);
  const [secili, setSecili] = useState("");
  const [firma, setFirma] = useState("");
  const [baslik, setBaslik] = useState("");
  const [url, setUrl] = useState("");
  const [cv, setCv] = useState("");
  const [tarih, setTarih] = useState("");
  const [hata, setHata] = useState("");
  const [hazir, setHazir] = useState(false);

  useEffect(() => {
    setKayitlar(kayitlariOku());
    setTarih(new Date().toLocaleDateString("sv-SE"));
    setHazir(true);
    fetch("/veri/ilanlar.json", { cache: "no-cache" })
      .then((yanit) => yanit.json() as Promise<IlanListesi>)
      .then((veri) => {
        setIlanlar(veri.ilanlar || []);
        const kimlik = new URLSearchParams(window.location.search).get("ilan");
        const ilan = veri.ilanlar?.find((i) => i.kimlik === kimlik);
        if (ilan) sec(ilan);
      })
      .catch(() => {});
  }, []);

  function sec(ilan: Ilan) {
    setSecili(ilan.kimlik);
    setFirma(ilan.firma_gorunen || ilan.firma);
    setBaslik(ilan.baslik);
    setUrl(ilan.url);
  }

  function kaydet(yeni: Kayit[]) {
    try {
      localStorage.setItem(ANAHTAR, JSON.stringify(yeni));
      setKayitlar(yeni);
      setHata("");
    } catch {
      setHata("Tarayıcı kayıt alanına yazılamadı. Gizli mod veya dolu depolama buna neden olabilir.");
    }
  }

  function ekle(olay: FormEvent<HTMLFormElement>) {
    olay.preventDefault();
    if (!firma.trim() || !baslik.trim() || !guvenliAdres(url) || !tarih || !cv.trim()) {
      setHata("Şirket, pozisyon, geçerli ilan adresi, tarih ve kullanılan CV adını doldur.");
      return;
    }
    const kimlik = secili || crypto.randomUUID();
    if (kayitlar.some((i) => i.kimlik === kimlik || i.url === url.trim())) {
      setHata("Bu ilan zaten takip listende.");
      return;
    }
    kaydet([
      {
        kimlik,
        firma: firma.trim(),
        baslik: baslik.trim(),
        url: url.trim(),
        tarih,
        cv: cv.trim(),
        durum: "basvuruldu",
      },
      ...kayitlar,
    ]);
    setSecili("");
    setFirma("");
    setBaslik("");
    setUrl("");
    setCv("");
    window.history.replaceState({}, "", "/basvurular/");
  }

  return (
    <div className="space-y-10">
      <form onSubmit={ekle} className="rounded-xl border border-cizgi bg-yuzey p-5 shadow-kagit md:p-8">
        <h2 className="baslik text-2xl">Başvuru ekle</h2>
        <p className="mt-2 text-sm text-murekkep-2">Gerçekten başvurduktan sonra buraya kaydet.</p>
        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <label className="text-sm font-medium md:col-span-2">
            InternReader ilanından seç (isteğe bağlı)
            <select
              className="mt-2 w-full rounded-md border border-cizgi bg-kagit p-3"
              value={secili}
              onChange={(e) => {
                const ilan = ilanlar.find((i) => i.kimlik === e.target.value);
                if (ilan) sec(ilan);
                else setSecili("");
              }}
            >
              <option value="">İlanı seç veya aşağıya elle yaz</option>
              {ilanlar.map((i) => (
                <option key={i.kimlik} value={i.kimlik}>
                  {i.firma_gorunen} — {i.baslik}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm font-medium">
            Şirket
            <input
              required
              maxLength={120}
              value={firma}
              onChange={(e) => setFirma(e.target.value)}
              className="mt-2 w-full rounded-md border border-cizgi bg-kagit p-3"
            />
          </label>
          <label className="text-sm font-medium">
            Pozisyon
            <input
              required
              maxLength={180}
              value={baslik}
              onChange={(e) => setBaslik(e.target.value)}
              className="mt-2 w-full rounded-md border border-cizgi bg-kagit p-3"
            />
          </label>
          <label className="text-sm font-medium md:col-span-2">
            İlan bağlantısı
            <input
              required
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://..."
              className="mt-2 w-full rounded-md border border-cizgi bg-kagit p-3"
            />
          </label>
          <label className="text-sm font-medium">
            Başvuru tarihi
            <input
              required
              type="date"
              value={tarih}
              onChange={(e) => setTarih(e.target.value)}
              className="mt-2 w-full rounded-md border border-cizgi bg-kagit p-3"
            />
          </label>
          <label className="text-sm font-medium">
            Kullanılan CV
            <input
              required
              maxLength={80}
              list="cv-adlari"
              value={cv}
              onChange={(e) => setCv(e.target.value)}
              placeholder="Örn. Yazılım TR"
              className="mt-2 w-full rounded-md border border-cizgi bg-kagit p-3"
            />
            <datalist id="cv-adlari">
              <option value="Yazılım TR" />
              <option value="AI EN" />
              <option value="Savunma TR" />
            </datalist>
          </label>
        </div>
        {hata && (
          <p role="alert" className="mt-4 text-sm text-kirmizi">
            {hata}
          </p>
        )}
        <button type="submit" className="dugme dugme-ana mt-6">
          Başvurdum, kaydet
        </button>
      </form>

      <section aria-labelledby="liste-baslik">
        <div className="flex items-end justify-between gap-4 border-b border-cizgi pb-3">
          <h2 id="liste-baslik" className="baslik text-2xl">
            Başvurularım
          </h2>
          <span className="font-mono text-sm text-murekkep-2">{kayitlar.length} kayıt</span>
        </div>
        {hazir && kayitlar.length === 0 && (
          <p className="py-8 text-murekkep-2">Henüz kayıt yok. İlk başvurunu yukarıdan ekleyebilirsin.</p>
        )}
        <ul className="divide-y divide-cizgi">
          {kayitlar.map((i) => (
            <li key={i.kimlik} className="grid gap-3 py-5 md:grid-cols-[1fr_auto] md:items-center">
              <div>
                <p className="font-mono text-xs text-murekkep-3">
                  {i.firma} · {i.tarih}
                </p>
                <a
                  href={i.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-1 block font-medium underline-offset-2 hover:underline"
                >
                  {i.baslik} ↗
                </a>
                <p className="mt-1 text-sm text-murekkep-2">CV: {i.cv}</p>
              </div>
              <div className="flex items-center gap-3">
                <label className="sr-only" htmlFor={`durum-${i.kimlik}`}>
                  Başvuru durumu
                </label>
                <select
                  id={`durum-${i.kimlik}`}
                  value={i.durum}
                  onChange={(e) =>
                    kaydet(kayitlar.map((k) => (k.kimlik === i.kimlik ? { ...k, durum: e.target.value as Durum } : k)))
                  }
                  className="rounded-md border border-cizgi bg-kagit p-2 text-sm"
                >
                  {Object.entries(DURUMLAR).map(([deger, ad]) => (
                    <option key={deger} value={deger}>
                      {ad}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() => {
                    if (window.confirm("Bu başvuru kaydını silmek istiyor musun?"))
                      kaydet(kayitlar.filter((k) => k.kimlik !== i.kimlik));
                  }}
                  className="text-sm text-murekkep-2 underline hover:text-kirmizi"
                >
                  Sil
                </button>
              </div>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
