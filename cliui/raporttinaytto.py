"""Raporttinäkymä: LLM-raportin generointi tutkimukselle."""
import threading
from cliui.apurit import kirjoita_rivi, piirra_otsikko, nayta_viesti
from cliui.ehdotusnaytto import kuittaa_ehdotukset
from cliui.valikot import toimintovalikko, valitse_tutkimus

# Tuoreuslaskenta on raskas (per-yliopisto-tilastot + kaikki vastaukset etäkannasta),
# joten se ajetaan taustasäikeessä eikä status-katselun kriittisellä polulla.
# Lippu estää päällekkäiset taustapäivitykset (yksi kerrallaan riittää).
_tuoreus_lukko = threading.Lock()
_tuoreus_kaynnissa = False


def _kaynnista_taustatuoreus(tutkimus: dict) -> None:
    """Käynnistää tuoreuslaskennan daemon-säikeessä, jos yksikään ei ole käynnissä.
    Ei kosketa curses-näyttöön (säie ei saa kirjoittaa stdscr:ään) — tulos näkyy
    seuraavalla 'Näytä tilanne' -avauksella."""
    from raportti import llmraportti
    global _tuoreus_kaynnissa
    with _tuoreus_lukko:
        if _tuoreus_kaynnissa:
            return
        _tuoreus_kaynnissa = True

    def aja():
        global _tuoreus_kaynnissa
        try:
            llmraportti.paivita_tuoreus(tutkimus)
        except Exception:
            pass  # parhaan yrityksen mukaan; UI ei riipu taustapäivityksestä
        finally:
            with _tuoreus_lukko:
                _tuoreus_kaynnissa = False

    threading.Thread(target=aja, daemon=True).start()


def nayta(stdscr) -> None:
    tutkimus = valitse_tutkimus(stdscr, "Tee raportti — valitse tutkimus")
    if tutkimus is not None:
        _raportti(stdscr, tutkimus)


def _raportti(stdscr, tutkimus: dict) -> None:
    toiminnot = [
        ("Generoi raportti LLM:llä", _generoi),
        ("Näytä tilanne", _nayta_tilanne),
        ("Tarkista tuoreus nyt", _tarkista_tuoreus),
    ]
    toimintovalikko(stdscr, f"Raportti — {tutkimus['LuokittelunNimi']}", toiminnot, tutkimus)


def _tila(stdscr, otsikko: str, teksti: str) -> None:
    piirra_otsikko(stdscr, otsikko)
    kirjoita_rivi(stdscr, 3, teksti)
    stdscr.refresh()


def _normalisoi_listat(stdscr, tutkimus: dict) -> int | None:
    """Lista-tyypin kysymysten arvojen yhdistäminen ennen raporttia: aiemmin
    hyväksytyt automaattisesti, sitten a) kirjainkoko ja b) LLM:n synonyymit
    käyttäjän kuittaamina. Palauttaa muuttuneiden vastausrivien määrän, None jos
    käyttäjä peruutti (kuitatut vaiheet ovat jo tallessa, peruttu ei)."""
    from raportti import listanormalisointi as ln, listasynonyymit as ls
    tid = tutkimus["TID"]
    otsikko = f"Lista-arvojen yhdistäminen — {tutkimus['LuokittelunNimi']}"
    kysymykset = ln.lista_kysymykset(tid)
    if not kysymykset:
        return 0
    _tila(stdscr, otsikko, "Sovelletaan aiemmin hyväksyttyjä yhdistämisiä...")
    muuttui = ln.sovella_tallennetut(tid)

    _tila(stdscr, otsikko, "Etsitään kirjainkokoeroja...")
    ehdotukset = ln.kirjainkoko_ehdotukset(tid, kysymykset)
    if ehdotukset:
        kuitatut = kuittaa_ehdotukset(stdscr, f"a) Kirjainkokoerot — {tutkimus['LuokittelunNimi']}", ehdotukset)
        if kuitatut is None:
            return None
        muuttui += ln.tallenna_kuittaus(tid, kuitatut)

    _tila(stdscr, otsikko, "Kysytään LLM:ltä synonyymejä...")

    def edistyminen(i, yht, kysymys):
        kirjoita_rivi(stdscr, 4, f"  Kysymys {i + 1}/{yht}: {kysymys}")
        stdscr.refresh()

    ehdotukset, lahetetyt, virheet = ls.synonyymiehdotukset(tid, kysymykset, edistyminen)
    if virheet:
        piirra_otsikko(stdscr, otsikko)
        nayta_viesti(stdscr, "LLM-vastaus jäi osin jäsentymättä (kysytään uudelleen ensi kerralla): "
                     + "; ".join(virheet), 3)
    kuitatut = []
    if ehdotukset:
        kuitatut = kuittaa_ehdotukset(stdscr, f"b) Synonyymit (LLM) — {tutkimus['LuokittelunNimi']}", ehdotukset)
        if kuitatut is None:
            return None
    return muuttui + ln.tallenna_kuittaus(tid, kuitatut, lahetetyt, ls.lue_kehote())


