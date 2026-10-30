"""Ayrıntı çıkarıcı: öğrenciye uygun ilanın metninden öğrencinin işine yarayan bilgileri çıkarır.

Yalnızca öğrenciye uygun ilanlar için çalışır (günde birkaç düzine) ve her ilan bir kez işlenir; metin değişmedikçe
tekrar gönderilmez. Uydurmaya karşı kodla denetim (denetle):
- Teknoloji adı ilan metninde geçmiyorsa atılır.
- Son başvuru tarihi geçerli bir tarih değilse ya da makul aralıkta değilse (bir yıldan uzak) atılır. Geçmiş bir son
  başvuru ancak metinde yılıyla açıkça yazıyorsa kalır: ilanın kapandığını gösterir (isleme/guncellik.py).
- İlan tarihi metinde gün, ay ve yılıyla gerçekten geçmiyorsa ya da gelecekteyse atılır (uydurma tarih).
Dönem yılları ("2025 Yaz Stajı") yapay zekâya sorulmaz, metinden kodla bulunur.

Rol ve ilan türü de burada doğrulanır: sınıflandırıcı kariyer sayfası ilanlarında yalnızca başlığı görür, bu adım
metnin tamamını görür. "Hotel WD Staj" başlıktan yazılım gibi durur, görevleri satış ve müşteri kurulumudur.
"""

import hashlib
import logging
from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, Field

from internreader.isleme.guncellik import donem_yillari, metindeki_tarihler
from internreader.isleme.kategori import ilan_turu_bul, savunma_metinde
from internreader.yz.istemci import Sonuc, YzIstemci

kayit = logging.getLogger(__name__)

METIN_SINIRI = 6_000  # ilan metninin modele giden en fazla karakteri (çoğu ilan bunun altında)


class IlanAyrintisi(BaseModel):
    ozet: str = Field(description="İşin ne olduğunu anlatan 1–2 cümlelik sade Türkçe özet, en fazla 240 karakter")
    son_basvuru: str | None = Field(None, description="Metinde açık son başvuru tarihi varsa YYYY-AA-GG, yoksa null")
    ilan_tarihi: str | None = Field(
        None, description="Metinde ilanın yayın/güncelleme tarihi gün, ay ve yılıyla yazıyorsa YYYY-AA-GG, yoksa null"
    )
    hedef: str | None = Field(None, description="Kimler başvurabilir (ör. '3. ve 4. sınıf öğrencileri'); yoksa null")
    calisma_modeli: Literal["ofis", "hibrit", "uzaktan", "belirsiz"]
    ucretli: Literal["evet", "hayir", "belirsiz"]
    teknolojiler: list[str] = Field(description="Metinde adı geçen somut teknoloji/dil/araç, en fazla 6")
    ilan_turu: Literal["is", "egitim", "yarisma", "genel_basvuru"] = Field(
        "is", description="Belirli bir iş/staj mı, eğitim programı mı, yarışma mı, genel CV toplama sayfası mı"
    )
    rol: Literal["yazilim", "yapay_zeka", "veri", "diger_teknik", "teknik_degil"] | None = Field(
        None, description="Görevlerin ağırlığına göre işin rolü; metin görevleri anlatmıyorsa null"
    )


SISTEM = """Bir staj ya da giriş seviyesi iş ilanının metnini alacaksın. Öğrencinin işine yarayan bilgileri çıkar.
Yalnızca metinde yazanı kullan; tahmin etme, genel bilgi ekleme.

- ozet: İşin kendisini anlatan 1–2 cümlelik sade Türkçe özet (en fazla 240 karakter). Şirket tanıtımı yazma.
  Metinde işin ne olduğu anlatılmıyorsa boş bırak (""); "metinde bilgi yok" gibi cümle yazma.
- son_basvuru: Metinde açık bir son başvuru tarihi varsa YYYY-AA-GG biçiminde (yıl yazmıyorsa bugünün tarihine
  göre en yakın gelecek tarih). Tarih geçmişte kalmışsa da olduğu gibi yaz. Yoksa null.
- ilan_tarihi: Metinde ilanın yayınlandığı ya da güncellendiği tarih gün, ay ve yılıyla açıkça yazıyorsa
  (ör. "08 Mayıs 2023", "Yayın tarihi: 12.09.2026") YYYY-AA-GG. Yazmıyorsa null; tahmin etme, bugünün tarihini yazma.
- hedef: Kimlerin başvurabileceği metinde yazıyorsa kısa ifade (ör. "3. ve 4. sınıf öğrencileri", "2026 mezunları",
  "haftada en az 3 gün çalışabilecek öğrenciler"). Yazmıyorsa null.
- calisma_modeli: ofis, hibrit ya da uzaktan; metinde yazmıyorsa belirsiz.
- ucretli: Ücretli olduğu açıkça yazıyorsa evet; ücretsiz/gönüllü olduğu yazıyorsa hayir; yazmıyorsa belirsiz.
- teknolojiler: Metinde adı geçen somut teknoloji, programlama dili ya da araç (ör. Python, React, SQL, Docker,
  PyTorch). En fazla 6. "Yazılım", "yapay zekâ" gibi genel kavramlar değil.
- ilan_turu: is: belirli bir staj ya da iş pozisyonu. egitim: eğitim programı, kamp, bootcamp (sonunda işe alım
  olsa da önce eğitim veriliyorsa). yarisma: yarışma, hackathon, etkinlik. genel_basvuru: belirli bir pozisyon
  olmayan, genel CV toplayan sayfa ("uygun ilan bulamadınız mı? CV'nizi gönderin").
- rol: Görevlerin AĞIRLIĞINA bak; şirketin yazılım firması olması ya da metinde teknoloji adı geçmesi yetmez.
  yazilim: aday ağırlıklı olarak kod yazıyor, test otomasyonu, DevOps, gömülü yazılım yapıyor.
  yapay_zeka: makine öğrenmesi, LLM, bilgisayarlı görü, NLP geliştiriyor. veri: veri analizi, veri mühendisliği, BI.
  diger_teknik: ERP danışmanlığı/uyarlama, raporlama, Excel-Office işleri, BT destek, donanım, elektronik.
  teknik_degil: satış, pazarlama, müşteri kurulumu ve eğitimi, müşteri ilişkileri, danışmanlık, İK, finans.
  Metin görevleri anlatmıyorsa null."""


