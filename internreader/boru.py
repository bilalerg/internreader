"""İş akışı (boru hattı): katmanları sırayla bağlar. Burada iş mantığı yok, sadece düzen var.

tara():    firmalar → [ATS toplayıcıları | kariyer sayfası + yapay zekâ] → tekilleştir → veritabanı
           → konum ön seçimi → (yalnızca yeni ilanlar) yapay zekâ sınıflandırma → veritabanı
yayinla(): veritabanı → README tablosu + JSON + (yeni ilan varsa) WhatsApp özeti
"""

import hashlib
import json
import logging
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import requests
from sqlalchemy.orm import sessionmaker

from internreader import depo
from internreader.ag import HttpIstemci, RobotsEngeli
from internreader.ayar import CIKTI, Ayarlar
from internreader.isleme.filtre import konum_uygun, yedek_siniflandirma
from internreader.isleme.tekillestirme import tekillestir
from internreader.kaynaklar.ats import TOPLAYICILAR
from internreader.kaynaklar.kariyer_sayfasi import html_ayikla, ilan_bolumu, ilan_metni, sayfa_oku
from internreader.model import FirmaBilgisi
from internreader.yayin import TURKIYE_SAATI, zenginlestir
from internreader.yayin.istatistik import istatistik_metni
from internreader.yayin.json_disa import json_metni
from internreader.yayin.readme import tablo_metni
from internreader.yayin.whatsapp import ozet_metni, taze_mi
from internreader.yz.ayrinti_cikarici import ayrintilari_cikar, metin_ozeti
from internreader.yz.istemci import YzIstemci, YzKullanilamaz
from internreader.yz.sayfa_okuyucu import ilanlara_cevir, sayfalari_oku
from internreader.yz.siniflandirici import siniflandir, siniflandirma_imzasi

kayit = logging.getLogger(__name__)


@dataclass
class TaramaRaporu:
    ats_firma: int = 0
    sayfa_firma: int = 0
    ats_ilan: int = 0
    sayfa_ilan: int = 0
    sayfa_durumlari: Counter = field(default_factory=Counter)
    toplam_ilan: int = 0
    yeni_ilan: int = 0
    kapanan_ilan: int = 0
    siniflandirilan: int = 0
    yedek_karar: int = 0
    imzadan: int = 0  # yeniden yayınlanan ilan: eski karar kullanıldı, yapay zekâya gidilmedi
    yz_usd: float = 0.0
    hatalar: list[str] = field(default_factory=list)
    yalnizca_ats: bool = False  # ara tarama: kariyer sayfaları okunmadı


# ---------------- toplama ----------------
def _ats_tara(http: HttpIstemci, firmalar: list[FirmaBilgisi], is_parcacigi: int):
    """(ilanlar, başarılı firma adları, hata metinleri, panosu kaldırılmış firma id'leri) döndürür."""

    def tek(f: FirmaBilgisi):
        try:
            ilanlar = TOPLAYICILAR[f.ats](http, f.ad, f.slug)
            for i in ilanlar:
                i.etiket = f.etiket
            return f, ilanlar, None
        except Exception as hata:  # tek firmanın hatası bütün taramayı durdurmaz
            return f, [], hata

    ilanlar, basarili, hatalar, kaldirilan = [], set(), [], []
    with ThreadPoolExecutor(max_workers=is_parcacigi) as havuz:
        for f, liste, hata in havuz.map(tek, firmalar):
            if hata is None:
                basarili.add(f.ad)
                ilanlar += liste
                continue
            hatalar.append(f"{f.ad} ({f.ats}): {str(hata)[:100]}")
            # 404: firma bu sistemdeki ilan panosunu kapatmış/taşımış → kayıt sıfırlanır, keşif yeniden bulur
            if isinstance(hata, requests.HTTPError) and getattr(hata.response, "status_code", None) == 404:
                kaldirilan.append(f.id)
    return ilanlar, basarili, hatalar, kaldirilan


