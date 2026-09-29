"""Arvioinnin testierä-mittaus: ajaa muutaman erän valitulla eräkoolla,
kirjaa tulokset kantaan (testitauluun) ja tilastot vertailua varten.

Sama malli kuin luokittelun testierissä: tulokset talletetaan
Vastaukset_testi-tauluun ajotunnuksella (Ajo), jotta LLM-kutsuja ei haaskata ja
kukin testiajo voidaan poistaa kohdennetusti. Tilastot kirjataan append-only
JSONL-tiedostoon, joten uusi ajo ei pyyhi aiempia.
"""
import random
import time
from datetime import datetime

from tietokanta import testimallit
from llm import kutsu, kurssimuoto, erakutsu
from arviointi import llmarviointi

TILASTOPOLKU = "testitulokset/arviointi_testierat.jsonl"


def _mittaa_era(era: list[dict], arviointikehote: str, kysymykset: list[dict],
                jarjestelma: str) -> tuple[dict, list[dict]]:
    """Lähettää yhden erän LLM:lle kuten tuotantoajo. Palauttaa (mittaustiedot, tulokset)."""
    vakaa_prefix = llmarviointi._vakaa_prefix(arviointikehote, kysymykset)
    viesti = erakutsu.rakenna_viesti(era, vakaa_prefix)
    alku = time.monotonic()
    try:
        tulokset, jasennys = erakutsu.kysy_json(viesti, jarjestelma, vakaa_prefix,
                                                llmarviointi._erittele_json, llmarviointi._UUSINTAOHJE,
                                                json_muoto=True)
    except Exception:
        tulokset, jasennys = [], "epaonnistui"
    kesto = time.monotonic() - alku

    mittaus = {
        "kursseja_lahetetty": len(era),
        "kysymyksia": len(kysymykset),
        "tuloksia_saatu": len(tulokset),
        "pudonneet": len(era) - len(tulokset),
        "jasennys": jasennys,
        "kesto_s": round(kesto, 2),
        **erakutsu.token_mittaus(),
    }
    return mittaus, tulokset


def _tallenna_testitulokset(tulokset, kysymykset, ajo_id, erakoko, tid, malli,
                            kys_tiiviste, lahetetyt) -> None:
    """Kirjaa (kurssi, kysymys) -vastaukset testitauluun ajotunnuksella."""
    siivotut = kurssimuoto.siivoa_tulokset(tulokset, lahetetyt)
    for kid, k, vastaus, pisteet, luokka, lista in llmarviointi.pura_tulokset(siivotut, kysymykset):
        testimallit.aseta_testivastaus(
            ajo=ajo_id, erakoko=erakoko, tid=tid, kysid=k["KysID"], kid=kid,
            vastaus=vastaus, malli=malli, pisteet=pisteet, luokka=luokka,
            lista=lista, tiiviste=(kys_tiiviste or {}).get(k["KysID"]),
        )


def aja_testierat(tutkimus: dict, erakoko: int, montako_era: int,
                  edistyminen_cb=None, tilastopolku: str | None = None) -> dict:
    """Ajaa enintään `montako_era` erää kooltaan `erakoko`, kirjaa tulokset kantaan
    (testitauluun, ajotunnuksella) ja tilastot tiedostoon. Palauttaa yhteenvedon."""
    polku = tilastopolku or TILASTOPOLKU
    tid = tutkimus["TID"]
    tieto = llmarviointi._selvita_tyo(tutkimus)
    ajo_id = datetime.now().strftime("%Y%m%dT%H%M%S")
    if not tieto["tyo"]:
        return {"ajo_id": ajo_id, "eria": 0, "tilastopolku": polku, "tietueet": []}

    arviointikehote = tieto["arviointikehote"]
    jarjestelma = tieto["jarjestelma"]
    kys_tiiviste = tieto["kys_tiiviste"]
    malli = kutsu.hae_malli()

    # Satunnaisotos työn alla olevista kursseista ilman takaisinpanoa → sama
    # kurssi ei voi osua kahteen erään. Ryhmittely kysymysjoukon mukaan säilyy.
    tyo_kohteet = list(tieto["tyo"].keys())
    valitut = set(random.sample(tyo_kohteet, min(erakoko * montako_era, len(tyo_kohteet))))
    tieto["tyo"] = {kid: v for kid, v in tieto["tyo"].items() if kid in valitut}
    erat = llmarviointi.rakenna_erat(tieto, erakoko)[:montako_era]
    tietueet = []
    for era_nro, (osa_kysymykset, era) in enumerate(erat, 1):
        mittaus, tulokset = _mittaa_era(era, arviointikehote, osa_kysymykset, jarjestelma)

        lahetetyt = {k["KID"] for k in era}
        _tallenna_testitulokset(tulokset, osa_kysymykset, ajo_id, erakoko, tid,
                                malli, kys_tiiviste, lahetetyt)

        tietue = erakutsu.testitietue(ajo_id, tutkimus, malli, erakoko, era_nro, len(erat), mittaus)
        erakutsu.kirjaa_jsonl(polku, tietue)
        tietueet.append(tietue)
        if edistyminen_cb:
            edistyminen_cb(era_nro, len(erat))

    return {"ajo_id": ajo_id, "eria": len(erat), "tilastopolku": polku, "tietueet": tietueet}
