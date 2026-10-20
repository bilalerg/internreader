"""Alan (domain) modelleri: projenin "dili".

Her kaynak (Lever, Greenhouse, kariyer sayfası...) ilanı `Ilan` kalıbına çevirir; sonraki adımlar
(filtre, sınıflandırma, yayın) ilanın nereden geldiğini bilmek zorunda kalmaz.
Bu sınıflar veritabanından bağımsızdır; veritabanı tabloları `db.py`'de ayrıca tanımlıdır.
"""

import hashlib
from dataclasses import asdict, dataclass, field


@dataclass
class FirmaBilgisi:
    id: int
    ad: str
    web: str = ""
    ats: str = ""  # hazır ilan sistemi: "lever", "greenhouse", "workday"...
    slug: str = ""  # firmanın o sistemdeki kısa adı
    kariyer: str = ""  # kendi kariyer sayfası
    etiket: list[str] = field(default_factory=list)


@dataclass
class Ilan:
    firma: str
    baslik: str
    url: str
    kaynak: str  # "lever", "greenhouse", "kariyer_sayfasi", ...
    konum: str = ""
    calisma_tipi: str = ""  # kaynağın verdiği tür: "Internship", "Full-time" ya da okuyucunun seviyesi
    tarih: str = ""  # kaynağın verdiği yayın tarihi (YYYY-AA-GG), yoksa boş
    aciklama: str = ""  # düz metin; bazı kaynaklar listede vermez
    etiket: list[str] = field(default_factory=list)

    @property
    def kimlik(self) -> str:
        """Aynı ilanı her çalıştırmada tanımak için URL'den türetilen kalıcı kimlik."""
        return hashlib.sha1(self.url.encode()).hexdigest()[:16]

    def sozluk(self) -> dict:
        return {"kimlik": self.kimlik, **asdict(self)}


# Öğrencilerin başvurabileceği seviyeler ve hedef rol aileleri (yayına girecek ilanlar)
OGRENCI_SEVIYELERI = frozenset({"staj", "uzun_donem_staj", "yari_zamanli", "junior", "yeni_mezun"})
HEDEF_ROLLER = frozenset({"yazilim", "yapay_zeka", "veri"})
