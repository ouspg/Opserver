"""Kurssien hakeminen opinto-oppaista — CLIUI-näkymä."""
from tietokanta import mallit
from tiedonhaku.peppilukija import PeppiLukija
from cliui.apurit import piirra_otsikko, nayta_viesti, valitse_listasta


def _tee_lukija(koulu: dict):
    if koulu["OpsTyyppi"] == "Peppi":
        return PeppiLukija(koulu)
    return None


def nayta(stdscr) -> None:
    koulut = mallit.hae_korkeakoulut()
    if not koulut:
        piirra_otsikko(stdscr, "Hae kurssit")
        nayta_viesti(stdscr, "Ei korkeakouluja. Lisää ensin korkeakoulu valikkokohdasta 1.")
        return

    rivit = [f"{k['KouluNimi']} ({k['OpsTyyppi']})" for k in koulut]
    indeksi = valitse_listasta(stdscr, "Hae kurssit — valitse korkeakoulu", rivit)
    if indeksi is None:
        return
    koulu = koulut[indeksi]

    lukija = _tee_lukija(koulu)
    if lukija is None:
        piirra_otsikko(stdscr, "Hae kurssit")
        nayta_viesti(stdscr, f"OPS-tyyppiä '{koulu['OpsTyyppi']}' ei tueta vielä.")
        return

    piirra_otsikko(stdscr, f"Hae kurssit — {koulu['KouluNimi']}")
    stdscr.addstr(3, 0, "Etsitään saatavilla olevia OPS-kausia...")
    stdscr.refresh()

    kaudet = lukija.hae_saatavilla_kaudet()
    if not kaudet:
        nayta_viesti(stdscr, "Ei löytynyt saatavilla olevia OPS-kausia.")
        return

    kausi_indeksi = valitse_listasta(stdscr, "Valitse OPS-kausi", kaudet)
    if kausi_indeksi is None:
        return
    kausi = kaudet[kausi_indeksi]

    piirra_otsikko(stdscr, f"Haetaan — {koulu['KouluNimi']} {kausi}")
    stdscr.addstr(3, 0, "Haetaan kursseja... (tämä voi kestää useita minuutteja)")
    stdscr.refresh()

    def paivita_edistyminen(n: int, yhteensa: int) -> None:
        stdscr.addstr(4, 0, f"  {n}/{yhteensa} kurssia tallennettu")
        stdscr.refresh()

    maara = lukija.hae_kurssit(kausi, edistyminen_cb=paivita_edistyminen)

    piirra_otsikko(stdscr, "Hae kurssit — valmis")
    nayta_viesti(stdscr, f"Tallennettu {maara} kurssia ({koulu['KouluNimi']}, {kausi}).")
