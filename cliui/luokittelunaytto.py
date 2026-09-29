"""Luokittelunäkymä: meta-suodatus ja LLM-luokittelu."""
from tietokanta import mallit
from cliui.apurit import piirra_otsikko, nayta_viesti, valitse_listasta
from cliui.valikot import toimintovalikko, valitse_tutkimus
from cliui import llmvaihe


def _vaihe() -> llmvaihe.Vaihe:
    from luokittelu import testierat
    from tietokanta import testimallit
    from cliui import asetuseditori
    return llmvaihe.Vaihe(
        nimi="luokittelun", yksikko="luokitusta", tulokset="luokitukset", oletus_erakoko="30",
        aja_testierat=testierat.aja_testierat, testiera_raportti=_testiera_raportti,
        hae_ajot=testimallit.hae_testiajot_luokittelu,
        ajon_rivi=lambda a: (f"{a['Ajo']}  —  {a['Rivit']} kurssia (mukana {a['Mukana']}), "
                             f"eräkoko {a['Erakoko']}, {a['Malli'] or '?'}"),
        ajon_koko=lambda a: f"{a['Rivit']} kurssia",
        siirra=testimallit.siirra_testiajo_luokittelu, poista=testimallit.poista_testiajo_luokittelu,
        asetukset=asetuseditori.LUOKITTELU_ASETUKSET,
        ei_eria="Ei eriä ajettu (ei luokittelemattomia kursseja?).",
    )


def nayta(stdscr) -> None:
    tutkimus = valitse_tutkimus(stdscr, "Luokittele — valitse tutkimus")
    if tutkimus is not None:
        _luokittele(stdscr, tutkimus)


