"""Bülten e-postası: HTML + düz metin.

E-posta istemcileri (Gmail, Outlook, Apple Mail) modern CSS'i desteklemez: düzen tablolarla, stiller satır içinde
yazılır; yazı tipleri sistem fontlarıdır. Renkler sitenin "sabah gazetesi" dilinden: kâğıt zemin, mürekkep yazı,
fosfor vurgusu. Dinamik her metin html.escape'ten geçer (ilan başlığında "<" olsa bile e-posta bozulmaz).
"""

import html
from collections.abc import Callable
from datetime import datetime

from internreader.eposta import Eposta
from internreader.isleme.sehir import SEHIRLER
from internreader.yayin import ROL_ADI, TURKIYE_SAATI, seviye_yazisi, tarih_bilgisi, tarih_yazisi

AZAMI_ILAN = 15  # bir e-postada en fazla; kalanlar sonraki bültene kalır

KAGIT, YUZEY, MUREKKEP, IKINCIL, CIZGI, FOSFOR = "#f3efe5", "#fbf9f3", "#16171a", "#4a4e55", "#d6cebb", "#ecdb3d"
SERIF = "Georgia, 'Times New Roman', serif"
SANS = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
CALISMA = {"yerinde": "Ofiste", "hibrit": "Hibrit", "uzaktan": "Uzaktan"}
ALAN_ETIKETI = {"oyun": "Oyun", "savunma": "Savunma/siber/havacılık"}
Baglanti = Callable[[dict], str]  # ilan → "Başvur" adresi


def _konum(ilan: dict) -> str:
    if ilan.get("sehirler"):
        return ", ".join(SEHIRLER[s][0] if s in SEHIRLER else s for s in ilan["sehirler"])
    return "Uzaktan" if ilan.get("uzaktan") else "Konum belirtilmemiş"


def _etiketler(ilan: dict) -> list[str]:
    konum = _konum(ilan)
    parcalar = [seviye_yazisi(ilan), ROL_ADI.get(ilan["rol"], ilan["rol"]), konum]
    parcalar += [ALAN_ETIKETI[x] for x in ilan.get("alanlar", []) if x in ALAN_ETIKETI]
    model = ilan.get("calisma_modeli")
    if model in CALISMA and not (model == "uzaktan" and konum == "Uzaktan"):  # "Uzaktan · Uzaktan" yazmasın
        parcalar.append(CALISMA[model])
    if ilan.get("girisim"):
        parcalar.append("Girişim")
    if ilan.get("yapay_zeka") in ("ozunde", "arti"):
        parcalar.append("yapay zekâ")
    return parcalar


def _html_ilan(ilan: dict, adres: str, adres_goster: bool = False) -> str:
    e = html.escape
    a = ilan.get("ayrinti") or {}
    ozet = (
        f'<p style="margin:8px 0 0;font:15px/1.55 {SANS};color:{IKINCIL}">{e(a["ozet"])}</p>' if a.get("ozet") else ""
    )
    alt = [f"<strong style='color:{MUREKKEP}'>{e(' · '.join(tarih_bilgisi(ilan)))}</strong>"]
    if a.get("hedef"):
        alt.append(e(a["hedef"]))
    if a.get("teknolojiler"):
        alt.append(e(" · ".join(a["teknolojiler"][:5])))
    alt_satir = f'<p style="margin:8px 0 0;font:13px/1.5 {SANS};color:{IKINCIL}">{" &nbsp;|&nbsp; ".join(alt)}</p>'
    if adres_goster:  # önizleme: ilanın gerçek adresi yazıyla (gizlemek için kopyalanır)
        not_ = f"<strong>{e(ilan['onizleme_notu'])}</strong><br>" if ilan.get("onizleme_notu") else ""
        alt_satir += (
            f'<p style="margin:8px 0 0;font:13px/1.5 {SANS};color:{IKINCIL};word-break:break-all">{not_}'
            f'{e(ilan.get("kaynak", ""))} · <a href="{e(ilan["url"])}" style="color:{MUREKKEP}">{e(ilan["url"])}</a></p>'
        )
    return f"""
<tr><td style="padding:20px 0;border-top:1px solid {CIZGI}">
  <p style="margin:0;font:600 12px/1.4 {SANS};letter-spacing:.02em;color:{IKINCIL}">{e(ilan.get("firma_gorunen") or ilan["firma"])}</p>
  <p style="margin:6px 0 0;font:600 19px/1.3 {SERIF};color:{MUREKKEP}">{e(ilan["baslik"])}</p>
  <p style="margin:6px 0 0;font:13px/1.5 {SANS};color:{IKINCIL}">{e(" · ".join(_etiketler(ilan)))}</p>
  {ozet}{alt_satir}
  <p style="margin:12px 0 0"><a href="{e(adres)}" style="display:inline-block;padding:9px 16px;border-radius:999px;background:{MUREKKEP};color:{KAGIT};font:600 14px {SANS};text-decoration:none">Başvur &rarr;</a></p>
</td></tr>"""


