"""Jaetut curses-apufunktiot CLI-käyttöliittymälle."""
import curses


def alusta_varit() -> None:
    """Käyttää terminaalin omaa taustaväriä (-1 = läpinäkyvä).
    Näin iTerm2:n oma väritys ja korostus toimivat oikein."""
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_WHITE, -1)


def piirra_otsikko(stdscr, teksti: str) -> None:
    stdscr.clear()
    stdscr.addstr(0, 0, teksti, curses.A_BOLD)
    stdscr.addstr(1, 0, "=" * len(teksti))


def nayta_viesti(stdscr, teksti: str, rivi: int = -1) -> None:
    """Näyttää viestin ja odottaa näppäinpainallusta."""
    if rivi < 0:
        rivi = stdscr.getmaxyx()[0] - 2
    stdscr.addstr(rivi, 0, teksti)
    stdscr.addstr(rivi + 1, 0, "Paina mitä tahansa näppäintä jatkaaksesi...")
    stdscr.getch()


def lue_teksti(stdscr, kehote: str, rivi: int, oletus: str = "") -> str:
    """Lukee yhden tekstirivin käyttäjältä. Tyhjä syöte palauttaa oletuksen."""
    naytto = kehote
    if oletus:
        naytto += f" [{oletus}]"
    naytto += ": "
    stdscr.addstr(rivi, 0, naytto)
    curses.echo()
    curses.curs_set(1)
    try:
        syote = stdscr.getstr(rivi, len(naytto)).decode("utf-8").strip()
    finally:
        curses.noecho()
        curses.curs_set(0)
    return syote if syote else oletus


def valitse_listasta(stdscr, otsikko: str, vaihtoehdot: list[str]) -> int | None:
    """Nuolinäppäimillä valittava lista. Palauttaa valitun indeksin tai None (Esc/q)."""
    valittu = 0
    while True:
        piirra_otsikko(stdscr, otsikko)
        if not vaihtoehdot:
            stdscr.addstr(3, 0, "(ei kohteita)")
        for i, teksti in enumerate(vaihtoehdot):
            tyyli = curses.A_REVERSE if i == valittu else curses.A_NORMAL
            stdscr.addstr(3 + i, 0, teksti, tyyli)
        ohje_rivi = 3 + max(len(vaihtoehdot), 1) + 1
        stdscr.addstr(ohje_rivi, 0, "↑/↓ liiku · Enter valitse · q takaisin")
        nappain = stdscr.getch()
        if nappain in (curses.KEY_UP, ord("k")):
            valittu = (valittu - 1) % max(len(vaihtoehdot), 1)
        elif nappain in (curses.KEY_DOWN, ord("j")):
            valittu = (valittu + 1) % max(len(vaihtoehdot), 1)
        elif nappain in (curses.KEY_ENTER, 10, 13):
            if vaihtoehdot:
                return valittu
        elif nappain in (ord("q"), 27):
            return None
