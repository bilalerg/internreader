"""YzIstemci'nin bütçe ve maliyet kaydı davranışı (gerçek API yerine sahte Anthropic istemcisi)."""

from types import SimpleNamespace

import anthropic
import httpx2
import pytest
from pydantic import BaseModel

from internreader.yz.istemci import ButceAsildi, CiktiBozuk, ServisHatasi, YzIstemci, YzKullanilamaz


class Cevap(BaseModel):
    ad: str


class SahteAnthropic:
    def __init__(self, metin, stop_reason="end_turn", girdi=1_000_000, cikti=0):
        self.istekler = []
        self._yanit = SimpleNamespace(
            content=[SimpleNamespace(type="text", text=metin)],
            stop_reason=stop_reason,
            usage=SimpleNamespace(input_tokens=girdi, output_tokens=cikti),
        )
        self.messages = self

    def create(self, **istek):
        self.istekler.append(istek)
        return self._yanit


def test_gecerli_cevap_dogrulanir_ve_maliyet_kaydedilir():
    sahte = SahteAnthropic('{"ad": "Beakwise"}')
    yz = YzIstemci("claude-haiku-5-5", tavan_usd=1.0, istemci=sahte)
    assert yz.yapilandirilmis("test", "sistem", "mesaj", Cevap).ad == "Beakwise"
    assert yz.harcanan_usd == pytest.approx(0.10)  # 1M girdi token × 0,10 $
    assert sahte.istekler[0]["output_config"]["format"]["type"] == "json_schema"


def test_kesilen_cevabin_maliyeti_yine_de_sayilir():
    yz = YzIstemci("claude-haiku-5-5", 1.0, istemci=SahteAnthropic('{"ad": "Bea', stop_reason="max_tokens"))
    with pytest.raises(CiktiBozuk):
        yz.yapilandirilmis("test", "s", "m", Cevap)
    assert yz.harcanan_usd > 0 and len(yz.kullanimlar) == 1


def test_bozuk_json_cikti_bozuk_hatasina_cevrilir():
    yz = YzIstemci("claude-haiku-5-5", 1.0, istemci=SahteAnthropic('{"baska": 1}'))
    with pytest.raises(CiktiBozuk):
        yz.yapilandirilmis("test", "s", "m", Cevap)


def test_butce_dolunca_cagri_yapilmaz():
    sahte = SahteAnthropic('{"ad": "x"}', girdi=2_000_000)  # tek çağrı 0,20 $
    yz = YzIstemci("claude-haiku-5-5", tavan_usd=0.15, istemci=sahte)
    yz.yapilandirilmis("test", "s", "m", Cevap)
    with pytest.raises(ButceAsildi):
        yz.yapilandirilmis("test", "s", "m", Cevap)
    assert len(sahte.istekler) == 1


class CokenAnthropic:
    """Her istekte bağlantı hatası veren sahte istemci (kredi bitti / servis kesintisi benzetimi)."""

    def __init__(self):
        self.istek_sayisi = 0
        self.messages = self

    def create(self, **istek):
        self.istek_sayisi += 1
        raise anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages"))


def test_servis_ust_uste_hata_verince_sigorta_atar():
    sahte = CokenAnthropic()
    yz = YzIstemci("claude-haiku-5-5", 1.0, istemci=sahte)
    for _ in range(YzIstemci.AZAMI_ARDISIK_HATA):
        with pytest.raises(ServisHatasi):
            yz.yapilandirilmis("test", "s", "m", Cevap)
    with pytest.raises(YzKullanilamaz):  # artık istek atılmaz
        yz.yapilandirilmis("test", "s", "m", Cevap)
    assert sahte.istek_sayisi == YzIstemci.AZAMI_ARDISIK_HATA and not yz.kullanilabilir_mi()


