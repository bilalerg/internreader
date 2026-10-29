// Gündüz / gece baskısı: menüdeki tema düğmesi. Seçim tarayıcıda saklanır (localStorage; ilk boyamadan önce
// Taban.astro'daki satır içi betik okur, ekran yanıp sönmez). Seçim yoksa sistem teması geçerlidir.
// Geçiş, tıklanan noktadan büyüyen bir daireyle olur (View Transitions API); desteklemeyen tarayıcıda ya da
// "hareketi azalt" tercihinde anında. Değişince "temadegisti" olayı yayınlanır (harita renklerini yeniden okur).
const kok = document.documentElement;
const geceMi = () =>
  kok.dataset.tema ? kok.dataset.tema === "gece" : matchMedia("(prefers-color-scheme: dark)").matches;

const dugme = document.querySelector<HTMLButtonElement>("[data-tema-dugmesi]");

function etiketle() {
  dugme?.setAttribute("aria-label", geceMi() ? "Gündüz baskısına geç" : "Gece baskısına geç");
}

function uygula(gece: boolean) {
  kok.dataset.tema = gece ? "gece" : "gunduz";
  try {
    localStorage.setItem("tema", kok.dataset.tema);
  } catch {
    // gizli pencere ya da engellenmiş depolama: seçim yalnızca bu sayfada geçerli
  }
  document.dispatchEvent(new Event("temadegisti"));
  etiketle();
}

if (dugme) {
  etiketle();
  dugme.addEventListener("click", (olay) => {
    const hedef = !geceMi();
    if (!("startViewTransition" in document) || matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return uygula(hedef);
    }
    // Klavyeyle basıldıysa (koordinat yok) daire düğmenin ortasından başlar
    const kutu = dugme.getBoundingClientRect();
    const x = olay.clientX || kutu.left + kutu.width / 2;
    const y = olay.clientY || kutu.top + kutu.height / 2;
    const yaricap = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
    kok.classList.add("tema-gecisi");
    const gecis = document.startViewTransition(() => uygula(hedef));
    gecis.ready.then(() =>
      kok.animate(
        { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${yaricap}px at ${x}px ${y}px)`] },
        { duration: 700, easing: "cubic-bezier(0.65, 0, 0.35, 1)", pseudoElement: "::view-transition-new(root)" },
      ),
    );
    gecis.finished.finally(() => kok.classList.remove("tema-gecisi"));
  });
}
