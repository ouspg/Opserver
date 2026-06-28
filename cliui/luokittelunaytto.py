"""Luokittelunäkymä: meta-suodatus ja LLM-luokittelu."""
from tietokanta import mallit
from cliui.apurit import piirra_otsikko, nayta_viesti, valitse_listasta, lue_teksti


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
    toiminnot = [
        ("Aja meta-suodatus", _aja_meta),
        ("Aja LLM-luokittelu", _aja_llm),
        ("Aja LLM-testierä kirjaten tilastot", _aja_testiera),
        ("Muokkaa LLM-luokittelun asetuksia", _muokkaa_asetukset),
        ("Siirrä testiajo varsinaiseen aineistoon", _siirra_testiajo),
        ("Poista testiajo", _poista_testiajo),
        ("Näytä tilanne", _nayta_tilanne),
    ]
    while True:
        valinta = valitse_listasta(
            stdscr,
            f"Luokittele — {tutkimus['LuokittelunNimi']}",
            [nimi for nimi, _ in toiminnot],
        )
        if valinta is None:
            return
        toiminnot[valinta][1](stdscr, tutkimus)


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
    from tietokanta import testimallit
    piirra_otsikko(stdscr, f"LLM-luokittelu — {tutkimus['LuokittelunNimi']}")

    tid = tutkimus["TID"]
    tiiv = llmluokittelu.laske_tiiviste(tutkimus)

    # Varoita siirtämättömistä testiajoista: ne käsiteltäisiin nyt uudelleen
    # (tokeneita hukkaan), ellei niitä siirretä ensin varsinaiseen aineistoon.
    siirrettavat = testimallit.hae_siirrettavat_ajot_luokittelu(tid, tiiv)
    if siirrettavat:
        valinta = valitse_listasta(
            stdscr,
            f"Siirtämättömiä testiajoja: {len(siirrettavat)} — niiden kurssit käsiteltäisiin uudelleen",
            [
                "Siirrä testiajot ensin (säästää tokeneita)",
                "Aja silti (testiajot käsitellään uudelleen)",
                "Peruuta",
            ],
        )
        if valinta is None or valinta == 2:
            return
        if valinta == 0:
            siirretty = sum(testimallit.siirra_testiajo_luokittelu(a) for a in siirrettavat)
            nayta_viesti(stdscr, f"Siirretty {siirretty} luokitusta {len(siirrettavat)} testiajosta.")
            piirra_otsikko(stdscr, f"LLM-luokittelu — {tutkimus['LuokittelunNimi']}")

    uudet = mallit.laske_luokittelemattomat(tid)            # ei vielä LLM-luokiteltu
    kaikki = mallit.laske_luokittelemattomat(tid, tiiv)     # + vanhentuneen kehotteen tulokset
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

    # Esitarkistus: malli on saatavilla ennen kuin aloitetaan LLM-kutsut.
    # Ohitetaan jos valintakehote on tyhjä → meta-luokittelu ei käytä LLM:ää.
    if (tutkimus.get("Luokittelukehote") or "").strip():
        try:
            mallitiedot.tarkista_saatavuus()
        except Exception as e:
            nayta_viesti(stdscr, f"Mallia ei voi käyttää: {e}")
            return

    # Tyhjennä vahvistusvalikon / testiajovaroituksen jäänteet ennen ajonäkymää.
    piirra_otsikko(stdscr, f"LLM-luokittelu — {tutkimus['LuokittelunNimi']}")
    stdscr.addstr(3, 0, "Yhdistetään LLM:ään...")
    stdscr.refresh()

    def edistyminen(n, yht, erä, erat, mukana, hylätty, epaonnistunut):
        osuus = f" (mukaan {mukana/(mukana + hylätty):.0%})" if (mukana + hylätty) else ""
        stdscr.addstr(4, 0, f"  Erä {erä}/{erat} — {n}/{yht} kurssia käsitelty")
        stdscr.addstr(5, 0, f"  Mukaan: {mukana}   Hylätty: {hylätty}   Epäonnistunut: {epaonnistunut}{osuus}")
        stdscr.clrtoeol()
        stdscr.refresh()

    try:
        mukana, hylätty, virheet = llmluokittelu.aja(tutkimus, edistyminen)
        piirra_otsikko(stdscr, "LLM-luokittelu — valmis")
        stdscr.addstr(3, 0, f"Mukaan otettu: {mukana}")
        stdscr.addstr(4, 0, f"Hylätty:       {hylätty}")
        if virheet:
            stdscr.addstr(5, 0, f"Ohitettuja viallisia eriä: {virheet} (kurssit tulevat seuraavalla ajolla)")
        nayta_viesti(stdscr, "", 7)
    except EnvironmentError as e:
        nayta_viesti(stdscr, f"Virhe: {e}")
    except Exception as e:
        nayta_viesti(stdscr, f"LLM-virhe: {e}")