def _sayfalari_indir(http: HttpIstemci, firmalar: list[FirmaBilgisi], is_parcacigi: int):
    """1. aşama (yalnızca ağ): kariyer sayfalarını paralel indirir. [(firma, durum, içerik | None)]"""

    def tek(f: FirmaBilgisi):
        try:
            return f, "indirildi", sayfa_oku(http, f.kariyer)
        except RobotsEngeli:
            return f, "robots-engeli", None
        except requests.RequestException:
            return f, "erisilemedi", None
        except Exception as hata:  # bozuk HTML vb. beklenmeyen durum tek firmayı etkiler, taramayı değil
            kayit.warning("%s: sayfa işlenemedi (%s: %s)", f.ad, type(hata).__name__, str(hata)[:100])
            return f, "hata", None

    with ThreadPoolExecutor(max_workers=is_parcacigi) as havuz:
        return list(havuz.map(tek, firmalar))


def _sayfalari_tara(http: HttpIstemci, yz: YzIstemci, firmalar: list[FirmaBilgisi], onbellek: dict, ayar: Ayarlar):
    """İndirilen sayfalardan değişmeyenler önbellekten, değişenler yapay zekâyla (2. aşama) okunur."""
    ilanlar, basarili, yeni_onbellek, durumlar = [], set(), {}, Counter()
    okunacak = []
    for f, durum, icerik in _sayfalari_indir(http, firmalar, ayar.is_parcacigi):
        if icerik is None:
            durumlar[durum] += 1
            continue
        u_ozet, i_ozet = depo.url_ozeti(f.kariyer), hashlib.sha256(icerik.metin.encode()).hexdigest()
        eski = onbellek.get(u_ozet)
        if eski and eski[0] == i_ozet:  # sayfa aynı → yapay zekâya gitme, önceki sonucu kullan
            durumlar["degismedi"] += 1
            basarili.add(f.ad)
            ilanlar += ilanlara_cevir(f, f.kariyer, eski[1])
        else:
            okunacak.append((f, icerik, u_ozet, i_ozet))
    kayit.info("Kariyer sayfaları indirildi: %s | yapay zekâyla okunacak: %d", dict(durumlar), len(okunacak))

    sonuclar = sayfalari_oku(yz, [(u_ozet, f.ad, icerik) for f, icerik, u_ozet, _ in okunacak], ayar.yz_is_parcacigi)
    for f, _, u_ozet, i_ozet in okunacak:
        sonuc = sonuclar[u_ozet]
        if isinstance(sonuc, YzKullanilamaz):
            durumlar["yz-kapali"] += 1
        elif isinstance(sonuc, Exception):
            kayit.warning("%s: sayfa yapay zekâyla okunamadı (%s)", f.ad, sonuc)
            durumlar["yz-hatasi"] += 1
        else:
            durumlar["okundu"] += 1
            basarili.add(f.ad)
            ilanlar += ilanlara_cevir(f, f.kariyer, sonuc)
            yeni_onbellek[f.kariyer] = (u_ozet, i_ozet, sonuc)
    return ilanlar, basarili, yeni_onbellek, durumlar


def yz_olustur(ayar: Ayarlar, oturum: sessionmaker) -> YzIstemci:
    """Bir çalıştırmanın yapay zekâ istemcisi: tavan = min(çalıştırma tavanı, aylıktan kalan). Bir çalıştırmadaki
    bütün yapay zekâ işleri (sayfa okuma, sınıflandırma, ayrıntı) bu tek istemciyi ve bütçesini paylaşır."""
    with oturum() as o:
        bu_ay = depo.bu_ay_harcanan(o)
    tavan = max(0.0, min(ayar.calisma_basina_yz_tavani_usd, ayar.aylik_yz_tavani_usd - bu_ay))
    kayit.info(
        "Yapay zekâ: bu ay %.4f $ harcandı (aylık tavan %.2f $) → bu çalıştırmanın tavanı %.4f $%s",
        bu_ay,
        ayar.aylik_yz_tavani_usd,
        tavan,
        " · toplu mod (yarı fiyat)" if ayar.yz_toplu else "",
    )
    return YzIstemci(ayar.model, tavan, toplu=ayar.yz_toplu)


