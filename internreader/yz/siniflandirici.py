"""İlan sınıflandırıcı: her ilan için seviye, rol ailesi ve yapay zekâ ağırlığını yapay zekâya sorar.

Maliyet tasarımı:
- Toplu: tek istekte PARTI_BOYU kadar ilan sınıflanır (her ilan için ayrı istek yerine).
- Bir kez: sonuç veritabanında saklanır; aynı ilan bir daha asla sınıflanmaz (bkz. depo.siniflandirilmamislar).
- Ön seçim: yalnızca konumu uygun (Türkiye / genel uzaktan) ilanlar buraya gelir.
"""

import hashlib
import logging
import re
from typing import Literal

from pydantic import BaseModel, Field

from internreader.model import Ilan
from internreader.yz.istemci import CiktiBozuk, ServisHatasi, YzIstemci, YzKullanilamaz

kayit = logging.getLogger(__name__)

PARTI_BOYU = 30


class IlanSinifi(BaseModel):
    no: int = Field(description="İlanın listedeki numarası")
    seviye: Literal["staj", "uzun_donem_staj", "yari_zamanli", "junior", "yeni_mezun", "deneyimli", "belirsiz"]
    rol: Literal["yazilim", "yapay_zeka", "veri", "diger_teknik", "teknik_degil"]
    yapay_zeka: Literal["ozunde", "arti", "yok"] = Field(
        description="Yapay zekâ/LLM/ML bu işin özünde mi, artı mı, yok mu"
    )
    gerekce: str = Field(description="En fazla 12 kelimelik Türkçe gerekçe")


class TopluSiniflandirma(BaseModel):
    sonuclar: list[IlanSinifi]


SISTEM = """İş ilanlarını sınıflandırıyorsun. Her ilan için başlık, firma, kaynak türü, konum ve kısa açıklama verilecek.

seviye:
- staj: intern, internship, stajyer. uzun_donem_staj: uzun dönem / long-term staj.
- yari_zamanli: part-time, yarı zamanlı (öğrenci için). junior: junior, jr, entry level, associate (deneyimsiz).
- yeni_mezun: new grad, yeni mezun, aday mühendis, genç yetenek / trainee programı.
- deneyimli: senior, kıdemli, uzman, lead, staff, principal, müdür, yönetici; unvanda "II"/"III" geçen;
  ya da birkaç yıl deneyim isteyen her ilan.
- "All levels", "tüm seviyeler", "her seviyeden" yazan ilan → junior (yeni başlayanlara da açık).
- belirsiz: seviye çıkarılamıyorsa. Sadece "Mühendis" ya da "Developer" yazan ve deneyim belirtmeyen ilanlar belirsizdir.

rol:
- yazilim: yazılım geliştirme, backend/frontend/full-stack, mobil, oyun programlama, test/QA otomasyon, DevOps/SRE, gömülü yazılım.
- yapay_zeka: makine öğrenmesi, LLM, yapay zekâ mühendisliği, bilgisayarlı görü, NLP.
- veri: veri analisti, veri mühendisi, veri bilimci, BI.
- diger_teknik: elektronik, mekanik, donanım, RF, endüstri, kalite, üretim, sistem mühendisliği (yazılım değil).
- teknik_degil: satış, pazarlama, sosyal medya, İK, finans, satın alma, hukuk, idari, müşteri hizmetleri.

yapay_zeka: ozunde (iş doğrudan AI/ML/LLM), arti (AI araçları/bilgisi tercih sebebi), yok.

Başlıktaki "AI" ya da "Mühendis" kelimesine değil, işin kendisine bak. Her ilan için tam bir sonuç ver; numaraları koru."""


# Seviyeyi ele veren cümleler: "3+ years of experience", "yeni mezun", "öğrenci"... Açıklamaların başı genelde
# şirket tanıtımıdır; yalnızca ilk 400 karakteri göndermek modele karar verecek bilgiyi vermiyordu
# (18.10.2026 çalıştırmasında 104 yazılım ilanı bu yüzden "belirsiz" çıktı).
SEVIYE_IPUCU = re.compile(
    r"(?i)(\d+\s*\+?\s*(years?|yrs?|yıl)|experience|deneyim|tecrübe|senior|junior|intern|stajyer|\bstaj|"
    r"graduat|mezun|student|öğrenci|entry[- ]level|all levels|seviye)"
)
ACIKLAMA_SINIRI = 400


