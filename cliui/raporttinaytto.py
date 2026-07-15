"""Raporttinäkymä: LLM-raportin generointi tutkimukselle."""
import threading
from tietokanta import mallit
from cliui.apurit import piirra_otsikko, nayta_viesti, valitse_listasta

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
    toiminnot = [
        ("Generoi raportti LLM:llä", _generoi),
        ("Näytä tilanne", _nayta_tilanne),
        ("Tarkista tuoreus nyt", _tarkista_tuoreus),
    ]
    while True:
        valinta = valitse_listasta(
            stdscr,
            f"Raportti — {tutkimus['LuokittelunNimi']}",
            [nimi for nimi, _ in toiminnot],
        )
        if valinta is None:
            return
        toiminnot[valinta][1](stdscr, tutkimus)


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
    if tilanne["hitl_jalkeen"] or tilanne["kommentit_jalkeen"]:
        stdscr.addstr(rivi, 0, f"  Generoinnin jälkeen: {tilanne['hitl_jalkeen']} HITL-korjausta, "
                               f"{tilanne['kommentit_jalkeen']} kommenttia")
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
