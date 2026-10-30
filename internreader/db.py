"""Veritabanı tabloları ve bağlantı.

Aynı tanımlar hem SQLite'ta (yerel) hem Postgres'te (sunucu) çalışır; uzun alanlar Text, anahtarlar kısa String.
Şema değişikliği: modeli değiştir → python -m internreader goc-uret "açıklama" → göç dosyasını gözden geçir.
Tablolar:
  firmalar          takip edilen şirketler
  ilanlar           görülen her ilan; ilk/son görülme tarihiyle (yeni ve kapanan ilanları buradan anlarız), elle gizleme
  siniflandirmalar  yapay zekânın ilan başına kararı (seviye, rol, yapay zekâ ağırlığı) — her ilan bir kez sınıflanır
  sayfa_onbellek    kariyer sayfası özeti + okuyucu sonucu — sayfa değişmediyse yapay zekâya tekrar gidilmez
  yz_kullanim       her yapay zekâ çağrısının token ve maliyet kaydı
  ilan_ayrintilari  öğrenci ilanlarından yapay zekânın çıkardığı özet, son başvuru, hedef sınıf, teknolojiler
  aboneler          bülten aboneleri (e-posta + tercihler; çift onaylı kayıt)
  gonderimler       hangi aboneye hangi ilan gönderildi (aynı ilan iki kez gitmez)
  bultenler         gönderilen bültenler (aktif kullanıcı ölçümü)
  tiklamalar        e-postadaki ilan bağlantısına tıklamalar (aboneyle bağı yok)
  eposta_sayaci     Türkiye günü başına gönderilen e-posta (Brevo kotası tek yerden sayılır)
  durum             küçük anahtar-değer kayıtları (ör. son yayın zamanı)
"""

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
    false,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def simdi() -> datetime:
    return datetime.now(UTC)


class Taban(DeclarativeBase):
    pass


class Firma(Taban):
    __tablename__ = "firmalar"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    anahtar: Mapped[str] = mapped_column(String(200), unique=True, index=True)  # alan adı ya da sade ad
    ad: Mapped[str] = mapped_column(String(300))
    web: Mapped[str | None] = mapped_column(Text)
    ats: Mapped[str | None] = mapped_column(String(40))
    slug: Mapped[str | None] = mapped_column(String(200))
    kariyer: Mapped[str | None] = mapped_column(Text)
    etiket: Mapped[list] = mapped_column(JSON, default=list)
    kaynak: Mapped[str | None] = mapped_column(Text)  # virgülle birleşen liste adları; uzayabilir
    aktif: Mapped[bool] = mapped_column(Boolean, default=True)
    kesif_tarihi: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    eklenme: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=simdi)


class IlanKaydi(Taban):
    __tablename__ = "ilanlar"
    kimlik: Mapped[str] = mapped_column(String(16), primary_key=True)
    firma: Mapped[str] = mapped_column(String(300), index=True)
    baslik: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    kaynak: Mapped[str] = mapped_column(String(40))
    konum: Mapped[str] = mapped_column(Text, default="")
    calisma_tipi: Mapped[str] = mapped_column(String(80), default="")
    yayin_tarihi: Mapped[str] = mapped_column(String(10), default="")
    aciklama: Mapped[str] = mapped_column(Text, default="")
    etiket: Mapped[list] = mapped_column(JSON, default=list)
    ilk_gorulme: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=simdi, index=True)
    son_gorulme: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=simdi)
    aktif: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    # Elle gizlenen ilan (ilan-gizle): sitede ve e-postada görünmez. Tarama bu alana dokunmaz, ilan yeniden açılmaz.
    gizli: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())

    __table_args__ = (Index("ix_ilanlar_aktif_ilk_gorulme", "aktif", "ilk_gorulme"),)


class Siniflandirma(Taban):
    __tablename__ = "siniflandirmalar"
    kimlik: Mapped[str] = mapped_column(String(16), ForeignKey("ilanlar.kimlik", ondelete="CASCADE"), primary_key=True)
    seviye: Mapped[str] = mapped_column(String(30))
    rol: Mapped[str] = mapped_column(String(30))
    yapay_zeka: Mapped[str] = mapped_column(String(10))
    ogrenciye_uygun: Mapped[bool] = mapped_column(Boolean, index=True)
    gerekce: Mapped[str] = mapped_column(Text, default="")
    model: Mapped[str] = mapped_column(String(60))
    tarih: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=simdi)
    # Aynı ilan farklı adresle yeniden yayınlanırsa (Workday'de sık) karar buradan bulunur; yapay zekâya gidilmez
    imza: Mapped[str | None] = mapped_column(String(40), index=True)