# ---------------------------------------------------------------- toplu mod (Message Batches API)
def _yanit(metin, girdi=1_000_000, stop_reason="end_turn"):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=metin)],
        stop_reason=stop_reason,
        usage=SimpleNamespace(input_tokens=girdi, output_tokens=0),
    )


class SahteToplu:
    """messages.batches.create/retrieve/results/cancel ve messages.create (normal yol) taklidi."""

    def __init__(self, sonuc_turleri: dict[str, str], bitis_sorgusu: int = 1):
        self.sonuc_turleri = sonuc_turleri  # custom_id → succeeded | errored
        self.bitis_sorgusu = bitis_sorgusu  # kaçıncı sorguda "ended" olur (çok büyükse hiç bitmez)
        self.sorgu = 0
        self.iptal = False
        self.normal_istekler = 0
        self.gonderilen: list[dict] = []
        self.messages = SimpleNamespace(create=self._create, batches=self)

    def _create(self, **istek):
        self.normal_istekler += 1
        return _yanit('{"ad": "normal"}')

    def create(self, requests):
        self.gonderilen = requests
        return SimpleNamespace(id="is_1", processing_status="in_progress")

    def retrieve(self, kimlik):
        self.sorgu += 1
        bitti = self.iptal or self.sorgu >= self.bitis_sorgusu
        return SimpleNamespace(id=kimlik, processing_status="ended" if bitti else "in_progress")

    def cancel(self, kimlik):
        self.iptal = True

    def results(self, kimlik):
        for istek in self.gonderilen:
            tur = "canceled" if self.iptal else self.sonuc_turleri.get(istek["custom_id"], "succeeded")
            mesaj = _yanit(f'{{"ad": "{istek["custom_id"]}"}}') if tur == "succeeded" else None
            yield SimpleNamespace(custom_id=istek["custom_id"], result=SimpleNamespace(type=tur, message=mesaj))


def _toplu_yz(sahte, tavan=10.0, bekleme=60.0):
    return YzIstemci("claude-haiku-5-5", tavan, istemci=sahte, toplu=True, toplu_bekleme_sn=bekleme, toplu_aralik_sn=0)


def test_toplu_mod_yari_fiyat_ve_kayit():
    sahte = SahteToplu({})
    yz = _toplu_yz(sahte)
    sonuc = yz.coklu_yapilandirilmis("test", "s", [("a", "m1"), ("b", "m2")], Cevap)
    assert {k: v.ad for k, v in sonuc.items()} == {"a": "i0", "b": "i1"}
    assert yz.harcanan_usd == pytest.approx(0.10)  # 2 × 1M token × 0,10 $ × yarı fiyat
    assert all(k["toplu"] for k in yz.kullanimlar) and sahte.normal_istekler == 0


def test_toplu_modda_basarisiz_sonuc_normal_yoldan_denenir():
    sahte = SahteToplu({"i1": "errored"})
    sonuc = _toplu_yz(sahte).coklu_yapilandirilmis("test", "s", [("a", "m1"), ("b", "m2")], Cevap)
    assert sonuc["a"].ad == "i0" and sonuc["b"].ad == "normal" and sahte.normal_istekler == 1


def test_toplu_is_zamaninda_bitmezse_iptal_edilip_normal_yoldan_gonderilir():
    sahte = SahteToplu({}, bitis_sorgusu=10**9)
    sonuc = _toplu_yz(sahte, bekleme=0).coklu_yapilandirilmis("test", "s", [("a", "m1")], Cevap)
    assert sahte.iptal and sonuc["a"].ad == "normal"


def test_toplu_is_butceye_sigmayan_istegi_gondermez():
    sahte = SahteToplu({})
    yz = _toplu_yz(sahte, tavan=0.0002)  # tek isteğin tahmini maliyeti ~0,00018 $
    sonuc = yz.coklu_yapilandirilmis("test", "s", [("a", "m1"), ("b", "m2")], Cevap)
    assert len(sahte.gonderilen) == 1 and isinstance(sonuc["b"], ButceAsildi)
