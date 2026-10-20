"""Kariyer sayfası okuyucu: sayfa metninden açık pozisyonları yapay zekâyla çıkarır ve kodla doğrular.

Uydurmaya karşı iki kural (dogrula):
  1. Pozisyon başlığı sayfa metninde birebir geçmeli.
  2. Bağlantı, sayfadaki bağlantı listesinden seçilmiş olmalı (model adres uyduramaz, sadece numara seçer).
Uzun sayfalar parçalara bölünür; cevap yarıda kesilirse parça ikiye bölünüp tekrar denenir.
"""

import hashlib
import logging
import re
import urllib.parse
from typing import Literal

from pydantic import BaseModel, Field

from internreader.kaynaklar.kariyer_sayfasi import SayfaIcerigi
from internreader.model import FirmaBilgisi, Ilan
from internreader.yz.istemci import CiktiBozuk, YzIstemci

kayit = logging.getLogger(__name__)

PARCA_BOYU = 12_000  # bir istekte gönderilecek en fazla metin (karakter); ~3–4 bin token
AZAMI_PARCA = 3  # çok uzun sayfalarda en fazla bu kadar parça okunur (maliyet tavanı)
EN_KISA_PARCA = 1_500  # yarıda kesilme durumunda bundan küçük parçaya bölünmez

Seviye = Literal["staj", "uzun_donem_staj", "yari_zamanli", "junior", "yeni_mezun", "deneyimli", "belirsiz"]


class Pozisyon(BaseModel):
    baslik: str = Field(description="Pozisyonun sayfada yazdığı haliyle başlığı; çevirme, düzeltme")
    link_no: int | None = Field(None, description="Bu pozisyona ait bağlantının listedeki numarası; yoksa null")
    konum: str | None = Field(None, description="Sayfada yazıyorsa şehir/ilçe/uzaktan bilgisi")
    seviye: Seviye = Field(description="Sayfadaki ifadeye göre seviye; emin değilsen 'belirsiz'")


class SayfaSonucu(BaseModel):
    kariyer_sayfasi_mi: bool = Field(description="Bu sayfa gerçekten bir kariyer/iş ilanı sayfası mı?")
    pozisyonlar: list[Pozisyon] = Field(description="Sayfada AÇIKÇA listelenen açık pozisyonlar; yoksa boş liste")
    genel_basvuru_var_mi: bool = Field(description="Belirli bir pozisyon olmadan genel CV/başvuru kabul ediliyor mu?")


SISTEM = """Bir şirketin kariyer sayfasının metnini (ya da metnin bir parçasını) ve sayfadaki bağlantıların numaralı \
listesini alacaksın. Görevin: metinde AÇIKÇA listelenen açık pozisyonları çıkarmak.

Kurallar:
- Yalnızca metinde gerçekten yazan pozisyonları al. Tahmin etme, uydurma.
- Başlığı metinde yazdığı gibi aynen yaz; çevirme, kısaltma, düzeltme yapma.
- "Kariyer fırsatları", "Bize katılın", "Genel başvuru" gibi ifadeler pozisyon değildir.
- Departman ya da ekip adları (ör. "Yazılım Ekibi") tek başına pozisyon değildir.
- Bir pozisyonun bağlantısı listede varsa numarasını ver; yoksa null bırak.
- Seviye: stajyer/intern → staj; uzun dönem staj → uzun_donem_staj; part-time/yarı zamanlı → yari_zamanli;
  junior/jr → junior; yeni mezun/new grad/aday mühendis/genç yetenek/trainee programı → yeni_mezun;
  senior/kıdemli/uzman/lead/müdür/yönetici ya da yıl cinsinden deneyim isteyen → deneyimli; emin değilsen belirsiz.
- Metinde açık pozisyon yoksa ya da "şu an açık pozisyon bulunmamaktadır" yazıyorsa pozisyon listesi boş olsun."""


