"""Korkeakoulujen hallintanäkymä: listaa, lisää, muokkaa ja poista."""
from tietokanta import mallit
from cliui.apurit import piirra_otsikko, nayta_viesti, lue_teksti, valitse_listasta

OPS_TYYPIT = ["Peppi", "Sisu"]


def nayta(stdscr) -> None:
    while True:
        valinta = valitse_listasta(
            stdscr,
            "Korkeakoulujen hallinta",
            ["Lisää korkeakoulu", "Muokkaa korkeakoulua", "Poista korkeakoulu", "Listaa korkeakoulut"],
        )
        if valinta is None:
            return
        if valinta == 0:
            _lisaa(stdscr)
        elif valinta == 1:
            _muokkaa(stdscr)
        elif valinta == 2:
            _poista(stdscr)
        elif valinta == 3:
            _listaa(stdscr)


def _valitse_korkeakoulu(stdscr, otsikko: str) -> dict | None:
    koulut = mallit.hae_korkeakoulut()
    if not koulut:
        piirra_otsikko(stdscr, otsikko)
        nayta_viesti(stdscr, "Ei korkeakouluja tietokannassa.")
        return None
    rivit = [f"{k['KouluNimi']} ({k['OpsTyyppi']})" for k in koulut]
    indeksi = valitse_listasta(stdscr, otsikko, rivit)
    return koulut[indeksi] if indeksi is not None else None


def _valitse_ops_tyyppi(stdscr, oletus: str = "") -> str | None:
    otsikko = "Valitse OPS-tyyppi"
    indeksi = valitse_listasta(stdscr, otsikko, OPS_TYYPIT)
    if indeksi is None:
        return oletus or None
    return OPS_TYYPIT[indeksi]


def _lisaa(stdscr) -> None:
    piirra_otsikko(stdscr, "Lisää korkeakoulu")
    nimi = lue_teksti(stdscr, "Koulun nimi", 3)
    if not nimi:
        nayta_viesti(stdscr, "Peruutettu (nimi pakollinen).")
        return
    osoite = lue_teksti(stdscr, "Opinto-oppaan osoite", 4)
    tyyppi = _valitse_ops_tyyppi(stdscr)
    if not tyyppi:
        nayta_viesti(stdscr, "Peruutettu (OPS-tyyppi pakollinen).")
        return
    mallit.lisaa_korkeakoulu(nimi, osoite, tyyppi)
    piirra_otsikko(stdscr, "Lisää korkeakoulu")
    nayta_viesti(stdscr, f"Lisätty: {nimi}")


def _muokkaa(stdscr) -> None:
    koulu = _valitse_korkeakoulu(stdscr, "Muokkaa korkeakoulua")
    if koulu is None:
        return
    piirra_otsikko(stdscr, f"Muokkaa: {koulu['KouluNimi']}")
    nimi = lue_teksti(stdscr, "Koulun nimi", 3, koulu["KouluNimi"])
    osoite = lue_teksti(stdscr, "Opinto-oppaan osoite", 4, koulu["OpsOsoite"])
    tyyppi = _valitse_ops_tyyppi(stdscr, koulu["OpsTyyppi"])
    mallit.paivita_korkeakoulu(koulu["KKID"], nimi, osoite, tyyppi)
    piirra_otsikko(stdscr, "Muokkaa korkeakoulua")
    nayta_viesti(stdscr, f"Päivitetty: {nimi}")


def _poista(stdscr) -> None:
    koulu = _valitse_korkeakoulu(stdscr, "Poista korkeakoulu")
    if koulu is None:
        return
    piirra_otsikko(stdscr, "Poista korkeakoulu")
    vahvistus = lue_teksti(stdscr, f"Poistetaanko '{koulu['KouluNimi']}'? (kyllä/ei)", 3)
    if vahvistus.lower() in ("kyllä", "k", "kylla"):
        mallit.poista_korkeakoulu(koulu["KKID"])
        nayta_viesti(stdscr, "Poistettu.")
    else:
        nayta_viesti(stdscr, "Peruutettu.")


def _listaa(stdscr) -> None:
    koulut = mallit.hae_korkeakoulut()
    piirra_otsikko(stdscr, "Korkeakoulut")
    if not koulut:
        nayta_viesti(stdscr, "Ei korkeakouluja tietokannassa.")
        return
    for i, k in enumerate(koulut):
        stdscr.addstr(3 + i, 0, f"{k['KouluNimi']} · {k['OpsTyyppi']} · {k['OpsOsoite']}")
    nayta_viesti(stdscr, "")
