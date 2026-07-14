"""LLM-raporttigenerointi: koostaa raporttiosiot tietokannasta ja täydentää LLM:llä."""
import os
from tietokanta import mallit
from llm import kutsu

OSIOT = ["johdanto", "kurssit", "arvioinnit"]


def _lue_jarjestelmakehote() -> str:
    polku = os.path.join(os.path.dirname(__file__), "..", "kehotteet", "raporttijarjestelma.txt")
    with open(polku, encoding="utf-8") as f:
        return f.read().strip()


def _tilasto_taulukko(rivit: list[dict]) -> str:
    otsikko = f"{'Yliopisto':<40} {'Kursseja':>10} {'LLM käsitelty':>15} {'Mukana':>8} {'Hylätty':>9} {'HITL':>6}"
    viiva = "-" * len(otsikko)
    rivit_txt = [otsikko, viiva]
    for r in rivit:
        rivit_txt.append(
            f"{r['KouluNimi']:<40} {r['KurssiYhteensa']:>10} {r['LLMKasitelty']:>15}"
            f" {r['Mukana']:>8} {r['Hylatty']:>9} {r['HitlLkm']:>6}"
        )
    return "\n".join(rivit_txt)


def _rakenna_johdanto_viesti(tutkimus: dict, tilastot: list[dict]) -> str:
    mukana_yht = sum(r["Mukana"] for r in tilastot)
    kurssit_yht = sum(r["KurssiYhteensa"] for r in tilastot)
    yliopistojen_lkm = len([r for r in tilastot if r["KurssiYhteensa"] > 0])
    raportointikehote = tutkimus.get("Raportointikehote") or ""
    return f"""Kirjoita tutkimusraportin johdanto-osio seuraavien tietojen pohjalta.

Tutkimuksen nimi: {tutkimus['LuokittelunNimi']}
Raportointikehote (tutkimuksen taustaohje): {raportointikehote or '(ei annettu)'}

Yleistilastot:
- Tarkasteltuja yliopistoja: {yliopistojen_lkm}
- Kursseja tietokannassa yhteensä: {kurssit_yht}
- LLM:n mukaan ottamia kursseja: {mukana_yht}

Tasorajaus: {tutkimus.get('Tasorajaus') or '(kaikki tasot)'}
Oppiainerajaus: {tutkimus.get('Oppiainerajaus') or '(kaikki oppiaineet)'}

Kirjoita johdanto, joka esittelee tutkimuksen aiheen, tavoitteen ja laajuuden.
Mainitse tarkasteltujen yliopistojen ja kurssien määrät."""


def _rakenna_kurssit_viesti(tutkimus: dict, tilastot: list[dict]) -> str:
    mukana_yht = sum(r["Mukana"] for r in tilastot)
    kurssit_yht = sum(r["KurssiYhteensa"] for r in tilastot)
    hitl_yht = sum(r["HitlLkm"] for r in tilastot)
    raportointikehote = tutkimus.get("Raportointikehote") or ""
    return f"""Kirjoita tutkimusraportin kurssit-osio seuraavien tietojen pohjalta.

Tutkimuksen nimi: {tutkimus['LuokittelunNimi']}
Raportointikehote: {raportointikehote or '(ei annettu)'}

Valintakehote (ohje LLM:lle kurssin valinnassa):
{tutkimus['Luokittelukehote']}

Suodatusperusteet:
- Tasorajaus: {tutkimus.get('Tasorajaus') or 'kaikki tasot'}
- Oppiainerajaus: {tutkimus.get('Oppiainerajaus') or 'kaikki oppiaineet'}

Yliopistokohtaiset tilastot:
{_tilasto_taulukko(tilastot)}

Yhteenveto:
- Kursseja tietokannassa yhteensä: {kurssit_yht}
- LLM:n valitsemia kursseja: {mukana_yht}
- Manuaalisia HITL-korjauksia: {hitl_yht}

Kirjoita osio, joka esittelee kurssihaun suodatusperusteet, valintakehotteen tarkoituksen
sekä kuvaa yliopistokohtaiset tulokset ja yhteenvedon."""


def _rakenna_arvioinnit_viesti(tutkimus: dict, kysymykset: list[dict], tilastot: list[dict]) -> str:
    mukana_yht = sum(r["Mukana"] for r in tilastot)
    kommentit_lkm = len(mallit.hae_arviokommentit_kaikki(tutkimus["TID"]))
    kysymysteksti = "\n".join(f"{i+1}. {k['Kysymys']}" for i, k in enumerate(kysymykset))
    raportointikehote = tutkimus.get("Raportointikehote") or ""
    return f"""Kirjoita tutkimusraportin arvioinnit-osio seuraavien tietojen pohjalta.

Tutkimuksen nimi: {tutkimus['LuokittelunNimi']}
Raportointikehote: {raportointikehote or '(ei annettu)'}

Arviointikehote (ohje LLM:lle kurssin arvioinnissa):
{tutkimus['Arviointikehote']}

Arviointikysymykset ({len(kysymykset)} kpl):
{kysymysteksti or '(ei kysymyksiä)'}

Arvioitujen kurssien määrä: {mukana_yht}
Ihmisten tekemien kommenttien määrä: {kommentit_lkm}

Kirjoita osio, joka esittelee arviointimenetelmän, käytetyt kysymykset ja kuvaa
arvioinnin laajuuden sekä ihmisten tekemien korjausten merkityksen."""


def aja(tutkimus: dict, edistyminen_cb=None) -> int:
    """Generoi raporttiosiot LLM:llä ja tallentaa ne tietokantaan.

    Palauttaa generoitujen osioiden määrän. Idempotentti — korvaa olemassa olevat.
    """
    tid = tutkimus["TID"]
    jarjestelma = _lue_jarjestelmakehote()
    tilastot = mallit.hae_tilastot_yliopistoittain(tid)
    kysymykset = mallit.hae_kysymykset(tid)

    viestirakentajat = {
        "johdanto": lambda: _rakenna_johdanto_viesti(tutkimus, tilastot),
        "kurssit": lambda: _rakenna_kurssit_viesti(tutkimus, tilastot),
        "arvioinnit": lambda: _rakenna_arvioinnit_viesti(tutkimus, kysymykset, tilastot),
    }

    generoitu = 0
    for i, avain in enumerate(OSIOT):
        if edistyminen_cb:
            edistyminen_cb(i, len(OSIOT), avain)
        viesti = viestirakentajat[avain]()
        teksti = kutsu.kysy(viesti, jarjestelma)
        mallit.aseta_raportti_osio(tid, avain, teksti)
        generoitu += 1

    if edistyminen_cb:
        edistyminen_cb(len(OSIOT), len(OSIOT), "valmis")
    return generoitu