def _kysy_luvut(stdscr, otsikko: str) -> tuple[int, int] | None:
    """Kysyy eräkoon ja erien määrän. Palauttaa (erakoko, montako) tai None."""
    piirra_otsikko(stdscr, otsikko)
    erakoko_s = lue_teksti(stdscr, "Eräkoko (kursseja per LLM-kutsu)", 3, "30")
    montako_s = lue_teksti(stdscr, "Montako erää ajetaan", 4, "3")
    try:
        erakoko, montako = int(erakoko_s), int(montako_s)
        if erakoko < 1 or montako < 1:
            raise ValueError
    except ValueError:
        nayta_viesti(stdscr, "Kelvottomat luvut — anna positiiviset kokonaisluvut.")
        return None
    return erakoko, montako


def _testiera_raportti(tulos: dict, erakoko: int) -> list[str]:
    """Per-erä raportti eräkoon viritystä ja siirtopäätöstä varten."""
    tietueet = tulos["tietueet"]
    rivit = [
        f"Ajotunnus {tulos['ajo_id']}  ·  eräkoko {erakoko}  ·  {tulos['eria']} erää",
        "",
        "Erä  Kurss  Mukana  Hyl   Täyttö  finish   Pudon  Kesto",
        "---  -----  ------  ----  ------  -------  -----  ------",
    ]
    for t in tietueet:
        ta = f"{t['ulostulo_tayttoaste']:.0%}" if t["ulostulo_tayttoaste"] is not None else "?"
        rivit.append(
            f"{t['era_nro']:<3}  {t['kursseja_lahetetty']:<5}  {t['mukana']:<6}  {t['hylatty']:<4}  "
            f"{ta:>5}   {(t['finish_reason'] or '?'):<7}  {t['pudonneet']:<5}  {t['kesto_s']}s"
        )
    kurss = sum(t["kursseja_lahetetty"] for t in tietueet)
    muk = sum(t["mukana"] for t in tietueet)
    hyl = sum(t["hylatty"] for t in tietueet)
    pud = sum(t["pudonneet"] for t in tietueet)
    tayt = [t["ulostulo_tayttoaste"] for t in tietueet if t["ulostulo_tayttoaste"] is not None]
    maxt = f"{max(tayt):.0%}" if tayt else "?"
    katk = sum(1 for t in tietueet if t["finish_reason"] == "length")
    rivit += [
        "",
        f"Yht: {kurss} kurssia · mukana {muk} / hylätty {hyl} · pudonneita {pud}",
        f"Suurin täyttöaste {maxt} (katto {tietueet[0]['ulostulo_katto']}) · katkesi {katk}",
        f"Tilastot: {tulos['tilastopolku']}",
    ]
    return rivit


def _aja_testiera(stdscr, tutkimus: dict) -> None:
    from luokittelu import testierat
    from llm import mallitiedot

    luvut = _kysy_luvut(stdscr, f"LLM-testierä — {tutkimus['LuokittelunNimi']}")
    if luvut is None:
        return
    erakoko, montako = luvut

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
        nayta_viesti(stdscr, "Ei eriä ajettu (ei luokittelemattomia kursseja?).")
        return

    from tietokanta import testimallit
    valinta = valitse_listasta(
        stdscr,
        "LLM-testierä valmis — siirretäänkö tulokset varsinaiseen aineistoon?",
        ["Siirrä varsinaiseen aineistoon", "Älä siirrä (säilyy testiajona)"],
        kiintea_otsikko=_testiera_raportti(tulos, erakoko),
    )
    if valinta == 0:
        siirretty = testimallit.siirra_testiajo_luokittelu(tulos["ajo_id"])
        nayta_viesti(stdscr, f"Siirretty {siirretty} luokitusta varsinaiseen aineistoon (ajo {tulos['ajo_id']}).")
    else:
        nayta_viesti(stdscr, f"Ei siirretty. Testiajo {tulos['ajo_id']} säilyy (siirrä/poista myöhemmin valikosta).")


