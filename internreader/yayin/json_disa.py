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
