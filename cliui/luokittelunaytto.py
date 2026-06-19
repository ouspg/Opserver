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

    kohteet = ["uudet", "kaikki", "hylatyt", "hyvaksytyt"]
    valinta = valitse_listasta(
        stdscr,
        f"Meta-suodatus — {tutkimus['LuokittelunNimi']}",
        [
            "Uudet — vain vielä luokittelemattomat kurssit",
            "Kaikki — luokittele kaikki uudelleen (korvaa myös LLM-päätökset)",
            "Hylätyt — luokittele meta-hylätyt uudelleen (esim. lisätty oppiaine)",
            "Hyväksytyt — luokittele meta-läpäisseet uudelleen (esim. poistettu oppiaine)",
        ],
    )
    if valinta is None:
        return
    kohde = kohteet[valinta]

    piirra_otsikko(stdscr, f"Meta-suodatus — {tutkimus['LuokittelunNimi']}")
    stdscr.addstr(3, 0, "Suodatetaan...")
    stdscr.refresh()

    def edistyminen(n, yht, hyvaksytty):
        stdscr.addstr(4, 0, f"  {n}/{yht} kurssia  |  hyväksytty: {hyvaksytty}")
        stdscr.refresh()

    try:
        lapaisseet, yhteensa = metasuodatus.aja(tutkimus, edistyminen, kohde=kohde)
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
    t = mallit.hae_tutkimuksen_tilanne(tid)
    arvioimattomat = len(mallit.hae_arvioimattomat(tid))
    arvioitu = t["hyvaksytty"] - arvioimattomat

    piirra_otsikko(stdscr, f"Tilanne — {tutkimus['LuokittelunNimi']}")
    korkeus, leveys = stdscr.getmaxyx()

    def rivi(nro: int, label: str, arvo, lisa: str = "") -> None:
        if 3 + nro < korkeus - 2:
            teksti = f"{label:<28}: {arvo}{lisa}"
            stdscr.addstr(3 + nro, 0, teksti[:leveys - 1])

    # Suppilo: vuosi- ja oppilaitosrajaus karsivat ehdokasjoukon,
    # meta- ja LLM-luokitus jakavat loput.
    rivi(0, "Kursseja yhteensä", t["kursseja_yht"])
    rivi(1, "Kursseja (vuosirajaus)", t["vuosi_lapi"], f"   ({t['vuosi_hyl']} hylätty)")
    rivi(2, "Kursseja (oppilaitosrajaus)", t["oppilaitos_lapi"], f"   ({t['oppilaitos_hyl']} hylätty)")
    rivi(3, "Odottaa metaluokitusta", t["odottaa_meta"])
    rivi(4, "Hylätty metaluokituksella", t["hyl_meta"])
    rivi(5, "Odottaa LLM-luokitusta", t["odottaa_llm"])
    rivi(6, "Hylätty LLM-luokituksella", t["hyl_llm"])
    rivi(7, "Hyväksytty tutkimukseen", t["hyvaksytty"])
    # Vaihe 3 (arviointi) hyväksytyille
    rivi(9, "LLM-arvioitu", f"{arvioitu} / {t['hyvaksytty']}")
    rivi(10, "Odottaa arviointia", arvioimattomat)
    nayta_viesti(stdscr, "")