def _generoi(stdscr, tutkimus: dict) -> None:
    from raportti import llmraportti
    try:
        muuttui = _normalisoi_listat(stdscr, tutkimus)
    except EnvironmentError as e:
        nayta_viesti(stdscr, f"Virhe: {e}")
        return
    except Exception as e:
        nayta_viesti(stdscr, f"Lista-arvojen yhdistäminen epäonnistui: {e}")
        return
    if muuttui is None:
        piirra_otsikko(stdscr, f"Raportti — {tutkimus['LuokittelunNimi']}")
        nayta_viesti(stdscr, "Keskeytetty — raporttia ei generoitu.", 3)
        return
    piirra_otsikko(stdscr, f"Raportti — {tutkimus['LuokittelunNimi']}")
    if muuttui:
        stdscr.addstr(2, 0, f"Lista-arvoja yhdistetty {muuttui} vastauksessa.")
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


_TUOREUS_TEKSTI = {
    "ajan_tasalla": "✓ Ajan tasalla — lähdeaineisto ei ole muuttunut generoinnin jälkeen.",
    "vanhentunut": "⚠ Vanhentunut — lähdeaineisto on muuttunut generoinnin jälkeen. Generoi uudelleen.",
    "tuntematon": "? Tuoreus tuntematon — ei vielä laskettu tai generoitu ennen tuoreusseurantaa.",
}


def _piirra_tilanne(stdscr, tilanne: dict) -> int:
    """Piirtää raportin tilannelohkon; palauttaa seuraavan vapaan rivin.
    Näyttää tuoreuden VIIMEKSI LASKETUN tuloksen + laskenta-ajan — ei laske sitä
    tässä (raskas laskenta on taustalla / 'Tarkista tuoreus nyt')."""
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
    tarkistettu = tilanne.get("tarkistettu")
    tark_teksti = f"Tuoreus tarkistettu: {_aika_str(tarkistettu)}" if tarkistettu \
        else "Tuoreutta ei ole vielä tarkistettu."
    stdscr.addstr(rivi, 0, f"  {tark_teksti}")
    rivi += 1
    if tilanne["hitl_jalkeen"] or tilanne["arviokorjaukset_jalkeen"]:
        stdscr.addstr(rivi, 0, f"  Generoinnin jälkeen: {tilanne['hitl_jalkeen']} luokituskorjausta, "
                               f"{tilanne['arviokorjaukset_jalkeen']} arviokorjausta")
        rivi += 1
    return rivi


def _nayta_tilanne(stdscr, tutkimus: dict) -> None:
    from raportti import llmraportti
    tilanne = llmraportti.koosta_tilanne(tutkimus)
    piirra_otsikko(stdscr, f"Raportin tilanne — {tutkimus['LuokittelunNimi']}")
    if not tilanne["generoitu"]:
        nayta_viesti(stdscr, "Raporttia ei ole vielä generoitu.")
        return
    rivi = _piirra_tilanne(stdscr, tilanne)
    # Käynnistä raskas tuoreuslaskenta taustalla → seuraava avaus näyttää tuoreen
    # tuloksen ilman että tämä katselu jäätyy sen ajaksi.
    _kaynnista_taustatuoreus(tutkimus)
    stdscr.addstr(rivi + 1, 0, "(tuoreus päivitetään taustalla)")
    nayta_viesti(stdscr, "", rivi + 3)


def _tarkista_tuoreus(stdscr, tutkimus: dict) -> None:
    """Laskee tuoreuden HETI (synkronisesti) käyttäjän pyynnöstä ja näyttää
    päivitetyn tilanteen. Raskas — voi kestää etäkantaa vasten."""
    from raportti import llmraportti
    piirra_otsikko(stdscr, f"Raportin tilanne — {tutkimus['LuokittelunNimi']}")
    if not llmraportti.koosta_tilanne(tutkimus)["generoitu"]:
        nayta_viesti(stdscr, "Raporttia ei ole vielä generoitu.")
        return
    stdscr.addstr(3, 0, "Lasketaan tuoreutta (voi kestää hetken)...")
    stdscr.refresh()
    try:
        llmraportti.paivita_tuoreus(tutkimus)
    except Exception as e:
        nayta_viesti(stdscr, f"Tuoreuslaskenta epäonnistui: {e}")
        return
    tilanne = llmraportti.koosta_tilanne(tutkimus)
    piirra_otsikko(stdscr, f"Raportin tilanne — {tutkimus['LuokittelunNimi']}")
    rivi = _piirra_tilanne(stdscr, tilanne)
    nayta_viesti(stdscr, "", rivi + 1)