def kisalt(metin: str, sinir: int) -> str:
    """Kelime ortasından kesmeden kısaltır."""
    metin = " ".join(metin.split())
    if len(metin) <= sinir:
        return metin
    return metin[: sinir - 1].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def metin_ozeti(metin: str) -> str:
    return hashlib.sha256(metin.encode()).hexdigest()


def _mesaj(baslik: str, firma: str, metin: str, bugun: date) -> str:
    return f"Bugünün tarihi: {bugun.isoformat()}\nŞirket: {firma}\nİlan başlığı: {baslik}\n\nİLAN METNİ:\n{metin[:METIN_SINIRI]}"


def _tarih(metin: str | None) -> date | None:
    try:
        return date.fromisoformat(metin) if metin else None
    except ValueError:
        return None


def denetle(ayrinti: IlanAyrintisi, metin: str, bugun: date, baslik: str = "") -> dict:
    """Modelin çıkardığını metne karşı denetler; tutarsız alanları atar."""
    kucuk = metin.lower()
    teknolojiler = [t.strip() for t in ayrinti.teknolojiler if t.strip() and t.strip().lower() in kucuk][:6]
    yazan_tarihler = metindeki_tarihler(metin)
    son = _tarih(ayrinti.son_basvuru)
    if son and not (bugun - timedelta(days=3) <= son <= bugun + timedelta(days=400)):
        # geçmiş son başvuru yalnızca metinde yılıyla yazıyorsa kalır (yıl yazmayanı model gelecek yıla taşır)
        son = son if son < bugun and son.year >= bugun.year - 5 and son in yazan_tarihler else None
    ilan_tarihi = _tarih(ayrinti.ilan_tarihi)
    if ilan_tarihi and (ilan_tarihi > bugun or ilan_tarihi not in yazan_tarihler):
        ilan_tarihi = None
    yillar = donem_yillari(metin)
    return {
        "ozet": kisalt(ayrinti.ozet, 320),
        "son_basvuru": son.isoformat() if son else None,
        "ilan_tarihi": ilan_tarihi.isoformat() if ilan_tarihi else None,
        "donem_yili": max(yillar) if yillar else None,
        "hedef": kisalt(ayrinti.hedef or "", 120) or None,
        "calisma_modeli": ayrinti.calisma_modeli,
        "ucretli": ayrinti.ucretli,
        "teknolojiler": teknolojiler,
        "ilan_turu": ilan_turu_bul(baslik, metin, ayrinti.ilan_turu),
        "rol": ayrinti.rol,
        "savunma_kaniti": savunma_metinde(metin),
    }


def ayrintilari_cikar(
    yz: YzIstemci, isler: list[tuple[str, str, str, str]], bugun: date, is_parcacigi: int = 4
) -> dict[str, dict | Exception]:
    """isler: (kimlik, başlık, firma, metin) → {kimlik: denetlenmiş ayrıntı sözlüğü ya da hata}."""
    cevaplar: dict[str, Sonuc] = yz.coklu_yapilandirilmis(
        "ayrinti",
        SISTEM,
        [(kimlik, _mesaj(baslik, firma, metin, bugun)) for kimlik, baslik, firma, metin in isler],
        IlanAyrintisi,
        max_tokens=1_200,
        is_parcacigi=is_parcacigi,
    )
    girdiler = {kimlik: (baslik, metin) for kimlik, baslik, _, metin in isler}
    sonuc: dict[str, dict | Exception] = {}
    for kimlik, cevap in cevaplar.items():
        baslik, metin = girdiler[kimlik]
        sonuc[kimlik] = denetle(cevap, metin, bugun, baslik) if isinstance(cevap, IlanAyrintisi) else cevap
    return sonuc