def _normal(metin: str) -> str:
    return re.sub(r"\s+", " ", metin.lower()).strip()


def parcala(metin: str, boy: int = PARCA_BOYU, azami: int = AZAMI_PARCA) -> list[str]:
    """Metni, sınırlarda başlık kesilmesin diye 300 karakter örtüşmeyle parçalara böler."""
    if len(metin) <= boy:
        return [metin]
    return [metin[i : i + boy] for i in range(0, len(metin), boy - 300)][:azami]


def dogrula(
    pozisyonlar: list[Pozisyon], metin: str, baglantilar: list[tuple[str, str]]
) -> tuple[list[dict], list[str]]:
    """Uydurma korumasi. (geçen pozisyonlar, atılan başlıklar) döndürür."""
    metin_n = _normal(metin)
    gecen, atilan, gorulen = [], [], set()
    for p in pozisyonlar:
        baslik = p.baslik.strip()
        if len(baslik) < 3 or _normal(baslik) not in metin_n:
            atilan.append(baslik)
            continue
        link = baglantilar[p.link_no][1] if p.link_no is not None and 0 <= p.link_no < len(baglantilar) else None
        anahtar = (_normal(baslik), link)
        if anahtar in gorulen:  # aynı pozisyon birden fazla parçada geçtiyse bir kez say
            continue
        gorulen.add(anahtar)
        gecen.append({"baslik": baslik, "link": link, "konum": p.konum, "seviye": p.seviye})
    return gecen, atilan


def _mesaj(firma: str, parca: str, liste: str) -> str:
    return f"Şirket: {firma}\n\nSAYFA METNİ:\n{parca}\n\nBAĞLANTILAR:\n{liste}"


def _parcayi_oku(yz: YzIstemci, firma: str, parca: str, liste: str) -> list[Pozisyon]:
    """Tek parça, normal istekle. Cevap kesilirse parça ikiye bölünüp yeniden denenir."""
    try:
        return yz.yapilandirilmis(
            islem="sayfa_okuma", sistem=SISTEM, cikti_turu=SayfaSonucu, mesaj=_mesaj(firma, parca, liste)
        ).pozisyonlar
    except CiktiBozuk:
        if len(parca) < EN_KISA_PARCA:
            raise
        return _bolerek_oku(yz, firma, parca, liste)


def _bolerek_oku(yz: YzIstemci, firma: str, parca: str, liste: str) -> list[Pozisyon]:
    yari = len(parca) // 2
    kayit.info("%s: cevap kesildi, parça ikiye bölünüyor (%d karakter)", firma, len(parca))
    return _parcayi_oku(yz, firma, parca[: yari + 150], liste) + _parcayi_oku(yz, firma, parca[yari - 150 :], liste)


def kisa_adres(url: str, sayfa_url: str) -> str:
    """Modele gösterilecek kısa adres: aynı sitedeyse yalnızca yol. Model bağlantıyı numarayla seçer; tam adres kodda
    saklıdır (dogrula numaradan geri bulur). Uzun adresler token harcıyordu."""
    p, s = urllib.parse.urlsplit(url), urllib.parse.urlsplit(sayfa_url)
    adres = p.path + (f"?{p.query}" if p.query else "")
    return ((p.netloc if p.netloc != s.netloc else "") + adres)[:80]


def baglanti_listesi(parca: str, baglantilar: list[tuple[str, str]], sayfa_url: str) -> str:
    """Yalnızca bu parçanın metninde yazısı geçen bağlantılar (numaralar sayfa genelindeki sırayı korur).
    18.10 ölçümü: sayfa başına ortalama 6.500 girdi token'ının büyük kısmı 150 bağlantının tam adresiydi ve
    çok parçalı sayfalarda bütün liste her parçada yeniden gönderiliyordu."""
    return "\n".join(
        f"[{i}] {yazi} -> {kisa_adres(url, sayfa_url)}" for i, (yazi, url) in enumerate(baglantilar) if yazi in parca
    )