def _muokkaa_asetukset(stdscr, tutkimus: dict) -> None:
    from cliui import asetuseditori
    asetuseditori.muokkaa_asetuksia(
        stdscr, f"LLM-luokittelun asetukset — {tutkimus['LuokittelunNimi']}",
        asetuseditori.LUOKITTELU_ASETUKSET,
    )


def _valitse_testiajo(stdscr, tutkimus: dict, otsikko: str):
    """Listaa luokittelun testiajot ja palauttaa valitun (tai None)."""
    from tietokanta import testimallit

    ajot = testimallit.hae_testiajot_luokittelu(tutkimus["TID"])
    if not ajot:
        nayta_viesti(stdscr, "Ei luokittelun testiajoja tälle tutkimukselle.")
        return None
    rivit = [
        f"{a['Ajo']}  —  {a['Rivit']} kurssia (mukana {a['Mukana']}), "
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
        stdscr, f"Siirrä ajo {ajo['Ajo']} ({ajo['Rivit']} kurssia) varsinaiseen aineistoon?",
        [f"Siirrä — korvaa näiden kurssien aiemmat luokitukset", "Peruuta"],
    )
    if varmistus != 0:
        return
    siirretty = testimallit.siirra_testiajo_luokittelu(ajo["Ajo"])
    nayta_viesti(stdscr, f"Siirretty {siirretty} luokitusta varsinaiseen aineistoon (ajo {ajo['Ajo']}).")


def _poista_testiajo(stdscr, tutkimus: dict) -> None:
    from tietokanta import testimallit

    ajo = _valitse_testiajo(stdscr, tutkimus, "Poista testiajo — valitse")
    if ajo is None:
        return
    varmistus = valitse_listasta(
        stdscr, f"Poista testiajo {ajo['Ajo']}?",
        [f"Poista {ajo['Rivit']} riviä lopullisesti", "Peruuta"],
    )
    if varmistus != 0:
        return
    poistettu = testimallit.poista_testiajo_luokittelu(ajo["Ajo"])
    nayta_viesti(stdscr, f"Poistettu {poistettu} riviä (ajo {ajo['Ajo']}).")


def _nayta_tilanne(stdscr, tutkimus: dict) -> None:
    tid = tutkimus["TID"]
    t = mallit.hae_tutkimuksen_tilanne(tid)
    arvioimattomat = len(mallit.hae_arvioimattomat(tid))
    arvioitu = max(0, t["hyvaksytty"] - arvioimattomat)

    piirra_otsikko(stdscr, f"Tilanne — {tutkimus['LuokittelunNimi']}")
    korkeus, leveys = stdscr.getmaxyx()

    def rivi(nro: int, label: str, arvo, lisa: str = "") -> None:
        if 3 + nro < korkeus - 2:
            teksti = f"{label:<28}: {arvo}{lisa}"
            stdscr.addstr(3 + nro, 0, teksti[:leveys - 1])

    # Suppilo: jokainen vaihe näyttää läpäisseiden määrän päälukuna ja
    # karsiutuneet (hylätyt / vielä odottavat) suluissa.
    meta_lapi = t["oppilaitos_lapi"] - t["odottaa_meta"] - t["hyl_meta"]
    rivi(0, "Kursseja yhteensä", t["kursseja_yht"])
    rivi(1, "Kursseja (vuosirajaus)", t["vuosi_lapi"], f"   ({t['vuosi_hyl']} hylätty)")
    rivi(2, "Kursseja (oppilaitosrajaus)", t["oppilaitos_lapi"], f"   ({t['oppilaitos_hyl']} hylätty)")
    rivi(3, "Kursseja (metaluokitus)", meta_lapi,
         f"   ({t['hyl_meta']} hylätty, {t['odottaa_meta']} odottaa luokitusta)")
    rivi(4, "Kursseja (LLM-luokitus)", t["hyvaksytty"],
         f"   ({t['hyl_llm']} hylätty, {t['odottaa_llm']} odottaa luokitusta)")
    # Vaihe 3 (arviointi) hyväksytyille — tyhjä rivi erottaa suppilosta.
    rivi(6, "Hyväksytty tutkimukseen", t["hyvaksytty"])
    rivi(7, "LLM-arvioitu", f"{arvioitu} / {t['hyvaksytty']}")
    rivi(8, "Odottaa arviointia", arvioimattomat)
    nayta_viesti(stdscr, "")
