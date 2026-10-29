// Sahne: yumuşak kaydırma (Lenis) ve kaydırmaya bağlı animasyonlar (GSAP ScrollTrigger + SplitText).
//
//   [data-giris]          giriş bölümü: kaydırdıkça metin geri çekilir, harita öne çıkar (kaydırmaya bağlı)
//   [data-bolum-basligi]  bölüm başlıkları satır satır, maskenin altından yükselir
//   [data-okunan]         metin, okundukça kelime kelime koyulaşır (kaydırmaya bağlı)
//   .serit                şirket şeridi kaydırma hızına göre hızlanır ve eğilir
//   [data-kunye]          sayfa sonundaki dev künye, harf harf yükselir
//
// "Hareketi azalt" tercihinde hiçbiri kurulmaz; içerik baştan son hâlinde görünür. Yalnızca Astro sayfasındaki
// statik öğelere uygulanır; React adalarının içine dokunulmaz (React kendi HTML'ini yönetir).
import Lenis from "lenis";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { SplitText } from "gsap/SplitText";

function girisSahnesi() {
  const sahne = document.querySelector("[data-giris]");
  if (!sahne) return;
  gsap
    .timeline({ scrollTrigger: { trigger: sahne, start: "top top", end: "bottom top", scrub: 0.6 } })
    .to("[data-giris-metin]", { yPercent: -16, opacity: 0.12, ease: "none" }, 0)
    .to("[data-giris-gorsel]", { yPercent: 12, scale: 1.07, ease: "none" }, 0);
}

function bolumBasliklari() {
  document.querySelectorAll<HTMLElement>("[data-bolum-basligi]").forEach((baslik) => {
    SplitText.create(baslik, {
      type: "lines",
      mask: "lines",
      autoSplit: true, // yazı tipi yüklenince ve pencere boyutu değişince satırlar yeniden bölünür
      onSplit(bolum) {
        // Başlık satır aralığı dar (0,98): maskeye pay ver ki ğ, ş, ç gibi harflerin alt kısmı kesilmesin
        gsap.set(bolum.masks, { paddingBottom: "0.16em", marginBottom: "-0.16em" });
        return gsap.from(bolum.lines, {
          yPercent: 115,
          duration: 1.1,
          ease: "expo.out",
          stagger: 0.09,
          scrollTrigger: { trigger: baslik, start: "top 86%", once: true },
        });
      },
    });
  });
}

function okunanMetinler() {
  document.querySelectorAll<HTMLElement>("[data-okunan]").forEach((metin) => {
    const { words } = SplitText.create(metin, { type: "words" });
    gsap.fromTo(
      words,
      { opacity: 0.18 },
      {
        opacity: 1,
        ease: "none",
        stagger: 0.1,
        scrollTrigger: { trigger: metin, start: "top 80%", end: "bottom 55%", scrub: true },
      },
    );
  });
}

function kunye() {
  const yazi = document.querySelector<HTMLElement>("[data-kunye]");
  if (!yazi) return;
  const { chars } = SplitText.create(yazi, { type: "chars", mask: "chars" });
  gsap.from(chars, {
    yPercent: 105,
    ease: "none",
    stagger: 0.06,
    scrollTrigger: { trigger: yazi, start: "top bottom", end: "bottom bottom", scrub: 0.8 },
  });
}

function seritHizi(lenis: Lenis) {
  const serit = document.querySelector<HTMLElement>(".serit");
  if (!serit) return;
  const animasyonlar = [...serit.querySelectorAll(".serit-ic")].flatMap((el) => el.getAnimations());
  const egimVer = gsap.quickTo(serit, "skewX", { duration: 0.5, ease: "power3.out" });
  lenis.on("scroll", ({ velocity }: Lenis) => {
    const hiz = 1 + Math.min(Math.abs(velocity) * 0.15, 6);
    animasyonlar.forEach((a) => (a.playbackRate = hiz));
    egimVer(gsap.utils.clamp(-7, 7, velocity * -0.3));
  });
}

if (!matchMedia("(prefers-reduced-motion: reduce)").matches) {
  gsap.registerPlugin(ScrollTrigger, SplitText);
  // Lenis ile GSAP aynı saati kullansın: kaydırma ve animasyonlar aynı karede güncellenir (titreme olmaz)
  const lenis = new Lenis({ anchors: { offset: -96 } }); // -96: yapışkan menünün altında dursun (scroll-mt-24)
  lenis.on("scroll", ScrollTrigger.update);
  gsap.ticker.add((zaman) => lenis.raf(zaman * 1000));
  gsap.ticker.lagSmoothing(0);

  girisSahnesi();
  bolumBasliklari();
  okunanMetinler();
  kunye();
  seritHizi(lenis);
}
