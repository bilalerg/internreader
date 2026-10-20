"""Depo modüllerinin ortak yardımcıları."""

from datetime import UTC, datetime


def utc(an: datetime | None) -> datetime | None:
    """SQLite saat dilimini saklamaz; okunan saf (naive) tarihleri UTC kabul eder."""
    if an is None:
        return None
    return an if an.tzinfo else an.replace(tzinfo=UTC)


def _parcalar(liste: list, boyut: int = 500):
    for i in range(0, len(liste), boyut):
        yield liste[i : i + boyut]
