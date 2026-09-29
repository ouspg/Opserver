"""Korkeakoulujen hallintanäkymä: listaa, lisää, muokkaa ja poista."""
from tietokanta import mallit
from tiedonhaku import konfiguraatio
from cliui.apurit import piirra_otsikko, nayta_viesti, lue_teksti, valitse_listasta
from cliui.valikot import toimintovalikko, valitse_korkeakoulu, vahvista_kylla

OPS_TYYPIT = ["Peppi", "Sisu"]


def _selvita_ja_vahvista(stdscr, osoite: str, tyyppi: str) -> str | None:
    """Selvittää API-osoitteen opinto-opasjärjestelmästä ja näyttää sen vahvistettavaksi.

    Palauttaa hyväksytyn API-osoitteen, tai None jos selvitys epäonnistui tai
    operaattori perui.
    """
    piirra_otsikko(stdscr, "Selvitetään API-osoitetta")
    stdscr.addstr(3, 0, f"Yhdistetään {osoite} ...")
    stdscr.refresh()
    try:
        api = konfiguraatio.selvita_konfiguraatio(osoite, tyyppi)["api_osoite"]
    except Exception as e:
        nayta_viesti(stdscr, f"API-osoitteen selvitys epäonnistui: {e}")
        return None
    piirra_otsikko(stdscr, "Vahvista API-osoite")
    stdscr.addstr(3, 0, f"Löydetty API-osoite: {api}")
    return api if vahvista_kylla(stdscr, "Tallennetaanko tämä?", 5, "kyllä") else None


def nayta(stdscr) -> None:
    toimintovalikko(stdscr, "Korkeakoulujen hallinta", [
        ("Lisää korkeakoulu", _lisaa),
        ("Muokkaa korkeakoulua", _muokkaa),
        ("Poista korkeakoulu", _poista),
        ("Listaa korkeakoulut", _listaa),
    ])


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
    api = _selvita_ja_vahvista(stdscr, osoite, tyyppi)
    if api is None:
        nayta_viesti(stdscr, "Peruutettu (API-osoitetta ei vahvistettu).")
        return
    mallit.lisaa_korkeakoulu(nimi, osoite, tyyppi, api_osoite=api)
    piirra_otsikko(stdscr, "Lisää korkeakoulu")
    nayta_viesti(stdscr, f"Lisätty: {nimi} · API {api}")


def _muokkaa(stdscr) -> None:
    koulu = valitse_korkeakoulu(stdscr, "Muokkaa korkeakoulua")
    if koulu is None:
        return
    piirra_otsikko(stdscr, f"Muokkaa: {koulu['KouluNimi']}")
    nimi = lue_teksti(stdscr, "Koulun nimi", 3, koulu["KouluNimi"])
    osoite = lue_teksti(stdscr, "Opinto-oppaan osoite", 4, koulu["OpsOsoite"])
    tyyppi = _valitse_ops_tyyppi(stdscr, koulu["OpsTyyppi"])
    # Selvitä API-osoite uudelleen (osoite/tyyppi voi muuttua); säilytä vanha jos peruttiin.
    api = _selvita_ja_vahvista(stdscr, osoite, tyyppi) or koulu.get("ApiOsoite")
    mallit.paivita_korkeakoulu(koulu["KKID"], nimi, osoite, tyyppi, api_osoite=api)
    piirra_otsikko(stdscr, "Muokkaa korkeakoulua")
    nayta_viesti(stdscr, f"Päivitetty: {nimi} · API {api}")


def _poista(stdscr) -> None:
    koulu = valitse_korkeakoulu(stdscr, "Poista korkeakoulu")
    if koulu is None:
        return
    piirra_otsikko(stdscr, "Poista korkeakoulu")
    if vahvista_kylla(stdscr, f"Poistetaanko '{koulu['KouluNimi']}'?", 3):
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
        api = k.get("ApiOsoite") or "(API selvittämättä)"
        stdscr.addstr(3 + i, 0, f"{k['KouluNimi']} · {k['OpsTyyppi']} · {k['OpsOsoite']} · API: {api}")
    nayta_viesti(stdscr, "")
