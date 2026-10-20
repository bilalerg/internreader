// Sitenin ortak etkileşimleri (kütüphane yok). Astro sayfasındaki statik öğelere uygulanır; React adalarının
// içine dokunulmaz (React kendi HTML'ini yönetir, dışarıdan dokunmak hidrasyon uyuşmazlığına yol açar).
//
//   data-belir        ekrana girince belirir (--sira ile sırayla)
//   .fosfor           ekrana girince fosforlu kalem çizgisi çekilir
//   .egim             imlecin konumuna göre hafifçe döner (data-egim="derece")
//   .isik             imlecin altında parlama
//   .miknatis         imlece doğru hafifçe çekilir
//
// Fareye bağlı efektler yalnızca fare olan cihazlarda kurulur; "hareketi azalt" tercihinde hiçbiri çalışmaz.

const azalt = matchMedia("(prefers-reduced-motion: reduce)").matches;
const fare = matchMedia("(hover: hover) and (pointer: fine)").matches;
const adaDisi = (el: Element) => !el.closest("astro-island");

/** Fare olaylarını kare hızına indirger: aynı karede gelen olaylardan yalnızca sonuncusu işlenir. */
function kareBasina<T extends Event>(isle: (olay: T) => void) {
  let bekleyen: T | null = null;
  return (olay: T) => {
    if (bekleyen === null) requestAnimationFrame(() => (isle(bekleyen!), (bekleyen = null)));
    bekleyen = olay;
  };
}

function belirmeler() {
  const hedefler = [...document.querySelectorAll("[data-belir], .fosfor:not(.fosfor-hemen)")].filter(adaDisi);
  if (azalt) return hedefler.forEach((el) => el.setAttribute("data-gorundu", ""));
  const gozcu = new IntersectionObserver(
    (girdiler) =>
      girdiler.forEach((g) => {
        if (!g.isIntersecting) return;
        g.target.setAttribute("data-gorundu", "");
        gozcu.unobserve(g.target);
      }),
    { rootMargin: "0px 0px -12% 0px" },
  );
  hedefler.forEach((el) => gozcu.observe(el));
}

function egimler() {
  document.querySelectorAll<HTMLElement>(".egim").forEach((el) => {
    const derece = Number(el.dataset.egim ?? 5);
    el.addEventListener(
      "pointermove",
      kareBasina((o: PointerEvent) => {
        const r = el.getBoundingClientRect();
        const x = (o.clientX - r.left) / r.width - 0.5;
        const y = (o.clientY - r.top) / r.height - 0.5;
        el.style.setProperty("--egy", `${(x * derece).toFixed(2)}deg`);
        el.style.setProperty("--egx", `${(-y * derece * 0.8).toFixed(2)}deg`);
        el.dataset.aktif = "";
      }),
    );
    el.addEventListener("pointerleave", () => {
      el.style.setProperty("--egx", "0deg");
      el.style.setProperty("--egy", "0deg");
      delete el.dataset.aktif;
    });
  });
}

function isiklar() {
  document.querySelectorAll<HTMLElement>(".isik").forEach((el) =>
    el.addEventListener(
      "pointermove",
      kareBasina((o: PointerEvent) => {
        const r = el.getBoundingClientRect();
        el.style.setProperty("--mx", `${o.clientX - r.left}px`);
        el.style.setProperty("--my", `${o.clientY - r.top}px`);
      }),
    ),
  );
}

function miknatislar() {
  document.querySelectorAll<HTMLElement>(".miknatis").forEach((el) => {
    el.addEventListener(
      "pointermove",
      kareBasina((o: PointerEvent) => {
        const r = el.getBoundingClientRect();
        const dx = o.clientX - (r.left + r.width / 2);
        const dy = o.clientY - (r.top + r.height / 2);
        el.style.setProperty("--mkx", `${(dx * 0.22).toFixed(1)}px`);
        el.style.setProperty("--mky", `${(dy * 0.3).toFixed(1)}px`);
      }),
    );
    el.addEventListener("pointerleave", () => {
      el.style.setProperty("--mkx", "0px");
      el.style.setProperty("--mky", "0px");
    });
  });
}

belirmeler();
if (fare && !azalt) {
  egimler();
  isiklar();
  miknatislar();
}
