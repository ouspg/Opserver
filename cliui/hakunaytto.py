"""Kurssien hakeminen opinto-oppaista — CLIUI-näkymä."""
from tietokanta import mallit
from cliui.apurit import piirra_otsikko, nayta_viesti, valitse_listasta


def _tee_lukija(koulu: dict):
    if koulu["OpsTyyppi"] == "Peppi":
        from tiedonhaku.peppilukija import PeppiLukija
        return PeppiLukija(koulu)
    if koulu["OpsTyyppi"] == "Sisu":
        from tiedonhaku.sisulukija import SisuLukija
        return SisuLukija(koulu)
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

    def paivita_tila(viesti: str) -> None:
        stdscr.addstr(4, 0, f"  {viesti}")
        stdscr.clrtoeol()
        stdscr.addstr(5, 0, "")
        stdscr.clrtoeol()
        stdscr.refresh()

    def paivita_edistyminen(n: int, yhteensa: int, kurssi_nimi: str = "") -> None:
        stdscr.addstr(4, 0, f"  Vaihe 2/2: tallennetaan kurssitietoja...  {n}/{yhteensa} kurssia")
        stdscr.clrtoeol()
        stdscr.addstr(5, 0, f"  {kurssi_nimi}")
        stdscr.clrtoeol()
        stdscr.refresh()

    tallennettu, ohitettu = lukija.hae_kurssit(
        kausi, edistyminen_cb=paivita_edistyminen, tila_cb=paivita_tila
    )

    piirra_otsikko(stdscr, "Hae kurssit — valmis")
    viesti = f"Tallennettu {tallennettu} uutta kurssia ({koulu['KouluNimi']}, {kausi})."
    if ohitettu:
        viesti += f" Ohitettu {ohitettu} (verkkovirhe)."
    nayta_viesti(stdscr, viesti)
