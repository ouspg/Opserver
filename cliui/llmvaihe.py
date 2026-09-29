"""LLM-vaiheiden (luokittelu, arviointi) yhteiset näkymät: testierä, testiajojen
siirto/poisto, siirtämättömien testiajojen varoitus, asetukset ja mallitarkistus.

Vaiheen erot kuvataan Vaihe-oliolla (näyttöteksti, testimallit-funktiot)."""
from dataclasses import dataclass
from typing import Callable

from cliui.apurit import piirra_otsikko, nayta_viesti, valitse_listasta, lue_teksti


@dataclass
class Vaihe:
    nimi: str                     # genetiivissä: "luokittelun" / "arvioinnin"
    yksikko: str                  # partitiivissa: "luokitusta" / "vastausta"
    tulokset: str                 # monikossa: "luokitukset" / "vastaukset"
    oletus_erakoko: str
    aja_testierat: Callable       # (tutkimus, erakoko, montako, edistyminen_cb) -> dict
    testiera_raportti: Callable   # (tulos, erakoko) -> list[str]
    hae_ajot: Callable            # (tid) -> list[dict]
    ajon_rivi: Callable           # (ajo) -> str valintalistaan
    ajon_koko: Callable           # (ajo) -> str, esim. "12 kurssia"
    siirra: Callable              # (ajo_id) -> int
    poista: Callable              # (ajo_id) -> int
    asetukset: list
    ei_eria: str                  # viesti kun testierässä ei ollut ajettavaa


def malli_kaytettavissa(stdscr) -> bool:
    """Esitarkistus ennen LLM-kutsuja: malli on saatavilla."""
    from llm import mallitiedot
    try:
        mallitiedot.tarkista_saatavuus()
        return True
    except Exception as e:
        nayta_viesti(stdscr, f"Mallia ei voi käyttää: {e}")
        return False


def kasittele_siirrettavat(stdscr, vaihe: Vaihe, siirrettavat: list[str]) -> bool:
    """Varoittaa siirtämättömistä testiajoista (ne käsiteltäisiin uudelleen, tokeneita
    hukkaan) ja siirtää ne pyydettäessä. False = käyttäjä peruutti."""
    if not siirrettavat:
        return True
    valinta = valitse_listasta(
        stdscr,
        f"Siirtämättömiä testiajoja: {len(siirrettavat)} — niiden {vaihe.tulokset} käsiteltäisiin uudelleen",
        [
            "Siirrä testiajot ensin (säästää tokeneita)",
            "Aja silti (testiajot käsitellään uudelleen)",
            "Peruuta",
        ],
    )
    if valinta is None or valinta == 2:
        return False
    if valinta == 0:
        siirretty = sum(vaihe.siirra(a) for a in siirrettavat)
        nayta_viesti(stdscr, f"Siirretty {siirretty} {vaihe.yksikko} {len(siirrettavat)} testiajosta.")
    return True


def _kysy_luvut(stdscr, otsikko: str, oletus_erakoko: str) -> tuple[int, int] | None:
    """Kysyy eräkoon ja erien määrän. Palauttaa (erakoko, montako) tai None."""
    piirra_otsikko(stdscr, otsikko)
    erakoko_s = lue_teksti(stdscr, "Eräkoko (kursseja per LLM-kutsu)", 3, oletus_erakoko)
    montako_s = lue_teksti(stdscr, "Montako erää ajetaan", 4, "3")
    try:
        erakoko, montako = int(erakoko_s), int(montako_s)
        if erakoko < 1 or montako < 1:
            raise ValueError
    except ValueError:
        nayta_viesti(stdscr, "Kelvottomat luvut — anna positiiviset kokonaisluvut.")
        return None
    return erakoko, montako


