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
    leveys = stdscr.getmaxyx()[1]
    teksti = teksti[:leveys - 1]  # estä addstr-ylivuoto kapealla ruudulla
    stdscr.addstr(0, 0, teksti, curses.A_BOLD)
    stdscr.addstr(1, 0, "=" * len(teksti))


def nayta_viesti(stdscr, teksti: str, rivi: int = -1) -> None:
    """Näyttää viestin ja odottaa näppäinpainallusta."""
    if rivi < 0:
        rivi = stdscr.getmaxyx()[0] - 2
    stdscr.addstr(rivi, 0, teksti)
    stdscr.addstr(rivi + 1, 0, "Paina mitä tahansa näppäintä jatkaaksesi...")
    stdscr.getch()


def _sana_eteen(buffer: list[str], pos: int) -> int:
    """Seuraavan sanan loppu (Option-F / Option-oikea)."""
    n = len(buffer)
    while pos < n and not buffer[pos].isalnum():
        pos += 1
    while pos < n and buffer[pos].isalnum():
        pos += 1
    return pos


def _sana_taakse(buffer: list[str], pos: int) -> int:
    """Edellisen sanan alku (Option-B / Option-vasen)."""
    while pos > 0 and not buffer[pos - 1].isalnum():
        pos -= 1
    while pos > 0 and buffer[pos - 1].isalnum():
        pos -= 1
    return pos


def _option_suunta(merkit: str) -> int:
    """Option/Alt-näppäilystä luettu sekvenssi → sanasiirron suunta.

    +1 = eteenpäin, -1 = taaksepäin, 0 = ei tunnistettu. Kattaa eri terminaalit:
    ESC b / ESC f (Meta), ESC[1;3C/D ja ESC O C/D (CSI/SS3 + modifier)."""
    if not merkit:
        return 0
    if merkit.endswith(("C", "f", "F")):
        return 1
    if merkit.endswith(("D", "b", "B")):
        return -1
    return 0


_OPTION_OIKEA = (b"kRIT3", b"kRIT4", b"kRIT5", b"kRIT6", b"kRIT7")
_OPTION_VASEN = (b"kLFT3", b"kLFT4", b"kLFT5", b"kLFT6", b"kLFT7")


def _rivita(buffer: list[str], etuliite: int, leveys: int) -> list[int]:
    """Pehmeä rivitys: palauttaa kunkin näyttörivin alkavan merkki-indeksin.

    Ensimmäinen rivi alkaa sarakkeesta `etuliite` (kehotteen jälkeen), loput
    sarakkeesta 0. Rivitys tehdään sanarajoilla kun mahdollista, muuten kovasti.
    """
    n = len(buffer)
    alut = [0]
    rivin_alku = 0
    kapasiteetti = max(1, leveys - etuliite)
    i = 0
    while i < n:
        if i - rivin_alku >= kapasiteetti:
            # Yritä peräytyä viimeiseen välilyöntiin (sanaraja)
            katko = i
            j = i
            while j > rivin_alku and buffer[j - 1] != " ":
                j -= 1
            if j > rivin_alku:
                katko = j
            alut.append(katko)
            rivin_alku = katko
            kapasiteetti = max(1, leveys)
            i = katko
        else:
            i += 1
    return alut


