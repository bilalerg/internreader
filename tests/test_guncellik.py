"""İlan güncelliği: tarih bulma, uydurma tarih denetimi, bayat ilan kuralları, kartta tarih satırı ve boru hattı
(tek sayfada listelenen ilanın bölümü, tarihsiz eski ayrıntıların bir kez yeniden çıkarılması)."""

from datetime import UTC, date, datetime

from internreader import boru, depo
from internreader.ayar import ayarlari_oku
from internreader.bulten.sablon import bulten_epostasi
from internreader.db import IlanAyrinti
from internreader.isleme.guncellik import donem_yillari, guncellik, metindeki_tarihler
from internreader.kaynaklar.kariyer_sayfasi import ilan_bolumu
from internreader.model import Ilan
from internreader.yayin import tarih_bilgisi, zenginlestir
from internreader.yz.ayrinti_cikarici import IlanAyrintisi, denetle
from tests.conftest import SahteHttp, SahteYz

BUGUN = date(2026, 10, 29)
AN = datetime(2026, 10, 29, 4, 0, tzinfo=UTC)
YEDITEK = "Proje Stajyeri (Görüntü İşleme). 08 Mayıs 2023. OpenCV ve Python bilen öğrenciler aranıyor."


def ayrinti(**alanlar) -> IlanAyrintisi:
    temel = {"ozet": "Staj.", "calisma_modeli": "belirsiz", "ucretli": "belirsiz", "teknolojiler": []}
    return IlanAyrintisi(**(temel | alanlar))


# ---------------- tarih bulma ve uydurma denetimi ----------------
def test_metindeki_tarihler_turkce_ingilizce_sayisal():
    beklenen = {date(2023, 5, 8)}
    for metin in ["08 Mayıs 2023", "8 MAYIS 2023", "Yayın: 08.05.2023", "2023-05-08", "May 8, 2023", "8 May 2023"]:
        assert beklenen <= metindeki_tarihler(metin), metin
    assert metindeki_tarihler("Son başvuru 15 Kasım") == set()  # yılsız tarih: yayın tarihi sayılmaz
    assert metindeki_tarihler("31.02.2025") == set()  # geçersiz tarih


def test_donem_yillari_yalnizca_donem_bildiren_yillar():
    assert donem_yillari("2025 Yaz Stajı başvuruları") == {2025}
    assert donem_yillari("2024-2025 dönemi için") == {2024, 2025}
    assert donem_yillari("Summer Internship 2024") == {2024}
    assert donem_yillari("2015 yılında kurulan şirketimiz 2026 mezunlarını arıyor") == set()


def test_uydurma_ilan_tarihi_reddedilir():
    tarihsiz = "Python bilen öğrenciler arıyoruz. Hibrit çalışma."
    assert denetle(ayrinti(ilan_tarihi="2026-10-01"), tarihsiz, BUGUN)["ilan_tarihi"] is None
    assert denetle(ayrinti(ilan_tarihi="2023-05-08"), YEDITEK, BUGUN)["ilan_tarihi"] == "2023-05-08"
    assert denetle(ayrinti(ilan_tarihi="2023-05-09"), YEDITEK, BUGUN)["ilan_tarihi"] is None  # metindeki değil
    ileri = "Yayın tarihi: 05.11.2026"
    assert denetle(ayrinti(ilan_tarihi="2026-11-05"), ileri, BUGUN)["ilan_tarihi"] is None  # gelecekte yayın olmaz


def test_gecmis_son_basvuru_yalnizca_metinde_yaziyorsa_kalir():
    metin = "Son başvuru: 15 Haziran 2025. 2025 Yaz Stajı."
    sonuc = denetle(ayrinti(son_basvuru="2025-06-15"), metin, BUGUN)
    assert sonuc["son_basvuru"] == "2025-06-15" and sonuc["donem_yili"] == 2025  # ilan kapanmış: sinyal kalır
    assert denetle(ayrinti(son_basvuru="2025-06-15"), "Python stajı.", BUGUN)["son_basvuru"] is None


