"""Opserver CLI-käyttöliittymän päävalikko."""
import curses
import locale

from cliui.apurit import valitse_listasta, piirra_otsikko, nayta_viesti, alusta_varit
from cliui import korkeakoulunaytto, hakunaytto, tutkimusnaytto, luokittelunaytto, arviointinaytto, raporttinaytto, asetuksetnaytto

VALIKKO = [
    "1) Muokkaa korkeakouluja",
    "2) Hae kurssit opinto-oppaista",
    "3) Määrittele tutkimuksia",
    "4) Luokittele",
    "5) Arvioi",
    "6) Tee raportti",
    "A) LLM-asetukset",
]


def paavalikko(stdscr) -> None:
    alusta_varit()
    stdscr.bkgd(" ", curses.color_pair(1))
    curses.curs_set(0)
    kasittelijat = {
        0: korkeakoulunaytto.nayta,
        1: hakunaytto.nayta,
        2: tutkimusnaytto.nayta,
        3: luokittelunaytto.nayta,
        4: arviointinaytto.nayta,
        5: raporttinaytto.nayta,
        6: asetuksetnaytto.nayta,
    }
    while True:
        valinta = valitse_listasta(stdscr, "Opserver — päävalikko", VALIKKO)
        if valinta is None:
            return
        kasittelijat[valinta](stdscr)


def main() -> None:
    locale.setlocale(locale.LC_ALL, "")
    curses.wrapper(paavalikko)


if __name__ == "__main__":
    main()
