"""kyberESR CLI-käyttöliittymän päävalikko."""
import curses
import locale

from cliui.apurit import valitse_listasta, piirra_otsikko, nayta_viesti, alusta_varit
from cliui import korkeakoulunaytto, hakunaytto, tutkimusnaytto, luokittelunaytto, arviointinaytto

VALIKKO = [
    "1) Muokkaa korkeakouluja",
    "2) Hae kurssit opinto-oppaista",
    "3) Määrittele tutkimuksia",
    "4) Luokittele",
    "5) Arvioi",
]


def _ei_toteutettu(stdscr) -> None:
    piirra_otsikko(stdscr, "kyberESR")
    nayta_viesti(stdscr, "Tätä toimintoa ei ole vielä toteutettu.")


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
    }
    while True:
        valinta = valitse_listasta(stdscr, "kyberESR — päävalikko", VALIKKO)
        if valinta is None:
            return
        kasittelijat[valinta](stdscr)


def main() -> None:
    locale.setlocale(locale.LC_ALL, "")
    curses.wrapper(paavalikko)


if __name__ == "__main__":
    main()