def _luokittele(stdscr, tutkimus: dict) -> None:
    toiminnot = [
        ("Aja meta-suodatus", _aja_meta),
        ("Aja LLM-luokittelu", _aja_llm),
        ("Aja LLM-testierä kirjaten tilastot", lambda s, t: llmvaihe.aja_testiera(s, t, _vaihe())),
        ("Muokkaa LLM-luokittelun asetuksia", lambda s, t: llmvaihe.muokkaa_asetukset(s, t, _vaihe())),
        ("Siirrä testiajo varsinaiseen aineistoon", lambda s, t: llmvaihe.siirra_testiajo(s, t, _vaihe())),
        ("Poista testiajo", lambda s, t: llmvaihe.poista_testiajo(s, t, _vaihe())),
        ("Näytä tilanne", _nayta_tilanne),
    ]
    toimintovalikko(stdscr, f"Luokittele — {tutkimus['LuokittelunNimi']}", toiminnot, tutkimus)


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
    from tietokanta import testimallit
    piirra_otsikko(stdscr, f"LLM-luokittelu — {tutkimus['LuokittelunNimi']}")

    tid = tutkimus["TID"]
    tiiv = llmluokittelu.laske_tiiviste(tutkimus)

    # Varoita siirtämättömistä testiajoista: ne käsiteltäisiin nyt uudelleen
    # (tokeneita hukkaan), ellei niitä siirretä ensin varsinaiseen aineistoon.
    siirrettavat = testimallit.hae_siirrettavat_ajot_luokittelu(tid, tiiv)
    if not llmvaihe.kasittele_siirrettavat(stdscr, _vaihe(), siirrettavat):
        return
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
    if (tutkimus.get("Luokittelukehote") or "").strip() and not llmvaihe.malli_kaytettavissa(stdscr):
        return

    # Tyhjennä vahvistusvalikon / testiajovaroituksen jäänteet ennen ajonäkymää.
    piirra_otsikko(stdscr, f"LLM-luokittelu — {tutkimus['LuokittelunNimi']}")
    # Ensin haetaan ehdokkaat kannasta — LLM-kutsut alkavat vasta sen jälkeen.
    # Vanha teksti ("Yhdistetään LLM:ään") ohjasi etsimään vikaa väärästä paikasta,
    # kun jumi oli tosiasiassa tässä tietokantakyselyssä.
    stdscr.addstr(3, 0, "Haetaan luokiteltavat kurssit tietokannasta...")
    stdscr.refresh()

    keskeytetty = [False]
    ctrl_s_kaytossa = [False]

    def rivi(nro: int, teksti: str) -> None:
        stdscr.addstr(nro, 0, teksti)
        stdscr.clrtoeol()

    # jaljella = vielä ilman päätöstä olevat, EI virheitä: ajon alussa se on koko
    # loppujoukko ja kutistuu nollaan. Epäonnistuneet ovat tämän passin virheet
    # (menetetyt erät + vastauksetta jääneet kurssit) — ne sisältyvät jäljellä-
    # lukuun, koska seuraava passi yrittää ne uudelleen.
    def edistyminen(n, yht, erä, erat, mukana, hylätty, jaljella, tilasto):
        me, mk, iv = tilasto["menetetyt_erat"], tilasto["menetetyt_kurssit"], tilasto["ilman_vastausta"]
        osuus = f"  ({mukana / (mukana + hylätty) * 100:.0f} %)" if (mukana + hylätty) else ""
        syyt = []
        if me:
            syyt.append(f"{me} erä{'ä' if me != 1 else ''} menetetty, {mk} kurssia")
        if iv:
            syyt.append(f"{iv} kurssi{'a' if iv != 1 else ''} ilman vastausta")
        selite = f"  ({', '.join(syyt)})" if syyt else ""

        rivi(3, f"  Erä {erä}/{erat} — {n}/{yht} kurssia käsitelty")
        rivi(4, "")
        for i, (nimi, luku, lisa) in enumerate((
            ("Mukaan:", mukana, osuus),
            ("Hylätty:", hylätty, ""),
            ("Jäljellä:", jaljella, ""),
            ("Epäonnistui:", mk + iv, selite),
        )):
            rivi(5 + i, f"  {nimi:<12}{luku:>5}{lisa}")
        rivi(9, "  Harkitse eräkoon pienentämistä (LUOKITTELU_ERAKOKO)." if me else "")
        if ctrl_s_kaytossa[0]:
            rivi(11, " Paina ctrl-s keskeyttääksesi ajon (jo tehtyjä luokitteluja ei menetetä!) ja muokataksesi asetuksia")
        stdscr.refresh()
        if ctrl_s_kaytossa[0] and stdscr.getch() == 19:  # ctrl-s
            keskeytetty[0] = True
            return True
        return False

    # ctrl-s pitää saada ajon aikana getch:lle: nodelay tekee pollauksesta
    # estämättömän, ja IXON pois estää päätettä nielemästä ctrl-s:ää virtaus-
    # kontrollina. Molemmat palautetaan finally-lohkossa. Jos stdin ei ole aito
    # pääte (esim. testit), keskeytys jää pois käytöstä mutta ajo etenee normaalisti.
    import sys, termios
    fd = vanha_termios = None
    try:
        fd = sys.stdin.fileno()
        vanha_termios = termios.tcgetattr(fd)
        muokattu = termios.tcgetattr(fd)
        muokattu[0] &= ~termios.IXON
        termios.tcsetattr(fd, termios.TCSANOW, muokattu)
        stdscr.nodelay(True)
        ctrl_s_kaytossa[0] = True
    except Exception:
        fd = vanha_termios = None  # ctrl-s pois päältä; getch ei kysele
    try:
        mukana, hylätty, luokittelematta = llmluokittelu.aja(tutkimus, edistyminen)
    except EnvironmentError as e:
        nayta_viesti(stdscr, f"Virhe: {e}")
        return
    except Exception as e:
        nayta_viesti(stdscr, f"LLM-virhe: {e}")
        return
    finally:
        if vanha_termios is not None:
            stdscr.nodelay(False)
            termios.tcsetattr(fd, termios.TCSANOW, vanha_termios)

    if keskeytetty[0]:
        piirra_otsikko(stdscr, "LLM-luokittelu — keskeytetty")
        stdscr.addstr(3, 0, f"Mukaan otettu: {mukana}   Hylätty: {hylätty}")
        stdscr.addstr(4, 0, "Jo tehdyt luokitukset on tallennettu — työ jatkuu mihin jäi.")
        stdscr.addstr(5, 0, "Muokkaa asetuksia (esim. eräkoko) ja aja uudelleen.")
        nayta_viesti(stdscr, "", 7)
        return

    piirra_otsikko(stdscr, "LLM-luokittelu — valmis")
    stdscr.addstr(3, 0, f"Mukaan otettu: {mukana}")
    stdscr.addstr(4, 0, f"Hylätty:       {hylätty}")
    if luokittelematta:
        stdscr.addstr(5, 0, f"Luokittelematta jäi: {luokittelematta} (LLM ei antanut päätöstä — pienennä LUOKITTELU_ERAKOKO)")
    nayta_viesti(stdscr, "", 7)


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


def _nayta_tilanne(stdscr, tutkimus: dict) -> None:
    tid = tutkimus["TID"]
    t = mallit.hae_tutkimuksen_tilanne(tid)
    arvioimattomat = mallit.laske_arvioimattomat(tid)
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
