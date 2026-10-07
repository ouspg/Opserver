"""Arviointinäkymä: LLM-arviointi mukaan otetuille kursseille."""
from tietokanta import mallit
from cliui.apurit import piirra_otsikko, nayta_viesti, valitse_listasta
from cliui.valikot import toimintovalikko, valitse_tutkimus
from cliui import llmvaihe


def _vaihe() -> llmvaihe.Vaihe:
    from arviointi import testierat
    from tietokanta import testimallit
    from cliui import asetuseditori
    return llmvaihe.Vaihe(
        nimi="arvioinnin", yksikko="vastausta", tulokset="vastaukset", oletus_erakoko="5",
        aja_testierat=testierat.aja_testierat, testiera_raportti=_testiera_raportti,
        hae_ajot=testimallit.hae_testiajot_arviointi,
        ajon_rivi=lambda a: (f"{a['Ajo']}  —  {a['Vastauksia']} vastausta / {a['Kursseja']} kurssia, "
                             f"eräkoko {a['Erakoko']}, {a['Malli'] or '?'}"),
        ajon_koko=lambda a: f"{a['Vastauksia']} vastausta",
        siirra=testimallit.siirra_testiajo_arviointi, poista=testimallit.poista_testiajo_arviointi,
        asetukset=asetuseditori.ARVIOINTI_ASETUKSET,
        ei_eria="Ei eriä ajettu (ei arvioimattomia kursseja?).",
    )


# Tilaston rivit: (avain aja()n tilastodictissä, näyttöteksti). Sama järjestys
# elävässä edistymisnäytössä ja loppuyhteenvedossa.
_TILASTORIVIT = [
    ("onnistuneet", "Onnistuneita arviointeja"),
    ("max_tokens", "Epäonnistuneita arviointeja (max tokens)"),
    ("virhe_502", "Epäonnistuneita arviointeja (502 virhe)"),
    ("tyhja", "Epäonnistuneita arviointeja (tyhjä vastaus)"),
    ("muoto", "Epäonnistuneita arviointeja (vastaus ei oikean muotoinen)"),
]
_TYHJA_TILASTO = {avain: 0 for avain, _ in _TILASTORIVIT}


def _piirra_tilasto(stdscr, tilasto: dict, alkurivi: int) -> None:
    for i, (avain, nimi) in enumerate(_TILASTORIVIT):
        stdscr.addstr(alkurivi + i, 0, f"  *  {tilasto.get(avain, 0):>3}  {nimi}")


def _piirra_edistyminen(stdscr, otsikko: str, tila_rivi: str, tilasto: dict) -> None:
    """Tyhjentää ja piirtää koko edistymisnäytön (ei jää roikkumaan vanhaa tekstiä)."""
    stdscr.erase()
    piirra_otsikko(stdscr, otsikko)
    stdscr.addstr(3, 0, "Yhdistetään LLM:ään...")
    stdscr.addstr(4, 0, f"  {tila_rivi}")
    _piirra_tilasto(stdscr, tilasto, 6)
    stdscr.addstr(6 + len(_TILASTORIVIT) + 1, 0, "paina q keskeyttääksesi")
    stdscr.refresh()


def _nayta_yhteenveto(stdscr, otsikko: str, keskeytetty: bool, tilasto: dict, yhteensa: int) -> None:
    stdscr.erase()
    piirra_otsikko(stdscr, f"{otsikko} — {'keskeytetty' if keskeytetty else 'valmis'}")
    _piirra_tilasto(stdscr, tilasto, 3)
    rivi = 3 + len(_TILASTORIVIT) + 1
    kesken = yhteensa - tilasto.get("onnistuneet", 0)
    if kesken > 0:
        stdscr.addstr(rivi, 0, f"Jäljellä vielä {kesken} kurssia (aja uudelleen jatkaaksesi).")
        rivi += 1
    nayta_viesti(stdscr, "", rivi + 1)


def nayta(stdscr) -> None:
    tutkimus = valitse_tutkimus(stdscr, "Arvioi — valitse tutkimus")
    if tutkimus is not None:
        _arvioi(stdscr, tutkimus)


