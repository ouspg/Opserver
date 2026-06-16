"""Arviointinäkymä: LLM-arviointi mukaan otetuille kursseille."""
from tietokanta import mallit
from cliui.apurit import piirra_otsikko, nayta_viesti, valitse_listasta


def nayta(stdscr) -> None:
    tutkimukset = mallit.hae_tutkimukset()
    if not tutkimukset:
        piirra_otsikko(stdscr, "Arvioi")
        nayta_viesti(stdscr, "Ei tutkimuksia — lisää ensin tutkimus (valikko 3).")
        return
    rivit = [f"{t['LuokittelunNimi']} ({t['Slug']})" for t in tutkimukset]
    indeksi = valitse_listasta(stdscr, "Arvioi — valitse tutkimus", rivit)
    if indeksi is None:
        return
    _arvioi(stdscr, tutkimukset[indeksi])


def _arvioi(stdscr, tutkimus: dict) -> None:
    while True:
        valinta = valitse_listasta(
            stdscr,
            f"Arvioi — {tutkimus['LuokittelunNimi']}",
            ["Aja LLM-arviointi", "Näytä tilanne"],
        )
        if valinta is None:
            return
        if valinta == 0:
            _aja_llm(stdscr, tutkimus)
        elif valinta == 1:
            _nayta_tilanne(stdscr, tutkimus)


def _aja_llm(stdscr, tutkimus: dict) -> None:
    from arviointi import llmarviointi
    piirra_otsikko(stdscr, f"LLM-arviointi — {tutkimus['LuokittelunNimi']}")

    odottavat = mallit.hae_arvioimattomat(tutkimus["TID"])
    if not odottavat:
        nayta_viesti(stdscr, "Kaikki mukana olevat kurssit on jo arvioitu. Katso tilanne-näkymästä.")
        return

    stdscr.addstr(3, 0, "Yhdistetään LLM:ään...")
    stdscr.refresh()

    _odottaa = [True]

    def edistyminen(n, yht, erä, erat):
        if _odottaa[0]:
            stdscr.addstr(4, 0, f"  Erä {erä}/{erat} — lähettää... ({n}/{yht} käsitelty)  ")
        else:
            stdscr.addstr(4, 0, f"  Erä {erä}/{erat} — {n}/{yht} käsitelty               ")
        _odottaa[0] = not _odottaa[0]
        stdscr.refresh()

    try:
        arvioitu = llmarviointi.aja(tutkimus, edistyminen)
        piirra_otsikko(stdscr, "LLM-arviointi — valmis")
        stdscr.addstr(3, 0, f"Arvioitu: {arvioitu}")
        nayta_viesti(stdscr, "", 5)
    except EnvironmentError as e:
        nayta_viesti(stdscr, f"Virhe: {e}")
    except Exception as e:
        nayta_viesti(stdscr, f"LLM-virhe: {e}")


def _nayta_tilanne(stdscr, tutkimus: dict) -> None:
    tid = tutkimus["TID"]
    mukana_kurssit = mallit.hae_luokitukset(tid, mukana=True)
    arvioimattomat = mallit.hae_arvioimattomat(tid)
    mukana_lkm = len(mukana_kurssit)
    arvioitu_lkm = mukana_lkm - len(arvioimattomat)

    piirra_otsikko(stdscr, f"Tilanne — {tutkimus['LuokittelunNimi']}")
    stdscr.addstr(3, 0, f"Mukaan otettuja kursseja: {mukana_lkm}")
    stdscr.addstr(4, 0, f"Arvioitu:                 {arvioitu_lkm}")
    stdscr.addstr(5, 0, f"Odottaa arviointia:       {len(arvioimattomat)}")
    nayta_viesti(stdscr, "", 7)
