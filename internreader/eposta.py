"""E-posta: ileti modeli ve göndericiler.

Gönderici bir arayüzdür (EpostaGonderici):
- DosyayaYazanGonderici: geliştirme. E-posta gönderilmez, `cikti/giden_eposta/` klasörüne okunabilir dosya olarak yazılır.
- SmtpGonderici: gerçek gönderim (Python'un yerleşik smtplib'i; Amazon SES, Brevo, Mailgun gibi her SMTP servisiyle).
Hangisinin kullanılacağına ayarlar karar verir (gonderici_olustur): SMTP sunucusu tanımlıysa gerçek gönderim.
Şablonlar ayrı modüllerde: onay e-postası burada, bülten internreader/bulten/sablon.py'de.
"""

import logging
import re
import smtplib
import ssl
from dataclasses import dataclass, field
from datetime import datetime
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path
from typing import Protocol

from internreader.ayar import CIKTI, Ayarlar

kayit = logging.getLogger(__name__)


@dataclass(frozen=True)
class Eposta:
    alici: str
    konu: str
    metin: str  # düz metin sürüm (her e-posta istemcisi gösterebilir; spam filtreleri de ister)
    html: str | None = None
    basliklar: dict[str, str] = field(default_factory=dict)  # ör. List-Unsubscribe


class EpostaGonderici(Protocol):
    def gonder(self, eposta: Eposta) -> None: ...


class DosyayaYazanGonderici:
    """Geliştirme göndericisi: e-postayı göndermez, okunabilir dosyalara yazar (düz metin + varsa HTML)."""

    def __init__(self, klasor: Path):
        self.klasor = klasor

    def gonder(self, eposta: Eposta) -> None:
        self.klasor.mkdir(parents=True, exist_ok=True)
        ad = f"{datetime.now():%Y%m%d_%H%M%S_%f}_{re.sub(r'[^a-z0-9]+', '_', eposta.alici.lower())}"
        basliklar = "".join(f"{k}: {v}\n" for k, v in eposta.basliklar.items())
        (self.klasor / f"{ad}.txt").write_text(
            f"Kime: {eposta.alici}\nKonu: {eposta.konu}\n{basliklar}\n{eposta.metin}\n", encoding="utf-8", newline="\n"
        )
        if eposta.html:
            (self.klasor / f"{ad}.html").write_text(eposta.html, encoding="utf-8", newline="\n")
        kayit.info("E-posta gönderilmedi, dosyaya yazıldı: %s", self.klasor / ad)


class SmtpGonderici:
    """SMTP ile gönderim. Bülten gönderirken bağlantı bir kez açılır, bütün e-postalar aynı bağlantıdan gider:
        with SmtpGonderici(...) as g: g.gonder(e1); g.gonder(e2)
    Bağlam dışında çağrılırsa her e-posta için ayrı bağlantı açılır (onay e-postası gibi tekil gönderimler)."""

    def __init__(self, sunucu: str, port: int, kullanici: str, parola: str, kimden: str, yanit: str = ""):
        self.sunucu, self.port, self.kullanici, self.parola = sunucu, port, kullanici, parola
        self.kimden, self.yanit = kimden, yanit
        self._baglanti: smtplib.SMTP | None = None

    def _baglan(self) -> smtplib.SMTP:
        baglam = ssl.create_default_context()
        if self.port == 465:  # doğrudan TLS
            baglanti: smtplib.SMTP = smtplib.SMTP_SSL(self.sunucu, self.port, context=baglam, timeout=30)
        else:  # 587: düz bağlanıp STARTTLS ile şifrele
            baglanti = smtplib.SMTP(self.sunucu, self.port, timeout=30)
            baglanti.starttls(context=baglam)
        if self.kullanici:
            baglanti.login(self.kullanici, self.parola)
        return baglanti

    def __enter__(self) -> "SmtpGonderici":
        self._baglanti = self._baglan()
        return self

    def __exit__(self, *_) -> None:
        if self._baglanti is not None:
            try:
                self._baglanti.quit()
            finally:
                self._baglanti = None

    def ileti(self, eposta: Eposta) -> EmailMessage:
        ileti = EmailMessage()
        ileti["From"] = self.kimden
        ileti["To"] = eposta.alici
        ileti["Subject"] = eposta.konu
        ileti["Date"] = formatdate(localtime=False)
        ileti["Message-ID"] = make_msgid(domain=self.kimden.rsplit("@", 1)[-1].strip("> ") or None)
        if self.yanit:
            ileti["Reply-To"] = self.yanit
        for ad, deger in eposta.basliklar.items():
            ileti[ad] = deger
        ileti.set_content(eposta.metin)
        if eposta.html:
            ileti.add_alternative(eposta.html, subtype="html")
        return ileti

    def gonder(self, eposta: Eposta) -> None:
        if self._baglanti is not None:
            self._baglanti.send_message(self.ileti(eposta))
            return
        with self as tekil:
            tekil._baglanti.send_message(self.ileti(eposta))  # type: ignore[union-attr]


def gonderici_olustur(ayar: Ayarlar) -> EpostaGonderici:
    if ayar.smtp_sunucu:
        return SmtpGonderici(
            ayar.smtp_sunucu,
            ayar.smtp_port,
            ayar.smtp_kullanici,
            ayar.smtp_parola,
            ayar.eposta_kimden,
            ayar.eposta_yanit,
        )
    kayit.warning("SMTP tanımlı değil: e-postalar gönderilmeyecek, cikti/giden_eposta/ klasörüne yazılacak")
    return DosyayaYazanGonderici(CIKTI / "giden_eposta")


def dogrulama_epostasi(alici: str, onay_linki: str) -> Eposta:
    return Eposta(
        alici=alici,
        konu="InternReader aboneliğini onayla",
        metin=(
            "Merhaba,\n\n"
            "InternReader bültenine abone olmak için bu adresi kullandın. Aboneliğini başlatmak için bağlantıya tıkla:\n\n"
            f"{onay_linki}\n\n"
            "Bağlantı 72 saat geçerli. Bu isteği sen yapmadıysan bu e-postayı yok sayabilirsin; "
            "onaylanmayan adresler 72 saat sonra kendiliğinden silinir.\n\n"
            "InternReader — Türkiye'deki yazılım ve yapay zekâ stajları, her sabah tek e-postada."
        ),
    )
