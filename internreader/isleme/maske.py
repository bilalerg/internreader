"""Kişisel veri maskeleme (KVKK: en az veri).

İlan metinlerinde bazen işe alım uzmanının kişisel e-postası ya da cep telefonu geçer. Bunları saklamaya ve
yayınlamaya ihtiyacımız yok: öğrenci başvuruyu ilanın bağlantısından yapar. Veritabanına yazmadan önce maskelenir.

Kurumsal rol adresleri (ik@, kariyer@, hr@, careers@...) kişisel veri değildir ve başvuru yolu olabilir; korunur.
Telefonlar ayrımsız maskelenir: cep ile kişinin masa hattını metinden güvenle ayırmak mümkün değil.
"""

import re

EPOSTA = re.compile(r"(?<![\w.+-])([A-Za-z0-9._%+-]+)@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,})\b")
ROL_ADRESI = re.compile(
    r"(?i)^(ik|insankaynaklari|insan\.?kaynaklari|hr|humanresources|kariyer|career|careers|jobs?|is|isbasvuru|"
    r"basvuru|cv|recruit(ment|ing)?|talent|people|staj|intern(ship)?|info|bilgi|iletisim|contact|hello|merhaba)$"
)
# Türkiye numaraları: +90 / 0 önekli ya da öneksiz 10 hane (5xx cep, 2xx-4xx sabit, 850 vb.), boşluk/nokta/tire/parantezli.
TELEFON = re.compile(r"(?<![\d+])(?:\+?90[\s.-]?)?\(?0?[2-58]\d{2}\)?[\s.-]?\d{3}[\s.-]?\d{2}[\s.-]?\d{2}(?!\d)")


def _eposta_maskesi(eslesme: re.Match) -> str:
    return eslesme.group(0) if ROL_ADRESI.match(eslesme.group(1).replace("-", "").replace("_", "")) else "[e-posta]"


def kisisel_veriyi_maskele(metin: str) -> str:
    if not metin:
        return metin
    return TELEFON.sub("[telefon]", EPOSTA.sub(_eposta_maskesi, metin))
