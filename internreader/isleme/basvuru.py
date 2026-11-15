"""Başvuru sayfasından muhafazakâr kanıt çıkarımı; ağ ve veritabanından bağımsız.

200, başlığın listede olması veya yalnızca JobPosting bulunması açık kanıtı değildir.
Yalnızca tek ilanın alanında kapanış veya etkin başvuru kontrolü aranır. Belirsizlikte tahmin edilmez.
"""

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Literal
from urllib.parse import parse_qs, urlsplit


@dataclass(frozen=True)
class BasvuruSonucu:
    durum: Literal["acik", "kapali", "belirsiz"]
    neden: str


def normal(metin: str) -> str:
    return " ".join(metin.replace("İ", "I").casefold().split())


class _Sayfa(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.yigin = []
        self.metin = []
        self.basliklar = []
        self.durum_metinleri = []
        self.kontroller = []
        self.kontrol = None
        self.baslik = None
        self.kartlar = []
        self.kart_yigini = []
        self.kart_basligi = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        atla = tag in {"script", "style", "noscript", "template", "head", "nav", "header", "footer", "aside"}
        atla = atla or bool(
            re.search(r"related|recommended|similar[-_ ]?jobs", a.get("class", "") + " " + a.get("id", ""), re.I)
        )
        gizli = (
            "hidden" in a
            or "inert" in a
            or a.get("aria-hidden") == "true"
            or a.get("aria-disabled") == "true"
            or (tag == "fieldset" and "disabled" in a)
            or bool(re.search(r"display\s*:\s*none|visibility\s*:\s*hidden", a.get("style", ""), re.I))
        )
        if tag not in {"input", "br", "hr", "img", "meta", "link", "source", "wbr", "area", "embed"}:
            self.yigin.append((tag, atla or gizli or any(x[1] for x in self.yigin)))
        if atla or gizli or any(x[1] for x in self.yigin):
            return
        if tag in {"article", "li"} and re.search(
            r"(?:^|[\s_-])(?:job|position|opening|vacancy)(?:[\s_-]|$)",
            a.get("class", "") + " " + a.get("id", ""),
            re.I,
        ):
            kart = {"basliklar": [], "kontroller": []}
            self.kartlar.append(kart)
            self.kart_yigini.append((len(self.yigin), kart))
        if tag == "h1":
            self.baslik = []
        if tag in {"h2", "h3"} and self.kart_yigini:
            self.kart_basligi = []
        if tag in {"button", "a"}:
            etkin = "disabled" not in a and a.get("aria-disabled") != "true"
            if tag == "button":
                etkin = etkin and a.get("type", "").lower() in {"", "button", "submit"}
            hedef = a.get("href", "")
            self.kontrol = (tag, etkin, hedef, [])
        if tag == "input" and a.get("type", "").lower() == "submit":
            etkin = "disabled" not in a and any(t == "form" for t, _ in self.yigin)
            kontrol = ("input", etkin, "", a.get("value", ""))
            self.kontroller.append(kontrol)
            if self.kart_yigini:
                self.kart_yigini[-1][1]["kontroller"].append(kontrol)

    def handle_endtag(self, tag):
        if tag == "h1" and self.baslik is not None:
            self.basliklar.append(normal(" ".join(self.baslik)))
            self.baslik = None
        if tag in {"h2", "h3"} and self.kart_basligi is not None:
            if self.kart_yigini:
                self.kart_yigini[-1][1]["basliklar"].append(normal(" ".join(self.kart_basligi)))
            self.kart_basligi = None
        if tag in {"button", "a"} and self.kontrol is not None and self.kontrol[0] == tag:
            t, etkin, hedef, metin = self.kontrol
            kontrol = (t, etkin, hedef, " ".join(metin))
            self.kontroller.append(kontrol)
            if self.kart_yigini:
                self.kart_yigini[-1][1]["kontroller"].append(kontrol)
            self.kontrol = None
        if self.kart_yigini and len(self.yigin) == self.kart_yigini[-1][0] and self.yigin[-1][0] == tag:
            self.kart_yigini.pop()
        for i in range(len(self.yigin) - 1, -1, -1):
            if self.yigin[i][0] == tag:
                del self.yigin[i:]
                break

    def handle_data(self, data):
        if any(x[1] for x in self.yigin):
            return
        self.metin.append(data)
        self.durum_metinleri.append(normal(data).strip(" .!"))
        if self.baslik is not None:
            self.baslik.append(data)
        if self.kart_basligi is not None:
            self.kart_basligi.append(data)
        if self.kontrol is not None:
            self.kontrol[3].append(data)


_KAPALI = re.compile(
    r"(?:we are )?no longer accepting applications(?: for this (?:position|role|job))?|applications (?:are |have been )?closed|"
    r"this (?:job|position|vacancy) (?:is (?:now )?closed|has been (?:filled|closed))|"
    r"şu an başvuru kabul etmiyor|artık başvuru kabul (?:etmiyor|edilmiyor)|"
    r"başvurular (?:kapanmıştır|kapanmış|kapandı|kapatılmıştır|kapalıdır|sona ermiştir)|"
    r"bu (?:ilan|pozisyon) (?:kapanmıştır|kapatılmıştır|için başvurular kapanmıştır)"
)
_BASVUR = re.compile(
    r"^(?:apply(?: now| for (?:this (?:job|position|role)|the role))?|submit application|başvur|hemen başvur|başvuruyu gönder)$"
)
_ENGEL = re.compile(
    r"verify you are human|checking your browser|just a moment|access denied|captcha|oturum açın|sign in to continue"
)
YASAK_ALANLAR = ("linkedin.com", "kariyer.net", "youthall.com", "jooble.org")


def alan_yasak(url: str) -> bool:
    alan = (urlsplit(url).hostname or "").lower()
    return any(alan == a or alan.endswith("." + a) for a in YASAK_ALANLAR)


def _etkin_basvuru(kontroller: list[tuple[str, bool, str, str]]) -> bool:
    for tag, etkin, hedef, yazi in kontroller:
        if not etkin or not _BASVUR.fullmatch(normal(yazi)):
            continue
        if tag == "a" and (not hedef or hedef.startswith("#") or urlsplit(hedef).scheme not in {"", "http", "https"}):
            continue
        return True
    return False


def _tek_ilan_basligi(basliklar: list[str], baslik: str) -> bool:
    if len(basliklar) != 1:
        return False
    asil = normal(baslik)
    h1 = basliklar[0]
    return h1 == asil or (h1.startswith(asil + " - ") and "careers" in h1[len(asil) :])


def sayfayi_dogrula(baslik: str, url: str, son_url: str, html: str) -> BasvuruSonucu:
    if urlsplit(url).fragment:
        return BasvuruSonucu("belirsiz", "coklu_ilan_sayfasi")
    once, sonra = urlsplit(url), urlsplit(son_url)
    yonlendi = (once.hostname, once.path.rstrip("/")) != (sonra.hostname, sonra.path.rstrip("/"))
    liste_yolu = sonra.path.rstrip("/").casefold() in {"/careers", "/career", "/kariyer", "/jobs", "/is-ilanlari"}
    sayfa = _Sayfa()
    sayfa.feed(html)
    metin = normal(" ".join(sayfa.metin))
    if _ENGEL.search(metin):
        return BasvuruSonucu("belirsiz", "erisim_dogrulama_veya_giris_engeli")
    # Yönlendirmede genel sayfanın metni başka ilana ait olabilir; önce tek ilanı doğrula.
    if _tek_ilan_basligi(sayfa.basliklar, baslik) and not (yonlendi and liste_yolu):
        if any(_KAPALI.fullmatch(m) for m in sayfa.durum_metinleri):
            return BasvuruSonucu("kapali", "ilan_sayfasinda_acik_kapanis_ifadesi")
        if _etkin_basvuru(sayfa.kontroller):
            return BasvuruSonucu("acik", "ilan_sayfasinda_etkin_basvuru_kontrolu")
    elif (
        once.hostname == "jobs.lever.co"
        and not yonlendi
        and len(once.path.strip("/").split("/")) == 2
        and not sayfa.basliklar
        and metin.startswith(normal(baslik) + " ")
        and any(
            etkin and normal(yazi) == "apply for this job" and hedef.rstrip("/") == url.rstrip("/") + "/apply"
            for tag, etkin, hedef, yazi in sayfa.kontroller
            if tag == "a"
        )
    ):
        return BasvuruSonucu("acik", "lever_ilanina_ozel_basvuru_baglantisi")
    elif (
        once.hostname == "curiosity.tech"
        and once.path.endswith("/careers/apply")
        and not yonlendi
        and parse_qs(once.query).get("title") == [baslik]
        and sayfa.basliklar == ["başvuru formu"]
        and normal(baslik) in metin
        and _etkin_basvuru(sayfa.kontroller)
    ):
        return BasvuruSonucu("acik", "ilana_ozel_basvuru_formu")
    elif yonlendi:
        # Genel kariyer sayfasında yalnızca aynı başlıklı, sınırları belirli tek kartın bağlantısı kanıttır.
        eslesenler = [k for k in sayfa.kartlar if k["basliklar"] == [normal(baslik)]]
        if len(eslesenler) == 1 and _etkin_basvuru(eslesenler[0]["kontroller"]):
            return BasvuruSonucu("acik", "yonlendirilen_listede_eslesen_ilan_karti")
        return BasvuruSonucu("belirsiz", "baska_sayfaya_yonlendi")
    else:
        return BasvuruSonucu("belirsiz", "tek_ilan_basligi_dogrulanamadi")
    return BasvuruSonucu("belirsiz", "basvuru_durumu_icin_yeterli_kanit_yok")