def aciklama_ozeti(aciklama: str, sinir: int = ACIKLAMA_SINIRI) -> str:
    """Açıklamadan seviyeyi ele veren cümleleri seçer; hiç yoksa başını alır. Gönderilen token sayısı aynı kalır."""
    cumleler = [c.strip() for c in re.split(r"(?<=[.!?;•])\s+|\n+", aciklama) if c.strip()]
    secilen = [c[:200] for c in cumleler if SEVIYE_IPUCU.search(c)]
    return (" … ".join(secilen) if secilen else " ".join(cumleler))[:sinir]


def siniflandirma_imzasi(i: Ilan) -> str:
    """Kararı belirleyen şeylerin özeti: firma + başlık + açıklamadaki seviye cümleleri. Aynı ilan farklı adresle
    yeniden yayınlanırsa (Workday'de sık) imza aynı kalır ve eski karar kullanılır; yapay zekâya gidilmez."""
    sade = lambda t: re.sub(r"\s+", " ", t.lower()).strip()  # noqa: E731
    return hashlib.sha1(f"{sade(i.firma)}|{sade(i.baslik)}|{sade(aciklama_ozeti(i.aciklama))}".encode()).hexdigest()


def _satir(no: int, i: Ilan) -> str:
    aciklama = aciklama_ozeti(i.aciklama)
    return (
        f"[{no}] Başlık: {i.baslik} | Firma: {i.firma} | Tür: {i.calisma_tipi or '-'} | "
        f"Konum: {i.konum or '-'} | Açıklama: {aciklama or '-'}"
    )


def _mesaj(parti: list[Ilan]) -> str:
    return "\n".join(_satir(no, i) for no, i in enumerate(parti))


def _eslestir(parti: list[Ilan], sonuc: TopluSiniflandirma) -> dict[str, dict]:
    cikti = {}
    for s in sonuc.sonuclar:
        if 0 <= s.no < len(parti):
            cikti[parti[s.no].kimlik] = s.model_dump(exclude={"no"})
    return cikti


def _parti(yz: YzIstemci, parti: list[Ilan]) -> dict[str, dict]:
    """Tek parti, normal istekle. Cevap sığmadıysa (kesildi) parti ikiye bölünüp yeniden denenir."""
    try:
        sonuc = yz.yapilandirilmis(
            islem="siniflandirma", sistem=SISTEM, mesaj=_mesaj(parti), cikti_turu=TopluSiniflandirma, max_tokens=8_000
        )
    except CiktiBozuk as hata:
        if len(parti) == 1:
            kayit.warning("Sınıflandırılamadı: %s (%s)", parti[0].baslik, hata)
            return {}
        yari = len(parti) // 2
        return _parti(yz, parti[:yari]) | _parti(yz, parti[yari:])
    return _eslestir(parti, sonuc)


def siniflandir(yz: YzIstemci, ilanlar: list[Ilan], is_parcacigi: int = 4) -> dict[str, dict]:
    """ilan kimliği → {seviye, rol, yapay_zeka, gerekce}. Bütçe biterse o ana kadarki sonuçlarla döner.
    Bütün partiler tek seferde gönderilir (toplu modda yarı fiyatına); kesilen parti bölünüp normal yoldan denenir."""
    partiler = [ilanlar[i : i + PARTI_BOYU] for i in range(0, len(ilanlar), PARTI_BOYU)]
    cevaplar = yz.coklu_yapilandirilmis(
        "siniflandirma",
        SISTEM,
        [(str(n), _mesaj(parti)) for n, parti in enumerate(partiler)],
        TopluSiniflandirma,
        max_tokens=8_000,
        is_parcacigi=is_parcacigi,
    )
    sonuclar: dict[str, dict] = {}
    for n, parti in enumerate(partiler):
        cevap = cevaplar.get(str(n))
        if isinstance(cevap, TopluSiniflandirma):
            sonuclar |= _eslestir(parti, cevap)
        elif isinstance(cevap, CiktiBozuk) and len(parti) > 1:
            try:
                sonuclar |= _parti(yz, parti[: len(parti) // 2]) | _parti(yz, parti[len(parti) // 2 :])
            except (YzKullanilamaz, ServisHatasi) as hata:
                kayit.warning("Sınıflandırma (bölünmüş parti) başarısız: %s", hata)
        elif isinstance(cevap, ServisHatasi):
            kayit.warning("Sınıflandırma isteği başarısız: %s", cevap)
    if len(sonuclar) < len(ilanlar):
        kayit.warning(
            "%d ilanın %d tanesi sınıflandırılamadı (bütçe, servis ya da çıktı hatası)",
            len(ilanlar),
            len(ilanlar) - len(sonuclar),
        )
    return sonuclar
