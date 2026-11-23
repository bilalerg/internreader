from ops.teknokent_dizin_pilotu import ad_anahtari, eslestir, itu_kayitlari, ytu_kayitlari


def test_itu_dizini_ve_alan_adi_eslesmesi():
    html = '<a href="https://firmalar.ariteknokent.com.tr/companies/ornek"><span class="sr-only">Örnek Teknoloji detaylarını görüntüle</span></a>'
    kayit = itu_kayitlari(html)[0]
    kayit["web"] = "https://www.ornek.com/"
    firma = {"ad": "Örnek A.Ş.", "web": "https://ornek.com", "ats": "", "kariyer": ""}
    assert eslestir([kayit], [firma])[0]["eslesme"] == "alan_adi"


def test_ytu_dizini_ve_turkce_ad():
    html = '<a href="https://sirket.com"><div class="service-block_six-inner"><div class="service-block_six-text">İş Yazılım</div></div></a>'
    assert ytu_kayitlari(html)[0]["ad"] == "İş Yazılım"
    assert ad_anahtari("İş Yazılım") == ad_anahtari("IS YAZILIM")