def _arvioi(stdscr, tutkimus: dict) -> None:
    toiminnot = [
        ("Aja LLM-arviointi (kaikki arvioimattomat)", _aja_llm),
        ("Aja LLM-arviointi (vain yksi eräpyyntö)", lambda s, t: _aja_llm(s, t, vain_yksi_era=True)),
        ("Aja LLM-testierä kirjaten tilastot", lambda s, t: llmvaihe.aja_testiera(s, t, _vaihe())),
        ("Muokkaa LLM-arvioinnin asetuksia", lambda s, t: llmvaihe.muokkaa_asetukset(s, t, _vaihe())),
        ("Siirrä testiajo varsinaiseen aineistoon", lambda s, t: llmvaihe.siirra_testiajo(s, t, _vaihe())),
        ("Poista testiajo", lambda s, t: llmvaihe.poista_testiajo(s, t, _vaihe())),
        ("Korjaa raaka-JSON-vastaukset ja luokkien kirjoitusasu", _korjaa_raaka_json),
        ("Näytä tilanne", _nayta_tilanne),
    ]
    toimintovalikko(stdscr, f"Arvioi — {tutkimus['LuokittelunNimi']}", toiminnot, tutkimus)


def _korjaa_raaka_json(stdscr, tutkimus: dict) -> None:
    """Jäsentää uudelleen vastaukset, joiden teksti jäi raa'aksi JSON-objektiksi, ja
    kanonisoi luokkien kirjoitusasun ('ei lainkaan ' → 'Ei lainkaan').

    Ei kuluta LLM-kutsuja: data on tallessa Vastaus-kentässä. Turvallinen ajaa
    uudelleen — korjattu rivi ei enää täytä hakuehtoa. Tuntemattomat luokat jäävät
    ennalleen ja listataan korjattaviksi (WebUI:n arviokorjaus).
    """
    from arviointi import korjaus

    piirra_otsikko(stdscr, f"Korjaa raaka-JSON — {tutkimus['LuokittelunNimi']}")
    stdscr.addstr(3, 0, "Etsitään korjattavia vastauksia...")
    stdscr.refresh()

    def edistyminen(n, yhteensa, korjatut, ohitetut):
        stdscr.addstr(3, 0, f"Korjataan {n}/{yhteensa} — korjattu {korjatut}, ohitettu {ohitetut}")
        stdscr.clrtoeol()
        stdscr.refresh()

    try:
        korjatut, ohitetut = korjaus.korjaa_raaka_json(tutkimus["TID"], edistyminen)
        luokat, tuntemattomat = korjaus.korjaa_luokat(tutkimus["TID"])
    except Exception as e:
        nayta_viesti(stdscr, f"Virhe korjauksessa: {e}")
        return

    if korjatut == ohitetut == luokat == 0 and not tuntemattomat:
        nayta_viesti(stdscr, "Ei korjattavia vastauksia — kaikki on jäsennetty oikein.")
        return
    viesti = f"Korjattu {korjatut} vastausta, kanonisoitu {luokat} luokkaa."
    if ohitetut:
        viesti += f" Ohitettu {ohitetut} (teksti ei jäsenny — jätetty ennalleen)."
    if tuntemattomat:
        esimerkit = ", ".join(sorted({f"'{r['Luokka']}'" for r in tuntemattomat})[:5])
        viesti += (f" Tuntematon luokka {len(tuntemattomat)} vastauksessa ({esimerkit}) —"
                   f" jätetty ennalleen, korjaa WebUI:n arvioinneissa.")
    nayta_viesti(stdscr, viesti)


