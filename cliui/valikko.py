"""kyberESR CLI-käyttöliittymän päävalikko."""
import curses

from cliui.apurit import valitse_listasta, piirra_otsikko, nayta_viesti, alusta_varit
from cliui import korkeakoulunaytto, hakunaytto

VALIKKO = [
    "1) Muokkaa korkeakouluja",
    "2) Hae kurssit opinto-oppaista",
    "3) Muokkaa luokitteluja",
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
        2: _ei_toteutettu,
        3: _ei_toteutettu,
        4: _ei_toteutettu,
    }
    while True:
        valinta = valitse_listasta(stdscr, "kyberESR — päävalikko", VALIKKO)
        if valinta is None:
            return
        kasittelijat[valinta](stdscr)


def main() -> None:
    curses.wrapper(paavalikko)


if __name__ == "__main__":
    main()