def aja_testiera(stdscr, tutkimus: dict, vaihe: Vaihe) -> None:
    otsikko = f"LLM-testierä — {tutkimus['LuokittelunNimi']}"
    luvut = _kysy_luvut(stdscr, otsikko, vaihe.oletus_erakoko)
    if luvut is None or not malli_kaytettavissa(stdscr):
        return
    erakoko, montako = luvut

    piirra_otsikko(stdscr, otsikko)
    stdscr.addstr(3, 0, f"Ajetaan {montako} × {erakoko} kurssia...")
    stdscr.refresh()

    def edistyminen(era_nro, erat):
        stdscr.addstr(4, 0, f"  Erä {era_nro}/{erat} käsitelty")
        stdscr.refresh()

    try:
        tulos = vaihe.aja_testierat(tutkimus, erakoko, montako, edistyminen)
    except Exception as e:
        nayta_viesti(stdscr, f"Virhe testierässä: {e}")
        return
    if not tulos["tietueet"]:
        nayta_viesti(stdscr, vaihe.ei_eria)
        return

    valinta = valitse_listasta(
        stdscr,
        "LLM-testierä valmis — siirretäänkö tulokset varsinaiseen aineistoon?",
        ["Siirrä varsinaiseen aineistoon", "Älä siirrä (säilyy testiajona)"],
        kiintea_otsikko=vaihe.testiera_raportti(tulos, erakoko),
    )
    if valinta == 0:
        siirretty = vaihe.siirra(tulos["ajo_id"])
        nayta_viesti(stdscr, f"Siirretty {siirretty} {vaihe.yksikko} varsinaiseen aineistoon (ajo {tulos['ajo_id']}).")
    else:
        nayta_viesti(stdscr, f"Ei siirretty. Testiajo {tulos['ajo_id']} säilyy (siirrä/poista myöhemmin valikosta).")


def muokkaa_asetukset(stdscr, tutkimus: dict, vaihe: Vaihe) -> None:
    from cliui import asetuseditori
    asetuseditori.muokkaa_asetuksia(
        stdscr, f"LLM-{vaihe.nimi} asetukset — {tutkimus['LuokittelunNimi']}", vaihe.asetukset,
    )


def _valitse_testiajo(stdscr, tutkimus: dict, vaihe: Vaihe, otsikko: str):
    ajot = vaihe.hae_ajot(tutkimus["TID"])
    if not ajot:
        nayta_viesti(stdscr, f"Ei {vaihe.nimi} testiajoja tälle tutkimukselle.")
        return None
    valinta = valitse_listasta(stdscr, otsikko, [vaihe.ajon_rivi(a) for a in ajot])
    return ajot[valinta] if valinta is not None else None


def siirra_testiajo(stdscr, tutkimus: dict, vaihe: Vaihe) -> None:
    ajo = _valitse_testiajo(stdscr, tutkimus, vaihe, "Siirrä testiajo varsinaiseen aineistoon — valitse")
    if ajo is None:
        return
    varmistus = valitse_listasta(
        stdscr, f"Siirrä ajo {ajo['Ajo']} ({vaihe.ajon_koko(ajo)}) varsinaiseen aineistoon?",
        [f"Siirrä — korvaa näiden kurssien aiemmat {vaihe.tulokset}", "Peruuta"],
    )
    if varmistus != 0:
        return
    siirretty = vaihe.siirra(ajo["Ajo"])
    nayta_viesti(stdscr, f"Siirretty {siirretty} {vaihe.yksikko} varsinaiseen aineistoon (ajo {ajo['Ajo']}).")


def poista_testiajo(stdscr, tutkimus: dict, vaihe: Vaihe) -> None:
    ajo = _valitse_testiajo(stdscr, tutkimus, vaihe, "Poista testiajo — valitse")
    if ajo is None:
        return
    varmistus = valitse_listasta(
        stdscr, f"Poista testiajo {ajo['Ajo']}?",
        [f"Poista {vaihe.ajon_koko(ajo)} lopullisesti", "Peruuta"],
    )
    if varmistus != 0:
        return
    poistettu = vaihe.poista(ajo["Ajo"])
    nayta_viesti(stdscr, f"Poistettu {poistettu} riviä (ajo {ajo['Ajo']}).")
