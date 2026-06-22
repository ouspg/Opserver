"""Arviointinäkymä: LLM-arviointi mukaan otetuille kursseille."""
from tietokanta import mallit
from cliui.apurit import piirra_otsikko, nayta_viesti, valitse_listasta, lue_teksti


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
    toiminnot = [
        ("Aja LLM-arviointi (kaikki arvioimattomat)", lambda s, t: _aja_llm(s, t)),
        ("Aja LLM-arviointi (vain yksi eräpyyntö)", lambda s, t: _aja_llm(s, t, vain_yksi_era=True)),
        ("Aja LLM-testierä kirjaten tilastot", _aja_testiera),
        ("Muokkaa LLM-arvioinnin asetuksia", _muokkaa_asetukset),
        ("Siirrä testiajo varsinaiseen aineistoon", _siirra_testiajo),
        ("Poista testiajo", _poista_testiajo),
        ("Näytä tilanne", _nayta_tilanne),
    ]
    while True:
        valinta = valitse_listasta(
            stdscr,
            f"Arvioi — {tutkimus['LuokittelunNimi']}",
            [nimi for nimi, _ in toiminnot],
        )
        if valinta is None:
            return
        toiminnot[valinta][1](stdscr, tutkimus)


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


def _aja_testiera(stdscr, tutkimus: dict) -> None:
    from arviointi import testierat
    from llm import mallitiedot

    piirra_otsikko(stdscr, f"LLM-testierä — {tutkimus['LuokittelunNimi']}")
    erakoko_s = lue_teksti(stdscr, "Eräkoko (kursseja per LLM-kutsu)", 3, "5")
    montako_s = lue_teksti(stdscr, "Montako erää ajetaan", 4, "3")
    try:
        erakoko, montako = int(erakoko_s), int(montako_s)
        if erakoko < 1 or montako < 1:
            raise ValueError
    except ValueError:
        nayta_viesti(stdscr, "Kelvottomat luvut — anna positiiviset kokonaisluvut.")
        return

    try:
        mallitiedot.tarkista_saatavuus()
    except Exception as e:
        nayta_viesti(stdscr, f"Mallia ei voi käyttää: {e}")
        return

    piirra_otsikko(stdscr, f"LLM-testierä — {tutkimus['LuokittelunNimi']}")
    stdscr.addstr(3, 0, f"Ajetaan {montako} × {erakoko} kurssia...")
    stdscr.refresh()

    def edistyminen(era_nro, erat):
        stdscr.addstr(4, 0, f"  Erä {era_nro}/{erat} käsitelty")
        stdscr.refresh()

    try:
        tulos = testierat.aja_testierat(tutkimus, erakoko, montako, edistyminen)
    except Exception as e:
        nayta_viesti(stdscr, f"Virhe testierässä: {e}")
        return

    if not tulos["tietueet"]:
        nayta_viesti(stdscr, "Ei eriä ajettu (ei arvioimattomia kursseja?).")
        return

    from tietokanta import testimallit
    valinta = valitse_listasta(
        stdscr,
        "LLM-testierä valmis — siirretäänkö tulokset varsinaiseen aineistoon?",
        ["Siirrä varsinaiseen aineistoon", "Älä siirrä (säilyy testiajona)"],
        kiintea_otsikko=_testiera_raportti(tulos, erakoko),
    )
    if valinta == 0:
        siirretty = testimallit.siirra_testiajo_arviointi(tulos["ajo_id"])
        nayta_viesti(stdscr, f"Siirretty {siirretty} vastausta varsinaiseen aineistoon (ajo {tulos['ajo_id']}).")
    else:
        nayta_viesti(stdscr, f"Ei siirretty. Testiajo {tulos['ajo_id']} säilyy (siirrä/poista myöhemmin valikosta).")