def sayfalari_oku(
    yz: YzIstemci, isler: list[tuple[str, str, SayfaIcerigi]], is_parcacigi: int = 4
) -> dict[str, dict | Exception]:
    """Birden çok sayfayı okur: (anahtar, firma, içerik) → {anahtar: sonuç sözlüğü ya da hata}.
    Bütün sayfaların bütün parçaları tek seferde gönderilir (toplu modda yarı fiyatına). Kesilen parça ikiye
    bölünüp normal yoldan denenir; bir parçası okunamayan sayfa hata sayılır (önbelleğe yazılmaz, yarın tekrar)."""
    istekler: list[tuple[str, str]] = []
    parcalar: dict[str, tuple[str, str, str, str]] = {}
    for anahtar, firma, icerik in isler:
        for no, parca in enumerate(parcala(icerik.metin)):
            liste = baglanti_listesi(parca, icerik.baglantilar, icerik.url)
            istek = f"{anahtar}|{no}"
            istekler.append((istek, _mesaj(firma, parca, liste)))
            parcalar[istek] = (anahtar, firma, parca, liste)

    cevaplar = yz.coklu_yapilandirilmis("sayfa_okuma", SISTEM, istekler, SayfaSonucu, is_parcacigi=is_parcacigi)
    bulunan: dict[str, list[Pozisyon]] = {anahtar: [] for anahtar, _, _ in isler}
    hatalar: dict[str, Exception] = {}
    for istek, (anahtar, firma, parca, liste) in parcalar.items():
        cevap = cevaplar.get(istek)
        if isinstance(cevap, SayfaSonucu):
            bulunan[anahtar] += cevap.pozisyonlar
            continue
        if isinstance(cevap, CiktiBozuk) and len(parca) >= EN_KISA_PARCA:
            try:
                bulunan[anahtar] += _bolerek_oku(yz, firma, parca, liste)
                continue
            except Exception as hata:  # bölünmüş parça da okunamadı
                cevap = hata
        hatalar[anahtar] = cevap if isinstance(cevap, Exception) else CiktiBozuk("cevap yok")

    sonuc: dict[str, dict | Exception] = {}
    for anahtar, firma, icerik in isler:
        if anahtar in hatalar:
            sonuc[anahtar] = hatalar[anahtar]
            continue
        pozisyonlar, atilan = dogrula(bulunan[anahtar], icerik.metin, icerik.baglantilar)
        if atilan:
            kayit.info("%s: %d başlık sayfada bulunamadığı için atıldı (olası uydurma)", firma, len(atilan))
        sonuc[anahtar] = {"pozisyonlar": pozisyonlar, "atilan": atilan}
    return sonuc


def sayfayi_oku(yz: YzIstemci, firma: str, icerik: SayfaIcerigi) -> dict:
    """Tek sayfa (testler ve elle deneme için). Hata olursa fırlatır."""
    sonuc = sayfalari_oku(yz, [("tek", firma, icerik)])["tek"]
    if isinstance(sonuc, Exception):
        raise sonuc
    return sonuc


def ilanlara_cevir(firma: FirmaBilgisi, kariyer_url: str, sonuc: dict) -> list[Ilan]:
    ilanlar = []
    for p in sonuc.get("pozisyonlar", []):
        # Bağlantısı olmayan pozisyona kariyer sayfası + başlık özetinden kalıcı bir adres verilir
        url = p["link"] or f"{kariyer_url}#{hashlib.sha1(p['baslik'].encode()).hexdigest()[:8]}"
        ilanlar.append(
            Ilan(
                firma=firma.ad,
                baslik=p["baslik"],
                url=url,
                kaynak="kariyer_sayfasi",
                konum=p.get("konum") or "",
                calisma_tipi=p.get("seviye") or p.get("tur") or "",
                etiket=firma.etiket,
            )
        )
    return ilanlar
