"""Tutkimuksen tarkentavien kysymysten hallinta."""
from tietokanta import mallit
from cliui.apurit import piirra_otsikko, nayta_viesti, lue_teksti, valitse_listasta

_KATKAISU = 55


def _lyhenna(teksti: str) -> str:
    return teksti[:_KATKAISU] + "…" if len(teksti) > _KATKAISU else teksti


def nayta(stdscr, tutkimus: dict) -> None:
    """Hallinnoi yhden tutkimuksen tarkentavia kysymyksiä."""
    otsikko_pohja = f"Kysymykset — {tutkimus['LuokittelunNimi']}"
    while True:
        kysymykset = mallit.hae_kysymykset(tutkimus["TID"])
        vaihtoehdot = ["[+] Lisää uusi kysymys"] + [
            f"{i}. {_lyhenna(k['Kysymys'])}" for i, k in enumerate(kysymykset, 1)
        ]
        valinta = valitse_listasta(stdscr, otsikko_pohja, vaihtoehdot)
        if valinta is None:
            return
        if valinta == 0:
            _lisaa(stdscr, tutkimus["TID"])
        else:
            _muokkaa_tai_poista(stdscr, kysymykset[valinta - 1])


def _lisaa(stdscr, tid: int) -> None:
    piirra_otsikko(stdscr, "Lisää kysymys")
    teksti = lue_teksti(stdscr, "Kysymys", 3)
    if not teksti:
        nayta_viesti(stdscr, "Peruutettu (kysymys ei voi olla tyhjä).")
        return
    mallit.lisaa_kysymys(tid, teksti)
    piirra_otsikko(stdscr, "Lisää kysymys")
    nayta_viesti(stdscr, "Kysymys lisätty.")


def _muokkaa_tai_poista(stdscr, kysymys: dict) -> None:
    valinta = valitse_listasta(
        stdscr,
        _lyhenna(kysymys["Kysymys"]),
        ["Muokkaa", "Poista"],
    )
    if valinta is None:
        return
    if valinta == 0:
        _muokkaa(stdscr, kysymys)
    else:
        _poista(stdscr, kysymys)


def _muokkaa(stdscr, kysymys: dict) -> None:
    piirra_otsikko(stdscr, "Muokkaa kysymystä")
    teksti = lue_teksti(stdscr, "Kysymys", 3, kysymys["Kysymys"])
    if not teksti:
        nayta_viesti(stdscr, "Peruutettu (kysymys ei voi olla tyhjä).")
        return
    mallit.paivita_kysymys(kysymys["KysID"], teksti)
    piirra_otsikko(stdscr, "Muokkaa kysymystä")
    nayta_viesti(stdscr, "Päivitetty.")


def _poista(stdscr, kysymys: dict) -> None:
    piirra_otsikko(stdscr, "Poista kysymys")
    stdscr.addstr(3, 0, _lyhenna(kysymys["Kysymys"]))
    vahvistus = lue_teksti(stdscr, "Poistetaanko? (kyllä/ei)", 5)
    if vahvistus.lower() in ("kyllä", "k", "kylla"):
        mallit.poista_kysymys(kysymys["KysID"])
        nayta_viesti(stdscr, "Poistettu.")
    else:
        nayta_viesti(stdscr, "Peruutettu.")
