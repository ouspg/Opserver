"""LLM-asetukset: nykyinen malli, saatavuustarkistus, mallien selaus ja vaihto."""
from cliui.apurit import piirra_otsikko, nayta_viesti, valitse_listasta, lue_teksti
from cliui.valikot import toimintovalikko
from llm import kutsu, mallitiedot, asetukset


def nayta(stdscr) -> None:
    def otsikko() -> str:
        malli = kutsu.hae_malli() or "(ei asetettu)"
        tuoreus = mallitiedot.tuoreus_teksti()
        teksti = f"LLM-asetukset — nykyinen malli: {malli}"
        return teksti + (f"  ·  mallilista {tuoreus}" if tuoreus else "  ·  mallilistaa ei vielä haettu")

    toimintovalikko(stdscr, otsikko, [
        ("Tarkista nykyisen mallin saatavuus", _tarkista),
        ("Selaa ja vaihda mallia", _selaa_ja_vaihda),
        ("Päivitä mallilista palvelimelta", _paivita_lista),
    ])


def _tarkista(stdscr) -> None:
    piirra_otsikko(stdscr, "Mallin saatavuus")
    stdscr.addstr(3, 0, "Tarkistetaan...")
    stdscr.refresh()
    try:
        mallitiedot.tarkista_saatavuus()
    except Exception as e:
        nayta_viesti(stdscr, f"Ei saatavilla: {e}", 4)
        return
    rivit = [f"Malli '{kutsu.hae_malli()}' on saatavilla."]
    varoitus = mallitiedot.muototuki_varoitus()
    if varoitus:
        rivit += ["", f"VAROITUS: {varoitus}"]
    for i, teksti in enumerate(rivit):
        stdscr.addstr(4 + i, 0, teksti)
    nayta_viesti(stdscr, "", 4 + len(rivit) + 1)


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
    otsikkorivit, rivit = mallitiedot.muotoile_taulukko(mallit)
    tuoreus = mallitiedot.tuoreus_teksti()
    otsikko = "Valitse malli (Enter vaihtaa)"
    otsikko += f" — lista {tuoreus}" if tuoreus else ""
    valinta = valitse_listasta(stdscr, otsikko, rivit, kiintea_otsikko=otsikkorivit)
    if valinta is None:
        return

    valittu = mallit[valinta]["id"]
    asetukset.aseta_malli(valittu)
    nayta_viesti(stdscr, f"Malli vaihdettu: {valittu}")
