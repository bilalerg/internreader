"""JSON dışa aktarım: web sitesinin ve MCP sunucusunun okuyacağı makine-okunur liste.

Bu dosya herkese açık bir veri sözleşmesidir: alan adı kaldırmak ya da anlamını değiştirmek SURUM'ü artırır,
yeni alan eklemek artırmaz. Böylece bu listeyi okuyan programlar biçim değişikliğini fark edebilir.
"""

import json
from datetime import datetime

SURUM = 1


def json_metni(ilanlar: list[dict], an: datetime) -> str:
    return json.dumps(
        {"surum": SURUM, "guncelleme": an.isoformat(), "sayi": len(ilanlar), "ilanlar": ilanlar},
        ensure_ascii=False,
        indent=1,
    )


def icerik_degisti(yeni_metin: str, eski_metin: str | None) -> bool:
    """İki ilan listesi `guncelleme` damgası dışında farklı mı? Ara tarama yalnızca veri gerçekten değiştiyse commit eder:
    her commit bir Vercel dağıtımı demek. Eski dosya yoksa ya da bozuksa değişmiş sayılır."""
    try:
        eski = json.loads(eski_metin or "")
    except ValueError:
        return True
    yeni = json.loads(yeni_metin)
    return {k: v for k, v in yeni.items() if k != "guncelleme"} != {k: v for k, v in eski.items() if k != "guncelleme"}