def _aja_llm(stdscr, tutkimus: dict, vain_yksi_era: bool = False) -> None:
    from arviointi import llmarviointi
    from tietokanta import testimallit
    otsikko = "LLM-arviointi (yksi erä)" if vain_yksi_era else "LLM-arviointi"
    piirra_otsikko(stdscr, f"{otsikko} — {tutkimus['LuokittelunNimi']}")

    # Varoita siirtämättömistä testiajoista: ne käsiteltäisiin nyt uudelleen,
    # ellei niitä siirretä ensin varsinaiseen aineistoon. Kevyt tiivistehaku
    # (ei vedä kursseja/vastauksia — täysi _selvita_tyo lasketaan vasta alempana).
    tiivisteet = list(llmarviointi._kysymystiivisteet(tutkimus).values())
    siirrettavat = testimallit.hae_siirrettavat_ajot_arviointi(tutkimus["TID"], tiivisteet)
    if not llmvaihe.kasittele_siirrettavat(stdscr, _vaihe(), siirrettavat):
        return
    piirra_otsikko(stdscr, f"{otsikko} — {tutkimus['LuokittelunNimi']}")

    # Selvitä työ KERRAN (mahdollisen testajosiirron jälkeen) ja jaa se
    # työmäärälaskennalle ja ajolle — muuten _selvita_tyo (kaikki kurssit +
    # vastaustiivisteet) ajettaisiin 2–3 kertaa peräkkäin etäpalvelinta vasten.
    tieto = llmarviointi._selvita_tyo(tutkimus)
    uudet, taydennettavat, muuttuneet = llmarviointi.laske_tyomaara(tutkimus, tieto=tieto)
    yhteensa = uudet + taydennettavat + muuttuneet
    if yhteensa == 0:
        nayta_viesti(stdscr, "Kaikki mukana olevat kurssit on jo arvioitu nykyisellä kehotteella ja kysymyksillä.")
        return

    # Varoitetaan vain jos kehote/kysymys OIKEASTI muuttui (uudelleenajo maksaa).
    # Pelkkä täydennys (puuttuvia vastauksia) ei ole muutos → ei varoitusta.
    if not vain_yksi_era and muuttuneet > 0:
        valinta = valitse_listasta(
            stdscr,
            "LLM-arviointi — kehote tai kysymys on muuttunut",
            [
                f"Aja LLM: {uudet} uutta + {taydennettavat} täydennys + {muuttuneet} uudelleen (muutos)",
                "Peruuta",
            ],
        )
        if valinta != 0:
            return

    if not llmvaihe.malli_kaytettavissa(stdscr):
        return

    otsikko_ajo = f"{otsikko} — {tutkimus['LuokittelunNimi']}"
    saatu = [dict(_TYHJA_TILASTO)]  # viimeisin tilasto talteen loppunäyttöä varten
    keskeytetty = [False]

    def edistyminen(n, yht, erä, erat, tilasto):
        saatu[0] = tilasto
        _piirra_edistyminen(stdscr, otsikko_ajo, f"Erä {erä}/{erat} — lähettää... ({n}/{yht} käsitelty)", tilasto)

    def keskeyta():
        if stdscr.getch() in (ord("q"), ord("Q")):
            keskeytetty[0] = True
            return True
        return False

    # nodelay(True): getch ei blokkaa → 'q' luetaan erien välissä keskeyttämättä ajoa.
    stdscr.nodelay(True)
    virhe = None
    try:
        llmarviointi.aja(tutkimus, edistyminen, max_erat=1 if vain_yksi_era else None,
                         tieto=tieto, keskeyta_cb=keskeyta)
    except EnvironmentError as e:
        virhe = f"Virhe: {e}"
    except Exception as e:
        virhe = f"LLM-virhe: {e}"
    finally:
        stdscr.nodelay(False)

    if virhe:
        nayta_viesti(stdscr, virhe)
        return
    _nayta_yhteenveto(stdscr, otsikko, keskeytetty[0], saatu[0], yhteensa)


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


def _nayta_tilanne(stdscr, tutkimus: dict) -> None:
    tid = tutkimus["TID"]
    # COUNT(*) eikä rivinouto: aiemmin haki kaikkien mukana-kurssien ja
    # arvioimattomien täydet rivit (OpsKuvaus-tekstit) pelkkään len()-laskentaan.
    mukana_lkm = mallit.laske_luokitukset(tid, mukana=True)
    arvioimatta_lkm = mallit.laske_arvioimattomat(tid)
    arvioitu_lkm = mukana_lkm - arvioimatta_lkm

    piirra_otsikko(stdscr, f"Tilanne — {tutkimus['LuokittelunNimi']}")
    stdscr.addstr(3, 0, f"Mukaan otettuja kursseja: {mukana_lkm}")
    stdscr.addstr(4, 0, f"Arvioitu:                 {arvioitu_lkm}")
    stdscr.addstr(5, 0, f"Odottaa arviointia:       {arvioimatta_lkm}")
    nayta_viesti(stdscr, "", 7)
