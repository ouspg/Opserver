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
    """Lukee tekstirivin readline-tyylisillä pikanäppäimillä.

    Tuetut komennot:
      ← → / Ctrl-B/F   merkki kerrallaan
      Ctrl-A / Ctrl-E   rivin alkuun / loppuun
      Option-B / Option-F  sana taaksepäin / eteenpäin
      Backspace / Ctrl-H   poista edeltävä merkki
      Ctrl-D / Del      poista seuraava merkki
      Ctrl-K            tyhjennä kursorista loppuun
      Ctrl-U            tyhjennä koko rivi
      Ctrl-W            poista edeltävä sana
      Enter             hyväksy
    """
    _, leveys = stdscr.getmaxyx()
    kehote_teksti = kehote + ": "
    kentan_leveys = max(1, leveys - len(kehote_teksti) - 1)

    buffer: list[str] = list(oletus)
    pos = len(buffer)
    offset = max(0, pos - kentan_leveys + 1)

    curses.noecho()
    curses.curs_set(1)

    def paivita() -> None:
        nonlocal offset
        if pos < offset:
            offset = pos
        elif pos >= offset + kentan_leveys:
            offset = pos - kentan_leveys + 1
        stdscr.move(rivi, 0)
        stdscr.clrtoeol()
        stdscr.addstr(rivi, 0, kehote_teksti)
        naytetty = "".join(buffer[offset:offset + kentan_leveys])
        try:
            stdscr.addstr(rivi, len(kehote_teksti), naytetty)
        except curses.error:
            pass
        try:
            stdscr.move(rivi, len(kehote_teksti) + pos - offset)
        except curses.error:
            pass
        stdscr.refresh()

    paivita()

    while True:
        try:
            ch = stdscr.get_wch()
        except curses.error:
            continue

        if isinstance(ch, str):
            if ch in ("\n", "\r"):
                break
            elif ch == "\x01":                  # Ctrl-A: rivin alkuun
                pos = 0
            elif ch == "\x05":                  # Ctrl-E: rivin loppuun
                pos = len(buffer)
            elif ch == "\x02":                  # Ctrl-B: merkki taaksepäin
                pos = max(0, pos - 1)
            elif ch == "\x06":                  # Ctrl-F: merkki eteenpäin
                pos = min(len(buffer), pos + 1)
            elif ch == "\x0b":                  # Ctrl-K: tyhjennä loppuun
                del buffer[pos:]
            elif ch == "\x15":                  # Ctrl-U: tyhjennä koko rivi
                del buffer[:]
                pos = 0
            elif ch == "\x17":                  # Ctrl-W: poista edeltävä sana
                end = pos
                while pos > 0 and buffer[pos - 1] == " ":
                    pos -= 1
                while pos > 0 and buffer[pos - 1] != " ":
                    pos -= 1
                del buffer[pos:end]
            elif ch in ("\x08", "\x7f"):        # Ctrl-H / BS
                if pos > 0:
                    del buffer[pos - 1]
                    pos -= 1
            elif ch == "\x04":                  # Ctrl-D: poista seuraava
                if pos < len(buffer):
                    del buffer[pos]
            elif ch == "\x1b":                  # ESC / Option+kirjain
                stdscr.nodelay(True)
                try:
                    nc = stdscr.get_wch()
                    if nc == "f" or nc == "F":  # Option-F: sana eteenpäin
                        while pos < len(buffer) and not buffer[pos].isalnum():
                            pos += 1
                        while pos < len(buffer) and buffer[pos].isalnum():
                            pos += 1
                    elif nc == "b" or nc == "B":  # Option-B: sana taaksepäin
                        while pos > 0 and not buffer[pos - 1].isalnum():
                            pos -= 1
                        while pos > 0 and buffer[pos - 1].isalnum():
                            pos -= 1
                except curses.error:
                    pass
                finally:
                    stdscr.nodelay(False)
            elif ch.isprintable():
                buffer.insert(pos, ch)
                pos += 1
        else:                                   # kokonaisluku: erikoisnäppäin
            if ch in (curses.KEY_BACKSPACE, 127):
                if pos > 0:
                    del buffer[pos - 1]
                    pos -= 1
            elif ch == curses.KEY_DC:
                if pos < len(buffer):
                    del buffer[pos]
            elif ch == curses.KEY_LEFT:
                pos = max(0, pos - 1)
            elif ch == curses.KEY_RIGHT:
                pos = min(len(buffer), pos + 1)
            elif ch == curses.KEY_HOME:
                pos = 0
            elif ch == curses.KEY_END:
                pos = len(buffer)
            elif ch in (10, 13):
                break

        paivita()

    curses.curs_set(0)
    return "".join(buffer)


def valitse_monivalinta(stdscr, otsikko: str, vaihtoehdot: list[str],
                        valitut: list[str] | None = None) -> list[str] | None:
    """Monivalintalista: Space toggleaa, Enter vahvistaa, q/Esc peruuttaa.

    Palauttaa valittujen arvojen listan tai None jos peruutettu.
    """
    aktiivinen = 0
    valinta_joukko = set(valitut or [])

    while True:
        piirra_otsikko(stdscr, otsikko)
        for i, teksti in enumerate(vaihtoehdot):
            merkki = "[x]" if teksti in valinta_joukko else "[ ]"
            tyyli = curses.A_REVERSE if i == aktiivinen else curses.A_NORMAL
            stdscr.addstr(3 + i, 0, f"{merkki} {teksti}", tyyli)
        ohje_rivi = 3 + max(len(vaihtoehdot), 1) + 1
        stdscr.addstr(ohje_rivi, 0, "↑/↓ liiku · Space valitse · Enter vahvista · q takaisin")
        nappain = stdscr.getch()
        if nappain in (curses.KEY_UP, ord("k")):
            aktiivinen = (aktiivinen - 1) % max(len(vaihtoehdot), 1)
        elif nappain in (curses.KEY_DOWN, ord("j")):
            aktiivinen = (aktiivinen + 1) % max(len(vaihtoehdot), 1)
        elif nappain == ord(" "):
            kohde = vaihtoehdot[aktiivinen]
            if kohde in valinta_joukko:
                valinta_joukko.discard(kohde)
            else:
                valinta_joukko.add(kohde)
        elif nappain in (curses.KEY_ENTER, 10, 13):
            return [v for v in vaihtoehdot if v in valinta_joukko]
        elif nappain in (ord("q"), 27):
            return None


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
