"""Geriye dönük uyumluluk: `python -m internreader.topla` = `python -m internreader calistir`.

Yeni komutlar için: python -m internreader --help
"""

from internreader.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main(["calistir"]))