# ---------------- kurallar ----------------
def test_guncellik_kurallari():
    ks, ats = "kariyer_sayfasi", "lever"
    # Yeditek: kariyer sayfası, metinde 08 Mayıs 2023 → kaldırılır
    assert guncellik(ks, "", None, "2023-05-08", set(), BUGUN)["bayat"] == "eski_ilan_tarihi"
    # "2025 Yaz Stajı" 2026'da → kaldırılır
    assert guncellik(ks, "", None, None, {2025}, BUGUN)["bayat"] == "gecmis_donem"
    # İleri tarihli son başvuru → eski tarih ya da geçmiş yıl olsa da kalır
    assert guncellik(ks, "", "2026-11-15", "2023-05-08", {2025}, BUGUN)["bayat"] is None
    # Son başvurusu geçmiş ilan her kaynakta kaldırılır
    assert guncellik(ats, "2026-10-01", "2026-10-20", None, set(), BUGUN)["bayat"] == "son_basvuru_gecti"
    # 2022 tarihli ATS ilanı kalır; eski yıl yazılmaz, "sürekli açık" sayılır
    ats_2022 = guncellik(ats, "2022-03-01", None, None, {2022}, BUGUN)
    assert ats_2022 == {"bayat": None, "yayin": None, "surekli_acik": True}
    # Tarihsiz kariyer sayfası ilanı kalır
    assert guncellik(ks, "", None, None, set(), BUGUN) == {"bayat": None, "yayin": None, "surekli_acik": False}
    # Yeni ilan tarihi gösterilir
    assert guncellik(ks, "", None, "2026-10-12", set(), BUGUN)["yayin"] == "2026-10-12"


def test_kart_tarih_satiri():
    assert tarih_bilgisi({"yayin": "2026-10-12", "ayrinti": {"son_basvuru": "2026-11-15"}}) == [
        "Yayın: 12.10.2026",
        "Son başvuru: 15.11.2026",
    ]
    assert tarih_bilgisi({"surekli_acik": True, "yayin": None}) == ["Sürekli açık başvuru"]
    assert tarih_bilgisi({"yayin": None, "ayrinti": None}) == ["Tarih belirtilmemiş"]


# ---------------- veritabanından yayına ----------------
def ilan_kur(oturum, url, baslik, kaynak="kariyer_sayfasi", yayin_tarihi="", ayrinti_alanlari=None, rol="yazilim"):
    i = Ilan(firma="Acme", baslik=baslik, url=url, kaynak=kaynak, tarih=yayin_tarihi)
    with oturum.begin() as o:
        depo.ilanlari_kaydet(o, [i], set())
        depo.siniflandirma_kaydet(o, {i.kimlik: {"seviye": "staj", "rol": rol, "yapay_zeka": "yok"}}, "test")
        if ayrinti_alanlari is not None:
            depo.ayrinti_kaydet(o, i.kimlik, {"ozet": "Özet.", **ayrinti_alanlari}, "ozet", "test")
    return i.kimlik


def test_bayat_ilanlar_yayindan_ve_bultenden_duser(oturum):
    ilan_kur(oturum, "https://acme.test/eski", "Proje Stajyeri", ayrinti_alanlari={"ilan_tarihi": "2023-05-08"})
    ilan_kur(oturum, "https://acme.test/2025", "2025 Yaz Stajı", ayrinti_alanlari={})
    ilan_kur(
        oturum, "https://acme.test/ileri", "2025 Yaz Stajı (uzatıldı)", ayrinti_alanlari={"son_basvuru": "2026-11-15"}
    )
    ilan_kur(oturum, "https://jobs.lever.co/acme/1", "Software Engineer (New Grad)", "lever", "2022-03-01")
    ilan_kur(oturum, "https://acme.test/tarihsiz", "Yazılım Stajyeri")
    with oturum() as o:
        ilanlar = {i["baslik"]: i for i in depo.yayinlanacak_ilanlar(o, an=AN)}
        nedenler = {i["baslik"]: i["bayat"] for i in depo.yayinlanacak_ilanlar(o, an=AN, bayatlar_dahil=True)}
    assert set(ilanlar) == {"2025 Yaz Stajı (uzatıldı)", "Software Engineer (New Grad)", "Yazılım Stajyeri"}
    assert nedenler["Proje Stajyeri"] == "eski_ilan_tarihi" and nedenler["2025 Yaz Stajı"] == "gecmis_donem"
    assert (
        ilanlar["Software Engineer (New Grad)"]["surekli_acik"]
        and ilanlar["Software Engineer (New Grad)"]["yayin"] is None
    )

    eposta = bulten_epostasi(
        "a@x.com",
        [zenginlestir(i) for i in ilanlar.values()],
        AN,
        "https://internreader.test",
        "https://internreader.test/iptal",
        "https://internreader.test/api/abone/iptal-tek",
        "gunluk",
    )
    for metin in (eposta.metin, eposta.html):
        assert "Sürekli açık başvuru" in metin and "Tarih belirtilmemiş" in metin and "Son başvuru: 15.11.2026" in metin
        assert "2022" not in metin