def tara(
    ayar: Ayarlar,
    oturum: sessionmaker,
    http: HttpIstemci | None = None,
    yz: YzIstemci | None = None,
    yalnizca_ats: bool = False,
) -> TaramaRaporu:
    """`yalnizca_ats`: ara tarama. Yalnızca ilan sistemleri okunur; kariyer sayfaları (yapay zekâyla okunduğu için pahalı)
    ve onların ilanları günlük tam taramaya kalır. Yapay zekâ yalnızca yeni ilanları sınıflar."""
    http = http or HttpIstemci(ayar.kullanici_ajani, ayar.http_zaman_asimi)
    yz = yz or yz_olustur(ayar, oturum)
    kullanim_basi = len(yz.kullanimlar)
    rapor = TaramaRaporu(yalnizca_ats=yalnizca_ats)

    with oturum() as o:
        firmalar = depo.aktif_firmalar(o)
        onbellek = depo.onbellek_hepsi(o)
    ats_firmalari = [f for f in firmalar if f.ats in TOPLAYICILAR]
    sayfa_firmalari = [] if yalnizca_ats else [f for f in firmalar if f.kariyer and f.ats not in TOPLAYICILAR]
    rapor.ats_firma, rapor.sayfa_firma = len(ats_firmalari), len(sayfa_firmalari)
    kayit.info(
        "Taranacak: %d firma ilan sisteminden, %d firma kariyer sayfasından", *[rapor.ats_firma, rapor.sayfa_firma]
    )

    ats_ilanlari, ats_basarili, rapor.hatalar, kaldirilan = _ats_tara(http, ats_firmalari, ayar.is_parcacigi)
    if kaldirilan:
        with oturum.begin() as o:
            depo.ats_kaydini_sifirla(o, kaldirilan)
        kayit.info("%d firmanın ilan panosu bulunamadı (404); bir sonraki keşifte yeniden aranacak", len(kaldirilan))
    rapor.ats_ilan = len(ats_ilanlari)
    kayit.info("İlan sistemlerinden %d ilan (%d firma hata verdi)", rapor.ats_ilan, len(rapor.hatalar))

    sayfa_ilanlari, sayfa_basarili, yeni_onbellek = [], set(), {}
    if not yalnizca_ats:
        sayfa_ilanlari, sayfa_basarili, yeni_onbellek, rapor.sayfa_durumlari = _sayfalari_tara(
            http, yz, sayfa_firmalari, onbellek, ayar
        )
    rapor.sayfa_ilan = len(sayfa_ilanlari)
    kayit.info("Kariyer sayfalarından %d ilan | %s", rapor.sayfa_ilan, dict(rapor.sayfa_durumlari))

    ilanlar = tekillestir(ats_ilanlari + sayfa_ilanlari)
    rapor.toplam_ilan = len(ilanlar)
    with oturum.begin() as o:
        yeniler, rapor.kapanan_ilan = depo.ilanlari_kaydet(
            o, ilanlar, ats_basarili | sayfa_basarili, sayfa_ilanlari_korunsun=yalnizca_ats
        )
        depo.onbellek_yaz(o, yeni_onbellek)
    rapor.yeni_ilan = len(yeniler)

    # Yalnızca konumu uygun ve daha önce yapay zekâyla sınıflanmamış ilanlar sınıflandırmaya gider
    adaylar = [i for i in ilanlar if konum_uygun(i)]
    with oturum() as o:
        bekleyen = depo.siniflandirilmamislar(o, [i.kimlik for i in adaylar])
    siniflanacak = [i for i in adaylar if i.kimlik in bekleyen]
    # Yeniden yayınlanan ilan: aynı imzalı eski karar varsa yapay zekâya gidilmez
    imzalar = {i.kimlik: siniflandirma_imzasi(i) for i in siniflanacak}
    with oturum() as o:
        eski_kararlar = depo.imzayla_kararlar(o, imzalar.values())
    imzadan = {k: {**eski_kararlar[im], "imza": im} for k, im in imzalar.items() if im in eski_kararlar}
    siniflanacak = [i for i in siniflanacak if i.kimlik not in imzadan]
    kayit.info(
        "Sınıflandırılacak yeni ilan: %d (konumu uygun toplam: %d, eski karardan: %d)",
        len(siniflanacak),
        len(adaylar),
        len(imzadan),
    )
    sonuclar = siniflandir(yz, siniflanacak, ayar.yz_is_parcacigi) if siniflanacak else {}
    sonuclar = {k: {**v, "imza": imzalar[k]} for k, v in sonuclar.items()}
    yedekler = {i.kimlik: yedek_siniflandirma(i) for i in siniflanacak if i.kimlik not in sonuclar}

    rapor.siniflandirilan, rapor.yedek_karar, rapor.yz_usd = len(sonuclar), len(yedekler), round(yz.harcanan_usd, 4)
    rapor.imzadan = len(imzadan)
    with oturum.begin() as o:
        depo.siniflandirma_kaydet(o, sonuclar, yz.model)
        depo.siniflandirma_kaydet(o, imzadan, "imza")
        depo.siniflandirma_kaydet(o, yedekler, "kural")  # bir sonraki çalıştırmada yapay zekâyla yeniden denenir
        depo.kullanim_yaz(o, yz.kullanimlar[kullanim_basi:])
        # İzleme: son taramanın özeti ("durum" komutu gösterir; sunucuda sorun tek bakışta görülür)
        # (asdict kullanılmaz: Counter alanını bozuyor — anahtarları demete çeviriyor)
        ozet = {**vars(rapor), "sayfa_durumlari": dict(rapor.sayfa_durumlari), "zaman": datetime.now(UTC).isoformat()}
        depo.durum_yaz(o, "son_tarama", json.dumps(ozet, ensure_ascii=False))
    kayit.info(
        "Sınıflandırılan: %d | yedek kural: %d | yapay zekâ maliyeti: %.4f $",
        rapor.siniflandirilan,
        rapor.yedek_karar,
        rapor.yz_usd,
    )
    return rapor


