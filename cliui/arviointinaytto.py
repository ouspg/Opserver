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
            [
                "Aja LLM-arviointi (kaikki arvioimattomat)",
                "Aja LLM-arviointi (vain yksi eräpyyntö)",
                "Näytä tilanne",
            ],
        )
        if valinta is None:
            return
        if valinta == 0:
            _aja_llm(stdscr, tutkimus)
        elif valinta == 1:
            _aja_llm(stdscr, tutkimus, vain_yksi_era=True)
        elif valinta == 2:
            _nayta_tilanne(stdscr, tutkimus)


def _aja_llm(stdscr, tutkimus: dict, vain_yksi_era: bool = False) -> None:
    from arviointi import llmarviointi
    from llm import mallitiedot
    otsikko = "LLM-arviointi (yksi erä)" if vain_yksi_era else "LLM-arviointi"
    piirra_otsikko(stdscr, f"{otsikko} — {tutkimus['LuokittelunNimi']}")

    uudet, vanhentuneet = llmarviointi.laske_tyomaara(tutkimus)
    if uudet + vanhentuneet == 0:
        nayta_viesti(stdscr, "Kaikki mukana olevat kurssit on jo arvioitu nykyisellä kehotteella ja kysymyksillä.")
        return

    # Yhden erän testiajo: ohitetaan kustannusvaroitus (yksi pyyntö on tarkoituksellisen pieni).
    # Täysajossa varoitetaan, jos kehote/kysymys on muuttunut (uudelleenajo maksaa).
    if not vain_yksi_era and vanhentuneet > 0:
        valinta = valitse_listasta(
            stdscr,
            "LLM-arviointi — kehote tai kysymys on muuttunut",
            [
                f"Aja LLM: {uudet} uutta + {vanhentuneet} uudelleen (muutos) — vain muuttuneet kysymykset",
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

    _odottaa = [True]

    def edistyminen(n, yht, erä, erat):
        if _odottaa[0]:
            stdscr.addstr(4, 0, f"  Erä {erä}/{erat} — lähettää... ({n}/{yht} käsitelty)  ")
        else:
            stdscr.addstr(4, 0, f"  Erä {erä}/{erat} — {n}/{yht} käsitelty               ")
        _odottaa[0] = not _odottaa[0]
        stdscr.refresh()

    try:
        arvioitu = llmarviointi.aja(tutkimus, edistyminen, max_erat=1 if vain_yksi_era else None)
        piirra_otsikko(stdscr, "LLM-arviointi — valmis")
        stdscr.addstr(3, 0, f"Arvioitu: {arvioitu}")
        if vain_yksi_era and arvioitu < uudet + vanhentuneet:
            jaljella = uudet + vanhentuneet - arvioitu
            stdscr.addstr(4, 0, f"Jäljellä vielä {jaljella} kurssia (aja uudelleen jatkaaksesi).")
        nayta_viesti(stdscr, "", 6)
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