def _metin_ilan(no: int, ilan: dict) -> str:
    a = ilan.get("ayrinti") or {}
    satirlar = [
        f"{no}) {ilan.get('firma_gorunen') or ilan['firma']} — {ilan['baslik']}",
        "   " + " · ".join(_etiketler(ilan)),
    ]
    if a.get("ozet"):
        satirlar.append(f"   {a['ozet']}")
    satirlar.append("   " + " · ".join(tarih_bilgisi(ilan)))
    if ilan.get("onizleme_notu"):
        satirlar.append(f"   {ilan['onizleme_notu']}")
    satirlar.append(f"   Başvur: {ilan['url']}")
    return "\n".join(satirlar)


def _eposta(
    alici: str,
    konu: str,
    baslik_html: str,
    giris: str,
    ilanlar: list[dict],
    an: datetime,
    site_adresi: str,
    iptal_adresi: str,
    tek_tik_adresi: str,
    bolum: str = "",
    baglanti: Baglanti | None = None,
    adres_goster: bool = False,
) -> Eposta:
    """Bültenin ve hoş geldin e-postasının ortak gövdesi. `baslik_html` kaçışlanmış olmalı; `bolum`: ilanların üst başlığı.
    `baglanti`: "Başvur" düğmesinin adresini üretir (tıklama ölçümü); düz metin sürümü doğrudan ilana gider.
    `adres_goster`: her ilanın adresi yazıyla da görünür (elle onay önizlemesi)."""
    e = html.escape
    gun = tarih_yazisi(an.astimezone(TURKIYE_SAATI))
    on_metin = " · ".join(f"{i.get('firma_gorunen') or i['firma']}: {i['baslik']}" for i in ilanlar[:3]) or konu
    bolum_html = (
        f'<tr><td style="padding:16px 32px 0"><p style="margin:0;font:600 13px {SANS};letter-spacing:.04em;'
        f'text-transform:uppercase;color:{IKINCIL}">{e(bolum)}</p></td></tr>'
        if bolum
        else ""
    )
    govde = "".join(_html_ilan(i, baglanti(i) if baglanti else i["url"], adres_goster) for i in ilanlar)
    html_metin = f"""<!doctype html>
<html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>{e(konu)}</title></head>
<body style="margin:0;padding:0;background:{KAGIT}">
<div style="display:none;max-height:0;overflow:hidden;opacity:0">{e(on_metin)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{KAGIT}"><tr><td align="center" style="padding:28px 12px">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:{YUZEY};border:1px solid {CIZGI};border-radius:14px">
<tr><td style="padding:28px 32px 8px">
  <p style="margin:0;font:600 12px {SANS};letter-spacing:.08em;text-transform:uppercase;color:{IKINCIL}">InternReader · {e(gun)}</p>
  <h1 style="margin:14px 0 0;font:600 28px/1.15 {SERIF};color:{MUREKKEP}">{baslik_html}</h1>
  <p style="margin:12px 0 0;font:15px/1.55 {SANS};color:{IKINCIL}">{e(giris)}</p>
</td></tr>{bolum_html}
<tr><td style="padding:8px 32px 12px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0">{govde}</table></td></tr>
<tr><td style="padding:20px 32px 28px;border-top:1px solid {CIZGI}">
  <p style="margin:0;font:13px/1.6 {SANS};color:{IKINCIL}">Bu e-postayı InternReader bültenine abone olduğun için aldın. Yapay zekâ hata yapabilir; başvurmadan önce ilanı şirketin sayfasında oku.</p>
  <p style="margin:10px 0 0;font:13px/1.6 {SANS};color:{IKINCIL}"><a href="{e(site_adresi)}/#bulten" style="color:{MUREKKEP}">Tercihlerini değiştir</a> &nbsp;·&nbsp; <a href="{e(iptal_adresi)}" style="color:{MUREKKEP}">Abonelikten çık</a> &nbsp;·&nbsp; <a href="{e(site_adresi)}/kvkk" style="color:{MUREKKEP}">KVKK</a></p>
</td></tr>
</table></td></tr></table></body></html>"""

    metin = "\n\n".join(
        [
            f"InternReader · {gun}",
            konu,
            giris,
            *([bolum] if bolum else []),
            *(_metin_ilan(no, i) for no, i in enumerate(ilanlar, start=1)),
            "—",
            f"Tercihlerini değiştir: {site_adresi}/#bulten\nAbonelikten çık: {iptal_adresi}",
        ]
    )
    return Eposta(
        alici=alici,
        konu=konu,
        metin=metin,
        html=html_metin,
        basliklar={
            # Gmail/Yahoo toplu gönderici kuralları: tek tıkla çıkış (RFC 8058)
            "List-Unsubscribe": f"<{tek_tik_adresi}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        },
    )


def bulten_epostasi(
    alici: str,
    ilanlar: list[dict],
    an: datetime,
    site_adresi: str,
    iptal_adresi: str,
    tek_tik_adresi: str,
    siklik: str,
    baglanti: Baglanti | None = None,
) -> Eposta:
    """`ilanlar` en fazla AZAMI_ILAN olmalı (çağıran keser). iptal_adresi: sayfa; tek_tik_adresi: RFC 8058 POST adresi."""
    n = len(ilanlar)
    donem = "Bugün" if siklik == "gunluk" else "Bu hafta"
    return _eposta(
        alici,
        f"{donem} sana uygun {n} yeni staj ilanı",
        f'{donem} sana uygun <span style="background:{FOSFOR};color:{MUREKKEP};padding:0 4px">{n} yeni ilan</span>',
        "Şirketlerin kendi sayfalarından, seçtiğin şehir, alan ve seviyeye göre ayıklandı. Başvuru şirketin kendi sayfasında.",
        ilanlar,
        an,
        site_adresi,
        iptal_adresi,
        tek_tik_adresi,
        baglanti=baglanti,
    )


def hos_geldin_epostasi(
    alici: str,
    ilanlar: list[dict],
    tam_uyan: bool,
    an: datetime,
    site_adresi: str,
    iptal_adresi: str,
    tek_tik_adresi: str,
    siklik: str,
    baglanti: Baglanti | None = None,
) -> Eposta:
    """Abonelik onaylanınca giden e-posta. `tam_uyan` değilse ilanlar yakın ilanlardır ya da liste boştur."""
    sonraki = (
        "Bundan sonra yeni ilan çıktığı sabahlar e-postanda."
        if siklik == "gunluk"
        else "Bundan sonra yeni ilanlar her pazartesi sabahı e-postanda."
    )
    if tam_uyan:
        n = len(ilanlar)
        return _eposta(
            alici,
            f"Şu an sana uygun {n} ilan",
            f'Şu an sana uygun <span style="background:{FOSFOR};color:{MUREKKEP};padding:0 4px">{n} ilan</span>',
            f"Aboneliğin başladı. Bunlar şu an açık olan, seçimlerine uyan ilanlar. {sonraki}",
            ilanlar,
            an,
            site_adresi,
            iptal_adresi,
            tek_tik_adresi,
            baglanti=baglanti,
        )
    konu = "Şu an seçimlerine tam uyan ilan yok"
    giris = f"Aboneliğin başladı. Şu an seçimlerine tam uyan ilan yok; çıkınca ilk sen öğreneceksin. {sonraki}"
    return _eposta(
        alici,
        konu,
        konu,
        giris,
        ilanlar,
        an,
        site_adresi,
        iptal_adresi,
        tek_tik_adresi,
        bolum="Yakın ilanlar: tercihlerine tam uymuyor" if ilanlar else "",
        baglanti=baglanti,
    )


def sessizlik_epostasi(
    alici: str,
    ilanlar: list[dict],
    firma_sayisi: int,
    an: datetime,
    site_adresi: str,
    iptal_adresi: str,
    tek_tik_adresi: str,
    baglanti: Baglanti | None = None,
) -> Eposta:
    """Pazartesi, bir haftadır e-posta almamış aboneye: "bu hafta sana uyan yeni ilan çıkmadı" + yakın ilanlar.
    `ilanlar` boş olamaz: yakın ilan yoksa çağıran e-posta göndermez."""
    konu = "Bu hafta sana uyan yeni ilan çıkmadı"
    taranan = f"{firma_sayisi:,}".replace(",", ".") + " şirketin" if firma_sayisi else "Şirketlerin"
    giris = (
        f"{taranan} ilan sayfasını her gün taradık; bu hafta seçimlerine uyan yeni ilan çıkmadı. Çıkınca ilk sen "
        "öğreneceksin. Bu arada tercihlerine yakın, şu an açık birkaç ilan:"
    )
    return _eposta(
        alici,
        konu,
        konu,
        giris,
        ilanlar,
        an,
        site_adresi,
        iptal_adresi,
        tek_tik_adresi,
        bolum="Yakın ilanlar: tercihlerine tam uymuyor",
        baglanti=baglanti,
    )


def onizleme_epostasi(
    alici: str, ilanlar: list[dict], an: datetime, site_adresi: str, iptal_adresi: str, tek_tik_adresi: str
) -> Eposta:
    """Elle onay modunda sabah önizlemesi (yalnızca proje sahibine): bültene girebilecek yeni ilanların hepsi,
    adresleriyle. Bağlantılar doğrudan ilana gider; tıklama ölçümüne girmez."""
    n = len(ilanlar)
    return _eposta(
        alici,
        f"[ÖNİZLEME] Onay bekleyen {n} yeni ilan",
        f'Onay bekleyen <span style="background:{FOSFOR};color:{MUREKKEP};padding:0 4px">{n} yeni ilan</span>',
        "Son bültenden sonra ilk kez görülen ilanların hepsi (tercih, 15 ilan ve firma sınırı yok). Yanlış olanın "
        "adresini kopyala: GitHub → Actions → İlan gizle. Hepsi doğruysa: Actions → Bülteni gönder. Göndermezsen bu "
        "ilanlar yarınki önizlemede de görünür.",
        ilanlar,
        an,
        site_adresi,
        iptal_adresi,
        tek_tik_adresi,
        adres_goster=True,
    )
