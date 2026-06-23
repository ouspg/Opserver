"""Testit muokkaa_lomake-komponentin logiikalle (navigointi/tallennus/validointi)."""
import curses
from unittest.mock import patch
from cliui import apurit


class FakeScr:
    """Minimaalinen stdscr-tynkä: getch syöttää skriptatut näppäimet."""
    def __init__(self, nappaimet):
        self._n = iter(nappaimet)

    def getmaxyx(self):
        return (40, 100)

    def getch(self):
        return next(self._n)

    def clear(self): pass
    def addstr(self, *a, **k): pass
    def move(self, *a): pass
    def clrtoeol(self): pass
    def refresh(self): pass


def _aja(nappaimet, kentat):
    with patch("cliui.apurit.curses.color_pair", lambda n: 0):
        return apurit.muokkaa_lomake(FakeScr(nappaimet), "Otsikko", kentat)


def _kentat():
    return [
        {"avain": "a", "otsikko": "A", "arvo": "x"},
        {"avain": "b", "otsikko": "B", "arvo": "y"},
    ]


def test_tallenna_palauttaa_arvot():
    # alas, alas (Tallenna), Enter
    tulos = _aja([curses.KEY_DOWN, curses.KEY_DOWN, 10], _kentat())
    assert tulos == {"a": "x", "b": "y"}


def test_peruutus_palauttaa_none():
    assert _aja([ord("q")], _kentat()) is None


def test_muokkain_paivittaa_arvon():
    kentat = [{"avain": "a", "otsikko": "A", "arvo": "vanha",
               "muokkain": lambda s, v, kaikki: "uusi"}]
    # Enter kentällä 0 (muokkaa) → alas (Tallenna) → Enter
    tulos = _aja([10, curses.KEY_DOWN, 10], kentat)
    assert tulos == {"a": "uusi"}


def test_validointi_estaa_tallennuksen():
    kentat = [{"avain": "a", "otsikko": "A", "arvo": "",
               "validoi": lambda v: "pakollinen" if not v else None}]
    # alas (Tallenna) → Enter (validointi estää, jää lomakkeeseen) → q (peruuta)
    assert _aja([curses.KEY_DOWN, 10, ord("q")], kentat) is None


def test_muokkain_none_ei_muuta_arvoa():
    kentat = [{"avain": "a", "otsikko": "A", "arvo": "ennallaan",
               "muokkain": lambda s, v, kaikki: None}]
    tulos = _aja([10, curses.KEY_DOWN, 10], kentat)
    assert tulos == {"a": "ennallaan"}