def lue_teksti(stdscr, kehote: str, rivi: int, oletus: str = "") -> str:
    """Lukee tekstin pehmeällä rivityksellä (textarea-tyyli) ja readline-näppäimillä.

    Pitkä teksti rivittyy automaattisesti useammalle näyttöriville alkaen rivistä
    `rivi`; lyhyt teksti mahtuu yhdelle riville kuten ennen. Tuetut komennot:
      ← → / Ctrl-B/F          merkki kerrallaan (rivien yli)
      ↑ ↓                     näyttörivi ylös/alas (sama sarake)
      Ctrl-A / Ctrl-E         näyttörivin alkuun / loppuun
      Option-← → / Option-B/F sana taaksepäin / eteenpäin
      Backspace / Ctrl-H      poista edeltävä merkki
      Ctrl-D / Del            poista seuraava merkki
      Ctrl-K                  tyhjennä kursorista loppuun
      Ctrl-U                  tyhjennä koko teksti
      Ctrl-W                  poista edeltävä sana
      Enter                   hyväksy
    """
    korkeus, leveys = stdscr.getmaxyx()
    kehote_teksti = kehote + ": "
    etuliite = len(kehote_teksti)
    leveys = max(etuliite + 1, leveys)

    buffer: list[str] = list(oletus)
    pos = len(buffer)

    curses.noecho()
    curses.curs_set(1)

    def rivi_ja_sarake(p: int, alut: list[int]) -> tuple[int, int]:
        """Merkki-indeksi → (näyttörivi-indeksi, sarake ruudulla)."""
        r = 0
        for k in range(len(alut) - 1, -1, -1):
            if p >= alut[k]:
                r = k
                break
        sar = (etuliite if r == 0 else 0) + (p - alut[r])
        return r, sar

    def paivita() -> int:
        alut = _rivita(buffer, etuliite, leveys)
        nakyvat = max(1, korkeus - rivi - 1)
        kur_r, kur_s = rivi_ja_sarake(pos, alut)
        for nayttorivi in range(nakyvat):
            stdscr.move(rivi + nayttorivi, 0)
            stdscr.clrtoeol()
        for nayttorivi in range(min(len(alut), nakyvat)):
            a = alut[nayttorivi]
            loppu = alut[nayttorivi + 1] if nayttorivi + 1 < len(alut) else len(buffer)
            teksti = "".join(buffer[a:loppu])
            sar = etuliite if nayttorivi == 0 else 0
            try:
                if nayttorivi == 0:
                    stdscr.addstr(rivi, 0, kehote_teksti)
                stdscr.addstr(rivi + nayttorivi, sar, teksti[: leveys - sar])
            except curses.error:
                pass
        try:
            if kur_r < nakyvat:
                stdscr.move(rivi + kur_r, min(kur_s, leveys - 1))
        except curses.error:
            pass
        stdscr.refresh()
        return len(alut)

    paivita()

    def siirra_pystyyn(suunta: int) -> None:
        nonlocal pos
        alut = _rivita(buffer, etuliite, leveys)
        r, sar = rivi_ja_sarake(pos, alut)
        kohde = r + suunta
        if kohde < 0 or kohde >= len(alut):
            return
        a = alut[kohde]
        loppu = alut[kohde + 1] if kohde + 1 < len(alut) else len(buffer)
        sar_alku = etuliite if kohde == 0 else 0
        haluttu = max(0, sar - sar_alku)
        pos = min(a + haluttu, loppu)

    def rivin_rajat() -> tuple[int, int]:
        alut = _rivita(buffer, etuliite, leveys)
        r, _ = rivi_ja_sarake(pos, alut)
        a = alut[r]
        loppu = alut[r + 1] if r + 1 < len(alut) else len(buffer)
        return a, loppu

    while True:
        try:
            ch = stdscr.get_wch()
        except curses.error:
            continue

        if isinstance(ch, str):
            if ch in ("\n", "\r"):
                break
            elif ch == "\x01":                  # Ctrl-A: näyttörivin alkuun
                pos, _ = rivin_rajat()
            elif ch == "\x05":                  # Ctrl-E: näyttörivin loppuun
                _, pos = rivin_rajat()
            elif ch == "\x02":                  # Ctrl-B: merkki taaksepäin
                pos = max(0, pos - 1)
            elif ch == "\x06":                  # Ctrl-F: merkki eteenpäin
                pos = min(len(buffer), pos + 1)
            elif ch == "\x0b":                  # Ctrl-K: tyhjennä loppuun
                del buffer[pos:]
            elif ch == "\x15":                  # Ctrl-U: tyhjennä koko teksti
                del buffer[:]
                pos = 0
            elif ch == "\x17":                  # Ctrl-W: poista edeltävä sana
                end = pos
                pos = _sana_taakse(buffer, pos)
                del buffer[pos:end]
            elif ch in ("\x08", "\x7f"):        # Ctrl-H / BS
                if pos > 0:
                    del buffer[pos - 1]
                    pos -= 1
            elif ch == "\x04":                  # Ctrl-D: poista seuraava
                if pos < len(buffer):
                    del buffer[pos]
            elif ch == "\x1b":                  # ESC: Option/Alt-sekvenssi (ESC b, ESC[1;3C, …)
                seq = ""
                stdscr.timeout(60)
                try:
                    while len(seq) < 8:
                        try:
                            c = stdscr.get_wch()
                        except curses.error:
                            break
                        if isinstance(c, int):
                            break
                        seq += c
                finally:
                    stdscr.timeout(-1)
                suunta = _option_suunta(seq)
                if suunta > 0:
                    pos = _sana_eteen(buffer, pos)
                elif suunta < 0:
                    pos = _sana_taakse(buffer, pos)
            elif ch.isprintable():
                buffer.insert(pos, ch)
                pos += 1
        else:                                   # erikoisnäppäin
            try:
                nimi = curses.keyname(ch)
            except (ValueError, OverflowError, curses.error):
                nimi = b""
            if nimi in _OPTION_OIKEA:           # Option/Alt + oikea: sana eteen
                pos = _sana_eteen(buffer, pos)
            elif nimi in _OPTION_VASEN:         # Option/Alt + vasen: sana taakse
                pos = _sana_taakse(buffer, pos)
            elif ch in (curses.KEY_BACKSPACE, 127):
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
            elif ch == curses.KEY_UP:
                siirra_pystyyn(-1)
            elif ch == curses.KEY_DOWN:
                siirra_pystyyn(1)
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
