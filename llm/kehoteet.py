"""Järjestelmäkehotteiden lukeminen kehoteet/-kansiosta.

Jaettu lukija, jotta sekä pipeline (luokittelu/arviointi) että WebUI voivat
laskea kehotetiivisteet samasta lähteestä ilman koodin kahdentamista.
"""
import os

_KANSIO = os.path.join(os.path.dirname(__file__), "..", "kehoteet")


def lue(tiedosto: str) -> str:
    """Lukee ja palauttaa kehotetiedoston sisällön (whitespace siivottuna)."""
    with open(os.path.join(_KANSIO, tiedosto), encoding="utf-8") as f:
        return f.read().strip()