class IlanAyrinti(Taban):
    """Öğrenciye uygun ilanlardan yapay zekânın çıkardığı ayrıntılar (bültende ve sitede gösterilir)."""

    __tablename__ = "ilan_ayrintilari"
    kimlik: Mapped[str] = mapped_column(String(16), ForeignKey("ilanlar.kimlik", ondelete="CASCADE"), primary_key=True)
    ozet: Mapped[str] = mapped_column(Text, default="")  # 1–2 cümle Türkçe
    son_basvuru: Mapped[str | None] = mapped_column(String(10))  # YYYY-AA-GG
    hedef: Mapped[str | None] = mapped_column(String(120))  # "3. ve 4. sınıf", "yeni mezun"...
    calisma_modeli: Mapped[str] = mapped_column(String(12), default="belirsiz")  # ofis | hibrit | uzaktan | belirsiz
    ucretli: Mapped[str] = mapped_column(String(10), default="belirsiz")  # evet | hayir | belirsiz
    teknolojiler: Mapped[list] = mapped_column(JSON, default=list)
    ilan_tarihi: Mapped[str | None] = mapped_column(String(10))  # metinde yazan yayın tarihi (YYYY-AA-GG), doğrulanmış
    donem_yili: Mapped[int | None] = mapped_column(Integer)  # metindeki en büyük dönem yılı ("2025 Yaz Stajı" → 2025)
    ilan_turu: Mapped[str] = mapped_column(String(14), default="is", server_default="is")
    # is | egitim | yarisma | genel_basvuru (genel CV sayfası yayınlanmaz)
    savunma_kaniti: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # Çıkarıcı sürümü: istem ya da metin kaynağı değişince artar; aktif ilanlar bir kez yeniden çıkarılır
    surum: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    metin_ozeti: Mapped[str] = mapped_column(
        String(64)
    )  # kullanılan metnin özeti: metin değişmedikçe yeniden çıkarılmaz
    model: Mapped[str] = mapped_column(String(60))
    tarih: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=simdi)


class SayfaOnbellek(Taban):
    __tablename__ = "sayfa_onbellek"
    url_ozeti: Mapped[str] = mapped_column(String(64), primary_key=True)
    url: Mapped[str] = mapped_column(Text)
    icerik_ozeti: Mapped[str] = mapped_column(String(64))
    sonuc: Mapped[dict] = mapped_column(JSON)
    tarih: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=simdi)


class YzKullanim(Taban):
    __tablename__ = "yz_kullanim"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tarih: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=simdi, index=True)
    islem: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(60))
    girdi_token: Mapped[int] = mapped_column(Integer)
    cikti_token: Mapped[int] = mapped_column(Integer)
    maliyet_usd: Mapped[float] = mapped_column(Float)
    sure_ms: Mapped[int | None] = mapped_column(Integer)
    durum: Mapped[str] = mapped_column(
        String(16), default="tamam", server_default="tamam"
    )  # tamam|kesildi|bozuk|reddedildi
    toplu: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())  # Batches API (yarı fiyat)


class Abone(Taban):
    """Bülten aboneleri. Kişisel veri en az tutulur: yalnızca e-posta ve tercihler (IP, ad vb. tutulmaz).
    Onay jetonunun kendisi değil özeti saklanır: veritabanı sızsa bile bağlantılar kullanılamaz."""

    __tablename__ = "aboneler"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    eposta: Mapped[str] = mapped_column(String(254), unique=True, index=True)  # küçük harfe çevrilmiş
    # {"sehirler", "alanlar", "seviyeler", "calisma_modelleri": [], "sadece_girisim": bool}; olmayan anahtar = hepsi
    tercihler: Mapped[dict] = mapped_column(JSON, default=dict)
    siklik: Mapped[str] = mapped_column(String(10), default="gunluk")  # gunluk | haftalik
    durum: Mapped[str] = mapped_column(String(10), default="bekliyor", index=True)  # bekliyor | onayli | iptal
    onay_jetonu_ozeti: Mapped[str | None] = mapped_column(String(64), index=True)
    onay_jetonu_tarihi: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    kvkk_surumu: Mapped[str] = mapped_column(String(20))  # onay verilen aydınlatma metninin sürümü
    kvkk_onay_tarihi: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=simdi)
    kaynak: Mapped[str] = mapped_column(String(40), default="site")  # site | whatsapp | ...
    olusturma: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=simdi)
    onay_tarihi: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    iptal_tarihi: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    son_bulten: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Gonderim(Taban):
    """Hangi aboneye hangi ilan gönderildi: aynı ilan bir aboneye iki kez gitmez."""

    __tablename__ = "gonderimler"
    abone_id: Mapped[int] = mapped_column(Integer, ForeignKey("aboneler.id", ondelete="CASCADE"), primary_key=True)
    ilan_kimlik: Mapped[str] = mapped_column(
        String(16), ForeignKey("ilanlar.kimlik", ondelete="CASCADE"), primary_key=True
    )
    tarih: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=simdi, index=True)


