"""E-posta imzası ile canlı API anahtarının aynı olduğunu güvenli bir HEAD isteğiyle denetle."""

import sys

import requests

from internreader.ayar import ayarlari_oku
from internreader.bulten.tiklama import jeton_olustur


def main() -> int:
    ayar = ayarlari_oku()
    hedef = "https://internreader.me/anahtar-kontrolu"
    jeton = jeton_olustur({"i": "0" * 16, "u": hedef}, ayar.gizli_anahtar)
    try:
        yanit = requests.head(f"{ayar.site_adresi.rstrip('/')}/api/t/{jeton}", allow_redirects=False, timeout=15)
    except requests.RequestException:
        print("Canlı API'ye ulaşılamadı; bülten güvenle durduruldu.", file=sys.stderr)
        return 1
    if yanit.status_code == 302 and yanit.headers.get("location") == hedef:
        print("E-posta imzası canlı API ile uyumlu.")
        return 0
    print(
        "GitHub Actions ve Vercel INTERNREADER_GIZLI_ANAHTAR değerleri uyuşmuyor olabilir; "
        "başvuru ve abonelikten çıkış bağlantıları çalışmayacağı için bülten durduruldu.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
