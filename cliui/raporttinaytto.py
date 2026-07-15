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


def _aika_str(aika) -> str:
    """Aikaleima (datetime tai merkkijono) → 'YYYY-MM-DD HH:MM' -esitys."""
    if aika is None:
        return "—"
    if hasattr(aika, "strftime"):
        return aika.strftime("%Y-%m-%d %H:%M")
    return str(aika)[:16]


def koosta_tilanne(tutkimus: dict) -> dict:
    """Kokoaa raportin tuoreustiedot status-sivulle (testattava, ei curses-riippuvuutta).

    Palauttaa {"generoitu": False} jos raporttia ei ole; muuten osioiden tila +
    aikaleimat, tuoreus (tiivistevertailu: ajan_tasalla / vanhentunut / tuntematon)
    ja generoinnin jälkeen tehtyjen HITL-korjausten ja kommenttien määrän.
    """
    from raportti import llmraportti
    tid = tutkimus["TID"]
    tila_rivit = mallit.hae_raportti_tila(tid)
    if not tila_rivit:
        return {"generoitu": False}

    kartta = {r["OsioAvain"]: r for r in tila_rivit}
    osiot = [{"avain": a, "on": a in kartta,
              "aikaleima": kartta[a]["Aikaleima"] if a in kartta else None}
             for a in llmraportti.OSIOT]
    aikaleimat = [r["Aikaleima"] for r in tila_rivit]
    generoitu_aika = min(aikaleimat)

    tallennettu = next((r["Laskentatiiviste"] for r in tila_rivit if r["Laskentatiiviste"]), None)
    if tallennettu is None:
        tuoreus = "tuntematon"
    else:
        tuoreus = "ajan_tasalla" if llmraportti.raporttitiiviste(tutkimus) == tallennettu else "vanhentunut"

    return {
        "generoitu": True,
        "osiot": osiot,
        "puuttuu": [o["avain"] for o in osiot if not o["on"]],
        "generoitu_aika": generoitu_aika,
        "viimeksi_muokattu": max(aikaleimat),
        "tuoreus": tuoreus,
        "hitl_jalkeen": mallit.laske_hitl_korjaukset_jalkeen(tid, generoitu_aika),
        "kommentit_jalkeen": mallit.laske_arviokommentit_jalkeen(tid, generoitu_aika),
    }


_TUOREUS_TEKSTI = {
    "ajan_tasalla": "✓ Ajan tasalla — lähdeaineisto ei ole muuttunut generoinnin jälkeen.",
    "vanhentunut": "⚠ Vanhentunut — lähdeaineisto on muuttunut generoinnin jälkeen. Generoi uudelleen.",
    "tuntematon": "? Tuoreus tuntematon — raportti generoitu ennen tuoreusseurantaa.",
}


def _nayta_tilanne(stdscr, tutkimus: dict) -> None:
    tilanne = koosta_tilanne(tutkimus)
    piirra_otsikko(stdscr, f"Raportin tilanne — {tutkimus['LuokittelunNimi']}")
    if not tilanne["generoitu"]:
        nayta_viesti(stdscr, "Raporttia ei ole vielä generoitu.")
        return

    rivi = 3
    stdscr.addstr(rivi, 0, f"Generoitu: {_aika_str(tilanne['generoitu_aika'])}")
    rivi += 2
    for osio in tilanne["osiot"]:
        tila = f"✓ {_aika_str(osio['aikaleima'])}" if osio["on"] else "— puuttuu"
        stdscr.addstr(rivi, 0, f"  {osio['avain']:<12} {tila}")
        rivi += 1
    rivi += 1
    stdscr.addstr(rivi, 0, _TUOREUS_TEKSTI[tilanne["tuoreus"]])
    rivi += 1
    if tilanne["hitl_jalkeen"] or tilanne["kommentit_jalkeen"]:
        stdscr.addstr(rivi, 0, f"  Generoinnin jälkeen: {tilanne['hitl_jalkeen']} HITL-korjausta, "
                               f"{tilanne['kommentit_jalkeen']} kommenttia")
        rivi += 1
    nayta_viesti(stdscr, "", rivi + 1)