def _testiera_raportti(tulos: dict, erakoko: int) -> list[str]:
    """Per-erä raportti eräkoon viritystä ja siirtopäätöstä varten."""
    tietueet = tulos["tietueet"]
    rivit = [
        f"Ajotunnus {tulos['ajo_id']}  ·  eräkoko {erakoko}  ·  {tulos['eria']} erää",
        "",
        "Erä  Kurss  Kysym  Täyttö  finish   Pudon  Kesto",
        "---  -----  -----  ------  -------  -----  ------",
    ]
    for t in tietueet:
        ta = f"{t['ulostulo_tayttoaste']:.0%}" if t["ulostulo_tayttoaste"] is not None else "?"
        rivit.append(
            f"{t['era_nro']:<3}  {t['kursseja_lahetetty']:<5}  {t['kysymyksia']:<5}  "
            f"{ta:>5}   {(t['finish_reason'] or '?'):<7}  {t['pudonneet']:<5}  {t['kesto_s']}s"
        )
    kurss = sum(t["kursseja_lahetetty"] for t in tietueet)
    pud = sum(t["pudonneet"] for t in tietueet)
    tayt = [t["ulostulo_tayttoaste"] for t in tietueet if t["ulostulo_tayttoaste"] is not None]
    maxt = f"{max(tayt):.0%}" if tayt else "?"
    katk = sum(1 for t in tietueet if t["finish_reason"] == "length")
    rivit += [
        "",
        f"Yht: {kurss} kurssia · pudonneita {pud}",
        f"Suurin täyttöaste {maxt} (katto {tietueet[0]['ulostulo_katto']}) · katkesi {katk}",
        f"Tilastot: {tulos['tilastopolku']}",
    ]
    return rivit


def _muokkaa_asetukset(stdscr, tutkimus: dict) -> None:
    from cliui import asetuseditori
    asetuseditori.muokkaa_asetuksia(
        stdscr, f"LLM-arvioinnin asetukset — {tutkimus['LuokittelunNimi']}",
        asetuseditori.ARVIOINTI_ASETUKSET,
    )


def _valitse_testiajo(stdscr, tutkimus: dict, otsikko: str):
    """Listaa arvioinnin testiajot ja palauttaa valitun (tai None)."""
    from tietokanta import testimallit

    ajot = testimallit.hae_testiajot_arviointi(tutkimus["TID"])
    if not ajot:
        nayta_viesti(stdscr, "Ei arvioinnin testiajoja tälle tutkimukselle.")
        return None
    rivit = [
        f"{a['Ajo']}  —  {a['Vastauksia']} vastausta / {a['Kursseja']} kurssia, "
        f"eräkoko {a['Erakoko']}, {a['Malli'] or '?'}"
        for a in ajot
    ]
    valinta = valitse_listasta(stdscr, otsikko, rivit)
    return ajot[valinta] if valinta is not None else None


def _siirra_testiajo(stdscr, tutkimus: dict) -> None:
    from tietokanta import testimallit

    ajo = _valitse_testiajo(stdscr, tutkimus, "Siirrä testiajo varsinaiseen aineistoon — valitse")
    if ajo is None:
        return
    varmistus = valitse_listasta(
        stdscr, f"Siirrä ajo {ajo['Ajo']} ({ajo['Vastauksia']} vastausta) varsinaiseen aineistoon?",
        ["Siirrä — korvaa näiden kurssien aiemmat vastaukset", "Peruuta"],
    )
    if varmistus != 0:
        return
    siirretty = testimallit.siirra_testiajo_arviointi(ajo["Ajo"])
    nayta_viesti(stdscr, f"Siirretty {siirretty} vastausta varsinaiseen aineistoon (ajo {ajo['Ajo']}).")


def _poista_testiajo(stdscr, tutkimus: dict) -> None:
    from tietokanta import testimallit

    ajo = _valitse_testiajo(stdscr, tutkimus, "Poista testiajo — valitse")
    if ajo is None:
        return
    varmistus = valitse_listasta(
        stdscr, f"Poista testiajo {ajo['Ajo']}?",
        [f"Poista {ajo['Vastauksia']} vastausta lopullisesti", "Peruuta"],
    )
    if varmistus != 0:
        return
    poistettu = testimallit.poista_testiajo_arviointi(ajo["Ajo"])
    nayta_viesti(stdscr, f"Poistettu {poistettu} riviä (ajo {ajo['Ajo']}).")


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
