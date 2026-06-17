"""LLM-asetukset: nykyinen malli, saatavuustarkistus, mallien selaus ja vaihto."""
from cliui.apurit import piirra_otsikko, nayta_viesti, valitse_listasta, lue_teksti
from llm import kutsu, mallitiedot, asetukset


def nayta(stdscr) -> None:
    while True:
        malli = kutsu.hae_malli() or "(ei asetettu)"
        valinta = valitse_listasta(
            stdscr,
            f"LLM-asetukset — nykyinen malli: {malli}",
            [
                "Tarkista nykyisen mallin saatavuus",
                "Selaa ja vaihda mallia",
                "Päivitä mallilista palvelimelta",
            ],
        )
        if valinta is None:
            return
        if valinta == 0:
            _tarkista(stdscr)
        elif valinta == 1:
            _selaa_ja_vaihda(stdscr)
        elif valinta == 2:
            _paivita_lista(stdscr)


def _tarkista(stdscr) -> None:
    piirra_otsikko(stdscr, "Mallin saatavuus")
    stdscr.addstr(3, 0, "Tarkistetaan...")
    stdscr.refresh()
    try:
        mallitiedot.tarkista_saatavuus()
        nayta_viesti(stdscr, f"Malli '{kutsu.hae_malli()}' on saatavilla.")
    except Exception as e:
        nayta_viesti(stdscr, f"Ei saatavilla: {e}")


def _paivita_lista(stdscr) -> None:
    piirra_otsikko(stdscr, "Mallilista")
    stdscr.addstr(3, 0, "Haetaan...")
    stdscr.refresh()
    try:
        mallit = mallitiedot.hae_mallit(paivita=True)
        nayta_viesti(stdscr, f"Mallilista päivitetty ({len(mallit)} mallia).")
    except Exception as e:
        nayta_viesti(stdscr, f"Haku epäonnistui: {e}")


def _selaa_ja_vaihda(stdscr) -> None:
    piirra_otsikko(stdscr, "Selaa malleja")
    suodatin = lue_teksti(stdscr, "Suodata (esim. 'free', 'gpt', tyhjä = kaikki)", 3).strip().lower()
    try:
        mallit = mallitiedot.hae_mallit()
    except Exception as e:
        nayta_viesti(stdscr, f"Mallilistan haku epäonnistui: {e}")
        return

    if suodatin:
        mallit = [m for m in mallit if suodatin in (m.get("id", "") + " " + m.get("name", "")).lower()]
    if not mallit:
        nayta_viesti(stdscr, "Ei suodatinta vastaavia malleja.")
        return

    mallit = sorted(mallit, key=lambda m: m.get("id", ""))
    rivit = [mallitiedot.kuvaa_malli(m) for m in mallit]
    valinta = valitse_listasta(stdscr, "Valitse malli (Enter vaihtaa)", rivit)
    if valinta is None:
        return

    valittu = mallit[valinta]["id"]
    asetukset.aseta_malli(valittu)
    nayta_viesti(stdscr, f"Malli vaihdettu: {valittu}")
