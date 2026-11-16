"""Başvuru durumunu düzenli doğrulama: sınırlı paralellik, robots, kaynak yasakları; LLM çağırmaz."""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import requests
from sqlalchemy.orm import sessionmaker

from internreader.ag import HttpIstemci, RobotsEngeli, hata_ozeti
from internreader.ayar import Ayarlar
from internreader.db import simdi
from internreader.depo.dogrulama import dogrulama_bekleyenler, dogrulama_yaz
from internreader.isleme.basvuru import BasvuruSonucu, alan_yasak, sayfayi_dogrula


def basvurulari_dogrula(ayar: Ayarlar, oturum: sessionmaker, http: HttpIstemci | None = None, sinir: int = 120) -> dict:
    an = simdi()
    http = http or HttpIstemci(ayar.kullanici_ajani, ayar.http_zaman_asimi)
    with oturum() as o:
        adaylar = dogrulama_bekleyenler(o, sinir, an)

    def kontrol(ilan):
        url = ilan["url"]
        try:
            if alan_yasak(url):
                return ilan["kimlik"], BasvuruSonucu("belirsiz", "kaynak_politikasi_geregi_okunmadi")
            if "#" in url:
                return ilan["kimlik"], BasvuruSonucu("belirsiz", "coklu_ilan_sayfasi")
            son_url, html = http.sayfa(url, adres_izinli=lambda adres: not alan_yasak(adres))
            if alan_yasak(son_url):
                return ilan["kimlik"], BasvuruSonucu("belirsiz", "yasak_kaynaga_yonlendi")
            return ilan["kimlik"], sayfayi_dogrula(ilan["baslik"], url, son_url, html)
        except RobotsEngeli:
            return ilan["kimlik"], BasvuruSonucu("belirsiz", "robots_engeli")
        except requests.RequestException as hata:
            # 404/410, 403, 429 veya timeout tek başına ilanın kapandığını kanıtlamaz.
            return ilan["kimlik"], BasvuruSonucu("belirsiz", hata_ozeti(hata))
        except (ValueError, UnicodeError):
            return ilan["kimlik"], BasvuruSonucu("belirsiz", "sayfa_cozumlendi_ama_okunamadi")

    with ThreadPoolExecutor(max_workers=min(4, ayar.is_parcacigi)) as havuz:
        sonuclar = list(havuz.map(kontrol, adaylar))
    rapor = Counter()
    with oturum.begin() as o:
        for kimlik, sonuc in sonuclar:
            dogrulama_yaz(o, kimlik, sonuc, an)
            rapor[sonuc.durum] += 1
    return {"kontrol_edilen": len(sonuclar), **dict(rapor)}
