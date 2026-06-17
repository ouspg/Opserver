"""Luokittelunäkymä: meta-suodatus ja LLM-luokittelu."""
from tietokanta import mallit
from cliui.apurit import piirra_otsikko, nayta_viesti, valitse_listasta


def nayta(stdscr) -> None:
    tutkimukset = mallit.hae_tutkimukset()
    if not tutkimukset:
        piirra_otsikko(stdscr, "Luokittele")
        nayta_viesti(stdscr, "Ei tutkimuksia — lisää ensin tutkimus (valikko 3).")
        return
    rivit = [f"{t['LuokittelunNimi']} ({t['Slug']})" for t in tutkimukset]
    indeksi = valitse_listasta(stdscr, "Luokittele — valitse tutkimus", rivit)
    if indeksi is None:
        return
    _luokittele(stdscr, tutkimukset[indeksi])


def _luokittele(stdscr, tutkimus: dict) -> None:
    while True:
        valinta = valitse_listasta(
            stdscr,
            f"Luokittele — {tutkimus['LuokittelunNimi']}",
            ["Aja meta-suodatus", "Aja LLM-luokittelu", "Näytä tilanne"],
        )
        if valinta is None:
            return
        if valinta == 0:
            _aja_meta(stdscr, tutkimus)
        elif valinta == 1:
            _aja_llm(stdscr, tutkimus)
        elif valinta == 2:
            _nayta_tilanne(stdscr, tutkimus)


def _aja_meta(stdscr, tutkimus: dict) -> None:
    from luokittelu import metasuodatus

    nollaa = False
    luokiteltu_lkm = len(mallit.hae_luokitukset(tutkimus["TID"]))
    if luokiteltu_lkm > 0:
        valinta = valitse_listasta(
            stdscr,
            f"Meta-suodatus — {tutkimus['LuokittelunNimi']}",
            [
                f"Ohita jo suodatetut ({luokiteltu_lkm} kpl) — käsittele vain uudet kurssit",
                "Alusta kaikki uudelleen — korvaa kaikki olemassaolevat luokittelut",
            ],
        )
        if valinta is None:
            return
        nollaa = valinta == 1

    piirra_otsikko(stdscr, f"Meta-suodatus — {tutkimus['LuokittelunNimi']}")
    stdscr.addstr(3, 0, "Suodatetaan...")
    stdscr.refresh()

    def edistyminen(n, yht, hyvaksytty):
        stdscr.addstr(4, 0, f"  {n}/{yht} kurssia  |  hyväksytty: {hyvaksytty}")
        stdscr.refresh()

    try:
        lapaisseet, yhteensa = metasuodatus.aja(tutkimus, edistyminen, nollaa=nollaa)
    except ValueError as virhe:
        piirra_otsikko(stdscr, "Meta-suodatus — keskeytyi")
        nayta_viesti(stdscr, str(virhe), 3)
        return
    piirra_otsikko(stdscr, "Meta-suodatus — valmis")
    stdscr.addstr(3, 0, f"Läpäisi:  {lapaisseet}")
    stdscr.addstr(4, 0, f"Hylätty:  {yhteensa - lapaisseet}")
    stdscr.addstr(5, 0, f"Yhteensä: {yhteensa}")
    nayta_viesti(stdscr, "", 7)


def _aja_llm(stdscr, tutkimus: dict) -> None:
    from luokittelu import llmluokittelu
    from llm import mallitiedot
    piirra_otsikko(stdscr, f"LLM-luokittelu — {tutkimus['LuokittelunNimi']}")

    tid = tutkimus["TID"]
    tiiv = llmluokittelu.laske_tiiviste(tutkimus)
    uudet = len(mallit.hae_luokittelemattomat(tid))            # ei vielä LLM-luokiteltu
    kaikki = len(mallit.hae_luokittelemattomat(tid, tiiv))     # + vanhentuneen kehotteen tulokset
    vanhentuneet = kaikki - uudet

    if kaikki == 0:
        nayta_viesti(stdscr, "Kaikki kurssit on jo luokiteltu nykyisellä kehotteella.")
        return

    # Varoita kustannusvaikutuksesta, jos kehotteen muutos pakottaa uudelleenajon
    if vanhentuneet > 0:
        valinta = valitse_listasta(
            stdscr,
            "LLM-luokittelu — kehote on muuttunut",
            [
                f"Aja LLM: {uudet} uutta + {vanhentuneet} uudelleen (kehote muuttui) — LLM-kuluja",
                "Peruuta",
            ],
        )
        if valinta != 0:
            return

    # Esitarkistus: malli on saatavilla ennen kuin aloitetaan LLM-kutsut
    try:
        mallitiedot.tarkista_saatavuus()
    except Exception as e:
        nayta_viesti(stdscr, f"Mallia ei voi käyttää: {e}")
        return

    stdscr.addstr(3, 0, "Yhdistetään LLM:ään...")
    stdscr.refresh()

    def edistyminen(n, yht, erä, erat):
        stdscr.addstr(4, 0, f"  Erä {erä}/{erat} — {n}/{yht} kurssia käsitelty")
        stdscr.refresh()

    try:
        mukana, hylätty = llmluokittelu.aja(tutkimus, edistyminen)
        piirra_otsikko(stdscr, "LLM-luokittelu — valmis")
        stdscr.addstr(3, 0, f"Mukaan otettu: {mukana}")
        stdscr.addstr(4, 0, f"Hylätty:       {hylätty}")
        nayta_viesti(stdscr, "", 6)
    except EnvironmentError as e:
        nayta_viesti(stdscr, f"Virhe: {e}")
    except Exception as e:
        nayta_viesti(stdscr, f"LLM-virhe: {e}")


def _nayta_tilanne(stdscr, tutkimus: dict) -> None:
    tid = tutkimus["TID"]
    luokitukset = mallit.hae_luokitukset(tid)
    kurssit_yht = len(mallit.hae_kurssit())
    mukana = sum(1 for l in luokitukset if l.get("Mukana") == 1)
    hylätty = sum(1 for l in luokitukset if l.get("Mukana") == 0)
    odottaa = kurssit_yht - len(luokitukset)
    arvioimattomat = len(mallit.hae_arvioimattomat(tid))
    arvioitu = mukana - arvioimattomat

    piirra_otsikko(stdscr, f"Tilanne — {tutkimus['LuokittelunNimi']}")
    stdscr.addstr(3, 0, f"Kursseja yhteensä:  {kurssit_yht}")
    stdscr.addstr(4, 0, f"Mukana (LLM):       {mukana}")
    stdscr.addstr(5, 0, f"Hylätty:            {hylätty}")
    stdscr.addstr(6, 0, f"Odottaa käsittelyä: {odottaa}")
    stdscr.addstr(7, 0, f"")
    stdscr.addstr(8, 0, f"LLM-arvioitu:       {arvioitu} / {mukana}")
    stdscr.addstr(9, 0, f"Odottaa arviointia: {arvioimattomat}")
    nayta_viesti(stdscr, "", 11)
