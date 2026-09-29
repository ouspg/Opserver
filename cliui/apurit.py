"""Jaetut curses-apufunktiot CLI-käyttöliittymälle: värit, otsikko, viestit ja listavalinnat.
Tekstinsyöttö: cliui.tekstikentta, lomake: cliui.lomake."""
import curses


def alusta_varit() -> None:
    """Käyttää terminaalin omaa taustaväriä (-1 = läpinäkyvä).
    Näin iTerm2:n oma väritys ja korostus toimivat oikein."""
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_WHITE, -1)
    curses.init_pair(2, curses.COLOR_CYAN, -1)   # lomakkeen kenttäotsikot


def piirra_otsikko(stdscr, teksti: str) -> None:
    stdscr.clear()
    leveys = stdscr.getmaxyx()[1]
    teksti = teksti[:leveys - 1]  # estä addstr-ylivuoto kapealla ruudulla
    stdscr.addstr(0, 0, teksti, curses.A_BOLD)
    stdscr.addstr(1, 0, "=" * len(teksti))


def kirjoita_rivi(stdscr, rivi: int, teksti: str) -> None:
    """Kirjoittaa yhden rivin ja tyhjentää lopun. Katkaisu ruudun leveyteen on
    pakollinen: ilman sitä pitkä teksti rivittyy seuraavalle riville, jolloin
    clrtoeol tyhjentää väärän kohdan ja näkymään jää sekaisia jäänteitä."""
    leveys = stdscr.getmaxyx()[1]
    stdscr.addstr(rivi, 0, teksti[:leveys - 1])
    stdscr.clrtoeol()


def nayta_viesti(stdscr, teksti: str, rivi: int = -1) -> None:
    """Näyttää viestin ja odottaa näppäinpainallusta."""
    if rivi < 0:
        rivi = stdscr.getmaxyx()[0] - 2
    stdscr.addstr(rivi, 0, teksti)
    stdscr.addstr(rivi + 1, 0, "Paina mitä tahansa näppäintä jatkaaksesi...")
    stdscr.getch()


def valitse_monivalinta(stdscr, otsikko: str, vaihtoehdot: list[str],
                        valitut: list[str] | None = None) -> list[str] | None:
    """Monivalintalista: Space toggleaa, Enter vahvistaa, q/Esc peruuttaa.

    Palauttaa valittujen arvojen listan tai None jos peruutettu.
    """
    aktiivinen = 0
    n = len(vaihtoehdot)
    valinta_joukko = set(valitut or [])

    while True:
        piirra_otsikko(stdscr, otsikko)
        korkeus, leveys = stdscr.getmaxyx()

        # Vieritysnäkymä: kuinka monta riviä mahtuu (ohje + reunavara varattu)
        nakyvat = max(1, korkeus - 3 - 2)
        if n > nakyvat:
            offset = min(max(0, aktiivinen - nakyvat // 2), n - nakyvat)
        else:
            offset = 0
        loppu = min(offset + nakyvat, n)

        for rivi_idx, i in enumerate(range(offset, loppu)):
            merkki = "[x]" if vaihtoehdot[i] in valinta_joukko else "[ ]"
            tyyli = curses.A_REVERSE if i == aktiivinen else curses.A_NORMAL
            stdscr.addstr(3 + rivi_idx, 0, f"{merkki} {vaihtoehdot[i]}"[:leveys - 1], tyyli)

        ohje = "↑/↓ liiku · Space valitse · Enter vahvista · q takaisin"
        if n > nakyvat:
            ohje += f"   [{aktiivinen + 1}/{n}]"
        ohje_rivi = min(3 + max(loppu - offset, 1), korkeus - 1)
        stdscr.addstr(ohje_rivi, 0, ohje[:leveys - 1])

        nappain = stdscr.getch()
        if nappain in (curses.KEY_UP, ord("k")):
            aktiivinen = (aktiivinen - 1) % max(n, 1)
        elif nappain in (curses.KEY_DOWN, ord("j")):
            aktiivinen = (aktiivinen + 1) % max(n, 1)
        elif nappain == ord(" "):
            if vaihtoehdot:
                kohde = vaihtoehdot[aktiivinen]
                if kohde in valinta_joukko:
                    valinta_joukko.discard(kohde)
                else:
                    valinta_joukko.add(kohde)
        elif nappain in (curses.KEY_ENTER, 10, 13):
            return [v for v in vaihtoehdot if v in valinta_joukko]
        elif nappain in (ord("q"), 27):
            return None


def valitse_listasta(stdscr, otsikko: str, vaihtoehdot: list[str],
                     kiintea_otsikko: list[str] | None = None) -> int | None:
    """Nuolinäppäimillä valittava lista. Palauttaa valitun indeksin tai None (Esc/q).

    Sivuttaa pitkät listat näytön korkeuden mukaan ja rajaa rivit näytön
    leveyteen, jottei addstr kirjoita ruudun ulkopuolelle (curses ERR).

    kiintea_otsikko: rivit (esim. taulukon sarakeotsikko + erotinviiva), jotka
    piirretään listan yläpuolelle ja pysyvät näkyvissä myös vieritettäessä.
    """
    valittu = 0
    n = len(vaihtoehdot)
    otsikkorivit = kiintea_otsikko or []
    while True:
        piirra_otsikko(stdscr, otsikko)
        korkeus, leveys = stdscr.getmaxyx()
        for j, rivi in enumerate(otsikkorivit):
            if 3 + j < korkeus:
                stdscr.addstr(3 + j, 0, rivi[:leveys - 1])
        alku_rivi = 3 + len(otsikkorivit)
        if not vaihtoehdot:
            stdscr.addstr(alku_rivi, 0, "(ei kohteita)")

        # Vieritysnäkymä: kuinka monta riviä mahtuu (ohje + reunavara varattu)
        nakyvat = max(1, korkeus - alku_rivi - 2)
        if n > nakyvat:
            offset = min(max(0, valittu - nakyvat // 2), n - nakyvat)
        else:
            offset = 0
        loppu = min(offset + nakyvat, n)

        for rivi_idx, i in enumerate(range(offset, loppu)):
            tyyli = curses.A_REVERSE if i == valittu else curses.A_NORMAL
            stdscr.addstr(alku_rivi + rivi_idx, 0, vaihtoehdot[i][:leveys - 1], tyyli)

        ohje = "↑/↓ liiku · Enter valitse · q takaisin"
        if n > nakyvat:
            ohje += f"   [{valittu + 1}/{n}]"
        ohje_rivi = min(alku_rivi + max(loppu - offset, 1), korkeus - 1)
        stdscr.addstr(ohje_rivi, 0, ohje[:leveys - 1])

        nappain = stdscr.getch()
        if nappain in (curses.KEY_UP, ord("k")):
            valittu = (valittu - 1) % max(n, 1)
        elif nappain in (curses.KEY_DOWN, ord("j")):
            valittu = (valittu + 1) % max(n, 1)
        elif nappain in (curses.KEY_ENTER, 10, 13):
            if vaihtoehdot:
                return valittu
        elif nappain in (ord("q"), 27):
            return None