class Bulten(Taban):
    """Gönderilen her bülten (aktif kullanıcı ölçümü). Abone çıkınca kayıt kalır ama aboneyle bağı kopar."""

    __tablename__ = "bultenler"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    abone_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("aboneler.id", ondelete="SET NULL"), index=True)
    tarih: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=simdi, index=True)
    ilan_sayisi: Mapped[int] = mapped_column(Integer)
    durum: Mapped[str] = mapped_column(String(12))  # gonderildi | hos_geldin | sessizlik | hata


class Tiklama(Taban):
    """E-postadaki "Başvur" bağlantısına tıklama. Aboneyle bağ kurulmaz: e-posta adresi, abone no, IP ve tarayıcı bilgisi
    tutulmaz; `kisi` her hafta değişen imzalı bir koddur (bkz. bulten/tiklama.py). İlan silinse de kayıt kalır."""

    __tablename__ = "tiklamalar"
    __table_args__ = (UniqueConstraint("eposta_no", "ilan_kimlik", "supheli", name="uq_tiklama_eposta_ilan"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tarih: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=simdi, index=True)
    ilan_kimlik: Mapped[str] = mapped_column(String(16))
    eposta_no: Mapped[str] = mapped_column(String(16))  # e-posta başına rastgele; aboneye geri götürmez
    kisi: Mapped[str] = mapped_column(String(16))
    hafta: Mapped[str] = mapped_column(String(8))  # e-postanın gittiği hafta ("2026-W44"); kisi kodu bu haftaya aittir
    tur: Mapped[str] = mapped_column(String(12))  # bulten | hos_geldin | sessizlik | deneme
    supheli: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false()
    )  # güvenlik tarayıcısı olabilir


class EpostaSayaci(Taban):
    """Türkiye günü başına e-posta sayısı. API ve sabah işi aynı anda yazabilir: artırma atomiktir (depo/bulten.py)."""

    __tablename__ = "eposta_sayaci"
    gun: Mapped[str] = mapped_column(String(10), primary_key=True)  # "2026-10-30"
    adet: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class Durum(Taban):
    __tablename__ = "durum"
    anahtar: Mapped[str] = mapped_column(String(80), primary_key=True)
    deger: Mapped[str] = mapped_column(Text)


def surucu_ekle(url: str) -> str:
    """Neon/Render gibi sağlayıcılar adresi "postgresql://" ya da "postgres://" diye verir; SQLAlchemy bu durumda
    kurulu olmayan psycopg2'yi arar. Kullandığımız sürücü psycopg (3) olduğu için adres ona çevrilir."""
    for onek in ("postgres://", "postgresql://"):
        if url.startswith(onek):
            return "postgresql+psycopg://" + url.removeprefix(onek)
    return url


def motor_olustur(url: str) -> Engine:
    url = surucu_ekle(url)
    if url.startswith("sqlite"):
        motor = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(motor, "connect")
        def _sqlite_ayarla(baglanti, _):
            imlec = baglanti.cursor()
            imlec.execute("PRAGMA journal_mode=WAL")  # okuma ve yazma birbirini kilitlemesin
            imlec.execute("PRAGMA foreign_keys=ON")
            imlec.close()

        return motor
    # Kopan bağlantıyı kullanmadan önce yokla; uzun süre boşta kalan bağlantıyı yenile (sunucu tarafı zaman aşımı)
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5, pool_recycle=1800)


def oturum_fabrikasi(url: str, semayi_kur: bool = True) -> sessionmaker:
    """Bağlantı ve oturum fabrikası. Bekleyen veritabanı göçleri burada uygulanır (bkz. internreader/sema.py)."""
    motor = motor_olustur(url)
    if semayi_kur:
        from internreader.sema import semayi_hazirla  # döngüsel içe aktarmayı önlemek için burada

        semayi_hazirla(motor)
    return sessionmaker(bind=motor, expire_on_commit=False)
