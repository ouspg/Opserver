"""Raporttinäkymä: LLM-raportin generointi tutkimukselle."""
from tietokanta import mallit
from cliui.apurit import piirra_otsikko, nayta_viesti, valitse_listasta


def nayta(stdscr) -> None:
    tutkimukset = mallit.hae_tutkimukset()
    if not tutkimukset:
        piirra_otsikko(stdscr, "Tee raportti")
        nayta_viesti(stdscr, "Ei tutkimuksia — lisää ensin tutkimus (valikko 3).")
        return
    rivit = [f"{t['LuokittelunNimi']} ({t['Slug']})" for t in tutkimukset]
    indeksi = valitse_listasta(stdscr, "Tee raportti — valitse tutkimus", rivit)
    if indeksi is None:
        return
    _raportti(stdscr, tutkimukset[indeksi])


def _raportti(stdscr, tutkimus: dict) -> None:
    while True:
        valinta = valitse_listasta(
            stdscr,
            f"Raportti — {tutkimus['LuokittelunNimi']}",
            ["Generoi raportti LLM:llä", "Näytä tilanne"],
        )
        if valinta is None:
            return
        if valinta == 0:
            _generoi(stdscr, tutkimus)
        elif valinta == 1:
            _nayta_tilanne(stdscr, tutkimus)


def _generoi(stdscr, tutkimus: dict) -> None:
    from raportti import llmraportti
    piirra_otsikko(stdscr, f"Raportti — {tutkimus['LuokittelunNimi']}")
    stdscr.addstr(3, 0, "Yhdistetään LLM:ään...")
    stdscr.refresh()

    def edistyminen(n, yht, avain):
        if avain == "valmis":
            return
        stdscr.addstr(4, 0, f"  Osio {n + 1}/{yht}: {avain}...                     ")
        stdscr.refresh()

    try:
        lkm = llmraportti.aja(tutkimus, edistyminen)
        piirra_otsikko(stdscr, "Raportti — valmis")
        stdscr.addstr(3, 0, f"Generoitu {lkm} osiota.")
        stdscr.addstr(4, 0, "Raportti on luettavissa Web-UI:n Raportti-välilehdellä.")
        nayta_viesti(stdscr, "", 6)
    except EnvironmentError as e:
        nayta_viesti(stdscr, f"Virhe: {e}")
    except Exception as e:
        nayta_viesti(stdscr, f"LLM-virhe: {e}")


def _nayta_tilanne(stdscr, tutkimus: dict) -> None:
    osiot = mallit.hae_raportti_osiot(tutkimus["TID"])
    piirra_otsikko(stdscr, f"Raportin tilanne — {tutkimus['LuokittelunNimi']}")
    if not osiot:
        nayta_viesti(stdscr, "Raporttia ei ole vielä generoitu.")
        return
    from raportti.llmraportti import OSIOT
    for i, avain in enumerate(OSIOT):
        tila = "✓ valmis" if avain in osiot else "— puuttuu"
        stdscr.addstr(3 + i, 0, f"  {avain:<15} {tila}")
    nayta_viesti(stdscr, "", 3 + len(OSIOT) + 1)
