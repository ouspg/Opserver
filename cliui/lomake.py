"""Monikenttäinen lomake (muokkaa_lomake): kaikki kentät näkyvissä, iso tekstikenttä
avautuu rivittyvänä editorina (cliui.tekstikentta)."""
import curses

from cliui.apurit import piirra_otsikko
from cliui.tekstikentta import lue_teksti


def _lomake_label_attr(valittu: bool):
    attr = curses.color_pair(2) | curses.A_BOLD
    return attr | curses.A_REVERSE if valittu else attr


def muokkaa_lomake(stdscr, otsikko: str, kentat: list[dict]):
    """Lomake-editori: kaikki kentät näkyvissä yhtä aikaa.

    ↑/↓ valitsee kentän, Enter muokkaa valittua (iso tekstikenttä avautuu
    rivittyvänä editorina), 'Tallenna' tallentaa, q/Esc peruuttaa.

    kentat: list[dict] avaimin:
      avain (str), otsikko (str), arvo (mikä tahansa),
      muokkain  fn(stdscr, arvo, kaikki_arvot) -> uusi | None   (oletus: tekstieditori)
      esikatselu fn(arvo) -> str                                 (oletus: str)
      validoi    fn(arvo) -> virheviesti | None                  (valinnainen)
    Palauttaa {avain: arvo} tallennettaessa, None peruttaessa.
    """
    n = len(kentat)
    valittu = 0
    scroll = 0
    virhe = ""

    def kaikki_arvot():
        return {k["avain"]: k["arvo"] for k in kentat}

    def esikatselu_teksti(k):
        fn = k.get("esikatselu") or (lambda v: "" if v is None else str(v))
        return fn(k["arvo"]).replace("\n", " ").strip()

    while True:
        piirra_otsikko(stdscr, otsikko)
        korkeus, leveys = stdscr.getmaxyx()
        rivit = []  # (tyyppi, kentta_indeksi)
        for i in range(n):
            rivit.append(("otsikko", i))
            rivit.append(("arvo", i))
        rivit.append(("tallenna", n))

        kaytettavissa = max(1, korkeus - 4)  # otsikko (0-1), virhe + apurivi alas
        sel_rivi = valittu * 2 if valittu < n else n * 2
        if sel_rivi < scroll:
            scroll = sel_rivi
        elif sel_rivi >= scroll + kaytettavissa:
            scroll = sel_rivi - kaytettavissa + 1

        for nayttorivi, ri in enumerate(range(scroll, min(scroll + kaytettavissa, len(rivit)))):
            y = 3 + nayttorivi
            tyyppi, i = rivit[ri]
            if tyyppi == "otsikko":
                merkki = "▸ " if i == valittu else "  "
                try:
                    stdscr.addstr(y, 0, f"{merkki}{kentat[i]['otsikko']}:"[:leveys - 1],
                                  _lomake_label_attr(i == valittu))
                except curses.error:
                    pass
            elif tyyppi == "arvo":
                teksti = "       " + (esikatselu_teksti(kentat[i]) or "—")
                try:
                    stdscr.addstr(y, 0, teksti[:leveys - 1])
                except curses.error:
                    pass
            else:  # tallenna
                merkki = "▸ " if valittu == n else "  "
                attr = curses.A_REVERSE if valittu == n else curses.A_NORMAL
                try:
                    stdscr.addstr(y, 0, f"{merkki}[ Tallenna ]", attr)
                except curses.error:
                    pass

        if virhe:
            try:
                stdscr.addstr(korkeus - 2, 0, virhe[:leveys - 1], curses.A_BOLD)
            except curses.error:
                pass
        try:
            stdscr.addstr(korkeus - 1, 0,
                          "↑/↓ liiku · Enter muokkaa/tallenna · q peruuta"[:leveys - 1])
        except curses.error:
            pass
        stdscr.refresh()

        nappain = stdscr.getch()
        if nappain in (curses.KEY_UP, ord("k")):
            valittu = (valittu - 1) % (n + 1)
            virhe = ""
        elif nappain in (curses.KEY_DOWN, ord("j")):
            valittu = (valittu + 1) % (n + 1)
            virhe = ""
        elif nappain in (curses.KEY_ENTER, 10, 13):
            if valittu == n:  # Tallenna
                virhe = ""
                for k in kentat:
                    tark = k.get("validoi")
                    if tark:
                        v = tark(k["arvo"])
                        if v:
                            virhe = v
                            break
                if not virhe:
                    return kaikki_arvot()
            else:
                k = kentat[valittu]
                muokkain = k.get("muokkain")
                if muokkain:
                    uusi = muokkain(stdscr, k["arvo"], kaikki_arvot())
                else:
                    piirra_otsikko(stdscr, k["otsikko"])
                    uusi = lue_teksti(stdscr, k["otsikko"], 3, k["arvo"] or "")
                if uusi is not None:
                    k["arvo"] = uusi
                virhe = ""
        elif nappain in (ord("q"), 27):
            return None
