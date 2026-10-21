// Yumuşak kaydırma (Lenis): tekerlek ve dokunmatik yüzey kaydırmasını kare kare yumuşatır; çapa bağlantıları
// (#bulten gibi) da yumuşak gider. Dokunmatik ekranda tarayıcının kendi kaydırması kalır. "Hareketi azalt"
// tercihinde hiç kurulmaz. Yapışkan bölümler (nasıl çalışır) gerçek sayfa kaydırmasını okuduğu için etkilenmez.
import Lenis from "lenis";

if (!matchMedia("(prefers-reduced-motion: reduce)").matches) {
  new Lenis({ autoRaf: true, anchors: { offset: -96 } }); // -96: yapışkan menünün altında dursun (scroll-mt-24)
}