# ---------------- ayrıntılar ----------------
def ayrintilari_zenginlestir(
    ayar: Ayarlar,
    oturum: sessionmaker,
    http: HttpIstemci | None = None,
    yz: YzIstemci | None = None,
    sinir: int = 40,
    yalnizca_ats: bool = False,
) -> dict:
    """Öğrenciye uygun ve ayrıntısı olmayan ilanlar için metni bulur (ATS açıklaması, ilanın kendi sayfası ya da
    ilanların tek sayfada listelendiği kariyer sayfasındaki bölümü) ve yapay zekâyla özet, son başvuru, ilan tarihi,
    hedef sınıf, çalışma modeli, ücret, teknolojiler çıkarır. Sayfalar robots.txt'ye uyarak okunur (HttpIstemci);
    aynı kariyer sayfası bir çalıştırmada bir kez indirilir."""
    http = http or HttpIstemci(ayar.kullanici_ajani, ayar.http_zaman_asimi)
    yz = yz or yz_olustur(ayar, oturum)
    kullanim_basi = len(yz.kullanimlar)
    with oturum() as o:
        bekleyenler = depo.ayrinti_bekleyenler(o, sinir, yalnizca_ats)
        liste_sayfalari = depo.sayfa_basliklari(
            o, {i["url"].split("#")[0] for i in bekleyenler if i["kaynak"] == "kariyer_sayfasi" and "#" in i["url"]}
        )
    adresler = {
        i["url"].split("#")[0] for i in bekleyenler if i["kaynak"] == "kariyer_sayfasi" and not i["aciklama"].strip()
    }

    def indir(adres: str) -> tuple[str, str | None]:
        try:
            return adres, http.sayfa(adres)[1]
        except (requests.RequestException, RobotsEngeli, ValueError):
            return adres, None  # bugün okunamadı: yarın yeniden denenir

    with ThreadPoolExecutor(max_workers=ayar.is_parcacigi) as havuz:
        sayfalar = dict(havuz.map(indir, adresler))

    def metni_bul(ilan: dict) -> tuple[dict, str | None]:
        if ilan["aciklama"].strip():
            return ilan, ilan["aciklama"]
        if ilan["kaynak"] != "kariyer_sayfasi":
            return ilan, ""  # metin yok
        adres, capa, _ = ilan["url"].partition("#")
        ham = sayfalar[adres]
        if ham is None:
            return ilan, None
        if not capa:  # ilanın kendi sayfası var: menü ve alt bilgi modele gitmez
            return ilan, ilan_metni(ham, ilan["baslik"])
        # Tek sayfada listelenen ilan: sayfadan yalnızca bu ilanın bölümü (bulunamazsa yalnızca başlık vardı)
        return ilan, ilan_bolumu(html_ayikla(ham, adres).metin, ilan["baslik"], liste_sayfalari.get(adres, []))

    metinler = [metni_bul(i) for i in bekleyenler]
    isler = [(i["kimlik"], i["baslik"], i["firma"], m) for i, m in metinler if m]
    bos = [i["kimlik"] for i, m in metinler if m == ""]
    bugun = datetime.now(TURKIYE_SAATI).date()
    sonuclar = ayrintilari_cikar(yz, isler, bugun, ayar.yz_is_parcacigi) if isler else {}
    metin_haritasi = {k: m for k, _, _, m in isler}
    rapor = {"bekleyen": len(bekleyenler), "cikarilan": 0, "metinsiz": len(bos), "hata": 0, "rol_degisen": 0}
    with oturum.begin() as o:
        for kimlik, sonuc in sonuclar.items():
            if isinstance(sonuc, Exception):
                rapor["hata"] += 1
                continue
            depo.ayrinti_kaydet(o, kimlik, sonuc, metin_ozeti(metin_haritasi[kimlik]), yz.model)
            rapor["cikarilan"] += 1
            # Sınıflandırıcı çoğu zaman yalnızca başlığı görür; rol kararını metnin tamamını gören çıkarıcı düzeltir.
            # Eğitim ve yarışmada görev yoktur, rol düzeltilmez ("Cloud Camp" kendi etiketiyle yayında kalır).
            if sonuc.get("ilan_turu", "is") == "is":
                rapor["rol_degisen"] += depo.rol_guncelle(o, kimlik, sonuc.get("rol"))
        for kimlik in bos:  # tekrar denenmesin diye boş kayıt
            depo.ayrinti_kaydet(o, kimlik, {}, "metin-yok", "metin-yok")
        depo.kullanim_yaz(o, yz.kullanimlar[kullanim_basi:])
    kayit.info("Ayrıntılar: %s", rapor)
    return rapor


