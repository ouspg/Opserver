"""Näkymien yhteiset valikot: toimintovalikko, tutkimuksen/korkeakoulun valinta, vahvistus."""
from tietokanta import mallit
from cliui.apurit import piirra_otsikko, nayta_viesti, valitse_listasta
from cliui.tekstikentta import lue_teksti


def toimintovalikko(stdscr, otsikko, toiminnot: list[tuple], *argumentit) -> None:
    """Toistuva valikko [(nimi, fn)]: valinta kutsuu fn(stdscr, *argumentit), Esc palaa.
    otsikko voi olla funktio, jolloin se lasketaan joka kierroksella uudelleen."""
    while True:
        valinta = valitse_listasta(stdscr, otsikko() if callable(otsikko) else otsikko,
                                   [nimi for nimi, _ in toiminnot])
        if valinta is None:
            return
        toiminnot[valinta][1](stdscr, *argumentit)


def _valitse(stdscr, otsikko: str, rivit: list, rivi, tyhja_viesti: str) -> dict | None:
    if not rivit:
        piirra_otsikko(stdscr, otsikko)
        nayta_viesti(stdscr, tyhja_viesti)
        return None
    indeksi = valitse_listasta(stdscr, otsikko, [rivi(r) for r in rivit])
    return rivit[indeksi] if indeksi is not None else None


def valitse_tutkimus(stdscr, otsikko: str) -> dict | None:
    return _valitse(stdscr, otsikko, mallit.hae_tutkimukset(),
                    lambda t: f"{t['LuokittelunNimi']} ({t['Slug']})",
                    "Ei tutkimuksia — lisää ensin tutkimus (valikko 3).")


def valitse_korkeakoulu(stdscr, otsikko: str) -> dict | None:
    return _valitse(stdscr, otsikko, mallit.hae_korkeakoulut(),
                    lambda k: f"{k['KouluNimi']} ({k['OpsTyyppi']})",
                    "Ei korkeakouluja — lisää ensin korkeakoulu (valikko 1).")


def vahvista_kylla(stdscr, kysymys: str, rivi: int, oletus: str = "") -> bool:
    """Kirjoitettava vahvistus (kyllä/ei) — tahallinen kitka poistoille."""
    return lue_teksti(stdscr, f"{kysymys} (kyllä/ei)", rivi, oletus).strip().lower() in ("kyllä", "k", "kylla")
