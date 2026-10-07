"""Yhdistämisehdotusten kuittausnäkymä (lista-arvojen normalisointi ennen raporttia).

Ohut näkymä: ehdotukset (raportti.listanormalisointi.Ehdotus) muodostetaan ja
tallennetaan muualla; tämä vain näyttää ne ja antaa käyttäjän valita/muokata."""
import curses

from cliui.apurit import piirra_otsikko
from cliui.tekstikentta import lue_teksti

_OHJE = "↑/↓ PgUp/PgDn liiku · Space ruksi · a kaikki · Enter muokkaa kohdetta / Hyväksy · Esc/q peruuta"
_NAPPI = "[ Hyväksy ]"


def _kirjoita(stdscr, y: int, teksti: str, attr=curses.A_NORMAL) -> None:
    try:
        stdscr.addstr(y, 0, teksti[:stdscr.getmaxyx()[1] - 1], attr)
    except curses.error:
        pass


def _muokkaa_kohdetta(stdscr, ehdotus) -> None:
    """Enter rivillä: kohdeluokan muokkaus, uusi Enter kuittaa. Tyhjä = ei muutosta;
    kohde == lähde poistaa ruksin (ei muuttaisi mitään)."""
    uusi = lue_teksti(stdscr, f"{ehdotus.lahde} -->", stdscr.getmaxyx()[0] - 2, ehdotus.kohde).strip()
    if uusi:
        ehdotus.kohde = uusi
        ehdotus.valittu = uusi != ehdotus.lahde


def kuittaa_ehdotukset(stdscr, otsikko: str, ehdotukset: list) -> list | None:
    """Näyttää ehdotukset ruksilistana ja Hyväksy-napin listan lopussa.
    Palauttaa ehdotukset (valittu/kohde päivitettyinä) Hyväksy-napista, None jos
    käyttäjä peruuttaa (Esc/q)."""
    n = len(ehdotukset)
    aktiivinen = 0           # 0..n-1 = ehdotus, n = Hyväksy-nappi
    while True:
        piirra_otsikko(stdscr, otsikko)
        korkeus, _ = stdscr.getmaxyx()
        valittuja = sum(e.valittu for e in ehdotukset)
        _kirjoita(stdscr, 2, f"{n} ehdotusta, {valittuja} valittu — ruksitut yhdistetään, muut hylätään")
        nakyvat = max(1, korkeus - 5)       # otsikko 0-2, vihje alin rivi, muokkausrivi
        alku = min(max(0, aktiivinen - nakyvat // 2), max(0, n + 1 - nakyvat))
        for rivi, i in enumerate(range(alku, min(alku + nakyvat, n + 1))):
            attr = curses.A_REVERSE if i == aktiivinen else curses.A_NORMAL
            _kirjoita(stdscr, 3 + rivi, ehdotukset[i].rivi() if i < n else _NAPPI,
                      attr | (curses.A_BOLD if i == n else 0))
        _kirjoita(stdscr, korkeus - 1, f"{_OHJE}   [{min(aktiivinen + 1, n)}/{n}]")
        stdscr.refresh()

        nappain = stdscr.getch()
        if nappain in (curses.KEY_UP, ord("k")):
            aktiivinen = (aktiivinen - 1) % (n + 1)
        elif nappain in (curses.KEY_DOWN, ord("j")):
            aktiivinen = (aktiivinen + 1) % (n + 1)
        elif nappain == curses.KEY_PPAGE:
            aktiivinen = max(0, aktiivinen - nakyvat)
        elif nappain == curses.KEY_NPAGE:
            aktiivinen = min(n, aktiivinen + nakyvat)
        elif nappain == ord(" ") and aktiivinen < n:
            ehdotukset[aktiivinen].valittu = not ehdotukset[aktiivinen].valittu
        elif nappain == ord("a"):
            kaikki = not all(e.valittu for e in ehdotukset)
            for e in ehdotukset:
                e.valittu = kaikki
        elif nappain in (curses.KEY_ENTER, 10, 13):
            if aktiivinen == n:
                return ehdotukset
            _muokkaa_kohdetta(stdscr, ehdotukset[aktiivinen])
        elif nappain in (ord("q"), 27):
            return None
