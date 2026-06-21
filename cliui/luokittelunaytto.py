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


def _testiera_yhteenveto(tietueet: list[dict]) -> list[str]:
    """Tiivis yhteenveto eräkoon viritystä varten (täyttöaste, katkeamiset, pudonneet)."""
    if not tietueet:
        return ["Ei eriä ajettu (ei luokittelemattomia kursseja?)."]
    tayttoasteet = [t["ulostulo_tayttoaste"] for t in tietueet if t["ulostulo_tayttoaste"] is not None]
    katkesi = sum(1 for t in tietueet if t["finish_reason"] == "length")
    pudonneet = sum(t["pudonneet"] for t in tietueet)
    epaonnistui = sum(1 for t in tietueet if t["jasennys"] != "ok")
    maks_taytto = f"{max(tayttoasteet):.0%}" if tayttoasteet else "?"
    return [
        f"Eriä: {len(tietueet)}  |  suurin ulostulon täyttöaste: {maks_taytto}",
        f"Katkesi (finish_reason=length): {katkesi}  |  pudonneita kursseja: {pudonneet}",
        f"Jäsennys ei-ok: {epaonnistui}  (uusinta/epäonnistui)",
    ]


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

    piirra_otsikko(stdscr, "LLM-testierä — valmis")
    stdscr.addstr(3, 0, f"Ajotunnus: {tulos['ajo_id']}   (eräkoko {erakoko})")
    for i, rivi in enumerate(_testiera_yhteenveto(tulos["tietueet"]), 4):
        stdscr.addstr(i, 0, rivi[:stdscr.getmaxyx()[1] - 1])
    stdscr.addstr(8, 0, f"Tilastot: {tulos['tilastopolku']}")
    nayta_viesti(stdscr, "", 10)


def _muokkaa_asetukset(stdscr, tutkimus: dict) -> None:
    from cliui import asetuseditori
    asetuseditori.muokkaa_asetuksia(
        stdscr, f"LLM-luokittelun asetukset — {tutkimus['LuokittelunNimi']}",
        asetuseditori.LUOKITTELU_ASETUKSET,
    )


def _poista_testiajo(stdscr, tutkimus: dict) -> None:
    from tietokanta import testimallit

    ajot = testimallit.hae_testiajot_luokittelu(tutkimus["TID"])
    if not ajot:
        nayta_viesti(stdscr, "Ei luokittelun testiajoja tälle tutkimukselle.")
        return
    rivit = [
        f"{a['Ajo']}  —  {a['Rivit']} kurssia (mukana {a['Mukana']}), "
        f"eräkoko {a['Erakoko']}, {a['Malli'] or '?'}"
        for a in ajot
    ]
    valinta = valitse_listasta(stdscr, "Poista testiajo — valitse", rivit)
    if valinta is None:
        return
    ajo = ajot[valinta]["Ajo"]
    varmistus = valitse_listasta(
        stdscr, f"Poista testiajo {ajo}?",
        [f"Poista {ajot[valinta]['Rivit']} riviä lopullisesti", "Peruuta"],
    )
    if varmistus != 0:
        return
    poistettu = testimallit.poista_testiajo_luokittelu(ajo)
    nayta_viesti(stdscr, f"Poistettu {poistettu} riviä (ajo {ajo}).")


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