# ---------------- boru hattı ----------------
LISTE_SAYFASI = """<html><body><h1>İnsan Kaynakları</h1>
<ul><li>Yazılım Stajyeri</li><li>Pazarlama Uzmanı</li></ul>
<div><h3>Yazılım Stajyeri</h3><p>Python bilen 3. sınıf öğrencileri. İlan tarihi: 12.10.2026</p></div>
<div><h3>Pazarlama Uzmanı</h3><p>Sosyal medya deneyimi olan adaylar.</p></div>
</body></html>"""


def test_ilan_bolumu_bir_sonraki_ilana_kadar():
    metin = "İK Yazılım Stajyeri Pazarlama Uzmanı Yazılım Stajyeri Python bilen. Pazarlama Uzmanı Sosyal medya."
    assert ilan_bolumu(metin, "Yazılım Stajyeri", ["Pazarlama Uzmanı"]) == "Yazılım Stajyeri Python bilen."
    assert ilan_bolumu(metin, "Veri Stajyeri", ["Pazarlama Uzmanı"]) == ""


def test_tek_sayfadaki_ilanin_metni_sayfadan_kesilir_ve_tarih_cikarilir(oturum):
    ilan_kur(oturum, "https://acme.test/kariyer#a", "Yazılım Stajyeri")
    ilan_kur(oturum, "https://acme.test/kariyer#b", "Pazarlama Uzmanı", rol="teknik_degil")
    mesajlar = []

    def cevap(_, mesaj):
        mesajlar.append(mesaj)
        return ayrinti(ilan_tarihi="2026-10-12", teknolojiler=["Python"])

    http = SahteHttp(sayfalar={"https://acme.test/kariyer": LISTE_SAYFASI})
    rapor = boru.ayrintilari_zenginlestir(ayarlari_oku(), oturum, http=http, yz=SahteYz(cevap))
    assert rapor["cikarilan"] == 1 and len(mesajlar) == 1
    assert "Python bilen" in mesajlar[0] and "Sosyal medya" not in mesajlar[0]  # komşu ilanın metni gitmez
    with oturum() as o:
        (ilan,) = depo.yayinlanacak_ilanlar(o, an=AN)
    assert ilan["yayin"] == "2026-10-12" and ilan["ayrinti"]["ilan_tarihi"] == "2026-10-12"


def test_tarihsiz_eski_ayrinti_bir_kez_yeniden_cikarilir_ve_bayatsa_duser(oturum):
    ilan_kur(oturum, "https://yeditek.test/proje-stajyeri", "Proje Stajyeri", ayrinti_alanlari={})
    # Tarih veren ATS ilanı yeniden çıkarılmaz (kaynak tarihi zaten var)
    ilan_kur(oturum, "https://jobs.lever.co/acme/2", "Data Intern", "lever", "2026-10-20", {}, rol="veri")
    with oturum.begin() as o:  # göçten önceki kayıtlar gibi: sürüm 1, tarih yok
        o.query(IlanAyrinti).update({"surum": 1})

    yz = SahteYz(lambda _, mesaj: ayrinti(ilan_tarihi="2023-05-08"))
    http = SahteHttp(sayfalar={"https://yeditek.test/proje-stajyeri": f"<p>{YEDITEK}</p>"})
    ayar = ayarlari_oku()
    rapor = boru.ayrintilari_zenginlestir(ayar, oturum, http=http, yz=yz)
    assert rapor["bekleyen"] == 1 and rapor["cikarilan"] == 1 and len(yz.cagrilar) == 1
    assert boru.ayrintilari_zenginlestir(ayar, oturum, http=http, yz=yz)["bekleyen"] == 0  # bir kez
    with oturum() as o:
        assert [i["baslik"] for i in depo.yayinlanacak_ilanlar(o)] == ["Data Intern"]  # Yeditek benzeri düştü