# ---------------- yayın ----------------
def _yaz(yol: Path, metin: str) -> None:
    """Çıktılar Windows'ta üretilse bile LF satır sonuyla yazılır (GitHub'da gereksiz satır farkı oluşmaz)."""
    yol.write_text(metin, encoding="utf-8", newline="\n")


def yayinla(oturum: sessionmaker, cikti_dizini: Path = CIKTI, tam_liste_linki: str = "", ozet_yaz: bool = True) -> dict:
    """`ozet_yaz=False`: ara tarama. "Son özetten beri yeni ilanlar" işareti ilerlemez, yeniler günlük özete kalır."""
    an = datetime.now(TURKIYE_SAATI)
    cikti_dizini.mkdir(parents=True, exist_ok=True)
    with oturum() as o:
        hepsi = [zenginlestir(i) for i in depo.yayinlanacak_ilanlar(o)]
        son = depo.durum_al(o, "son_whatsapp_ozeti")
        yeniler = (
            [zenginlestir(i) for i in depo.yayinlanacak_ilanlar(o, sonra=datetime.fromisoformat(son))] if son else hepsi
        )
        site_ozeti = istatistik_metni(
            an,
            takip_edilen_firma=depo.takip_edilen_firma_sayisi(o),
            taranan_firma=depo.taranan_firma_sayisi(o),
            aktif_ilan=len(depo.aktif_konumlar(o)),
            ogrenci_ilani=len(hepsi),
            konumlar=depo.aktif_konumlar(o),
            firma_adlari=depo.ornek_firma_adlari(o),
            kararlar=depo.ornek_kararlar(o, uygun=True, sinir=6) + depo.ornek_kararlar(o, uygun=False, sinir=10),
        )
    yeniler = [i for i in yeniler if taze_mi(i, an)]

    _yaz(cikti_dizini / "README.md", tablo_metni(hepsi, an))
    _yaz(cikti_dizini / "ilanlar.json", json_metni(hepsi, an))
    _yaz(cikti_dizini / "istatistik.json", site_ozeti)
    metin = ozet_metni(yeniler, an, tam_liste_linki) if ozet_yaz else None
    ozet_yolu = None
    if metin:
        ozet_yolu = cikti_dizini / f"whatsapp_{an:%Y-%m-%d_%H%M}.txt"
        _yaz(ozet_yolu, metin)
        with oturum.begin() as o:
            depo.durum_yaz(o, "son_whatsapp_ozeti", datetime.now(UTC).isoformat())
    kayit.info("Yayın: %d açık ilan, %d yeni ilan → %s", len(hepsi), len(yeniler), cikti_dizini)
    return {
        "acik_ilan": len(hepsi),
        "yeni_ilan": len(yeniler),
        "whatsapp_dosyasi": str(ozet_yolu) if ozet_yolu else None,
    }
