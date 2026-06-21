"""Arvioinnin testierä-mittaus: ajaa muutaman erän valitulla eräkoolla,
kirjaa tulokset kantaan (testitauluun) ja tilastot vertailua varten.

Sama malli kuin luokittelun testierissä: tulokset talletetaan
Vastaukset_testi-tauluun ajotunnuksella (Ajo), jotta LLM-kutsuja ei haaskata ja
kukin testiajo voidaan poistaa kohdennetusti. Tilastot kirjataan append-only
JSONL-tiedostoon, joten uusi ajo ei pyyhi aiempia.
"""
import json
import os
import time
from datetime import datetime

from tietokanta import testimallit
from llm import kutsu, kurssimuoto, asetukset
from arviointi import llmarviointi

TILASTOPOLKU = "testitulokset/arviointi_testierat.jsonl"


def _mittaa_era(era: list[dict], arviointikehote: str, kysymykset: list[dict],
                jarjestelma: str) -> tuple[dict, list[dict]]:
    """Lähettää yhden erän LLM:lle. Palauttaa (mittaustiedot, jäsennetyt tulokset)."""
    kurssit_json = json.dumps(
        [kurssimuoto.kurssi_json_promptiin(k) for k in era],
        ensure_ascii=False,
        indent=2,
    )
    kysymysteksti = llmarviointi._rakenna_kysymysteksti(kysymykset)
    vakaa_prefix = f"{arviointikehote}\n\n{kysymysteksti}\n\nArvioi seuraavat kurssit:\n"
    viesti = f"{vakaa_prefix}{kurssit_json}"

    alku = time.monotonic()
    jasennys = "ok"
    tulokset: list[dict] = []
    try:
        vastaus = kutsu.kysy(viesti, jarjestelma, json_muoto=True, vakaa_prefix=vakaa_prefix)
        try:
            tulokset = llmarviointi._erittele_json(vastaus)
        except (ValueError, json.JSONDecodeError):
            jasennys = "uusinta"
            vastaus = kutsu.kysy(
                viesti + "\n\nPalauta PELKKÄ JSON-objekti muodossa {\"tulokset\": [...]}.",
                jarjestelma, json_muoto=True, vakaa_prefix=vakaa_prefix,
            )
            tulokset = llmarviointi._erittele_json(vastaus)
    except Exception:
        jasennys = "epaonnistui"
        tulokset = []
    kesto = time.monotonic() - alku

    kaytto = kutsu.hae_viimeisin_kaytto()
    katto = asetukset.lue_int("LLM_MAX_TOKENIT", kutsu._MAX_TOKENIT)
    ulostulo = kaytto.get("completion_tokens")
    tayttoaste = round(ulostulo / katto, 3) if ulostulo else None

    mittaus = {
        "kursseja_lahetetty": len(era),
        "kysymyksia": len(kysymykset),
        "tuloksia_saatu": len(tulokset),
        "pudonneet": len(era) - len(tulokset),
        "jasennys": jasennys,
        "kesto_s": round(kesto, 2),
        "syote_tokenit": kaytto.get("prompt_tokens"),
        "ulostulo_tokenit": ulostulo,
        "ulostulo_katto": katto,
        "ulostulo_tayttoaste": tayttoaste,
        "finish_reason": kaytto.get("finish_reason"),
    }
    return mittaus, tulokset


def _kirjaa(polku: str, tietue: dict) -> None:
    """Lisää tietueen JSONL-tiedoston loppuun (ei koskaan ylikirjoita)."""
    kansio = os.path.dirname(polku)
    if kansio:
        os.makedirs(kansio, exist_ok=True)
    with open(polku, "a", encoding="utf-8") as f:
        f.write(json.dumps(tietue, ensure_ascii=False) + "\n")


def _tallenna_testitulokset(tulokset, kysymykset, ajo_id, erakoko, tid, malli,
                            kys_tiiviste, lahetetyt) -> None:
    """Kirjaa (kurssi, kysymys) -vastaukset testitauluun ajotunnuksella."""
    for tulos in tulokset:
        kid = tulos.get("id")
        if kid not in lahetetyt:
            continue
        for i, k in enumerate(kysymykset):
            vastaukset_lista = tulos.get("vastaukset", [])
            raw = vastaukset_lista[i] if i < len(vastaukset_lista) else ""
            vastaus, pisteet, luokka, lista = llmarviointi.pura_vastaus(k, raw)
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

    erat = llmarviointi.rakenna_erat(tieto, erakoko)[:montako_era]
    tietueet = []
    for era_nro, (osa_kysymykset, era) in enumerate(erat, 1):
        mittaus, tulokset = _mittaa_era(era, arviointikehote, osa_kysymykset, jarjestelma)

        lahetetyt = {k["KID"] for k in era}
        _tallenna_testitulokset(tulokset, osa_kysymykset, ajo_id, erakoko, tid,
                                malli, kys_tiiviste, lahetetyt)

        tietue = {
            "aikaleima": datetime.now().isoformat(timespec="seconds"),
            "ajo_id": ajo_id,
            "tutkimus": tutkimus.get("Slug", ""),
            "tid": tid,
            "malli": malli,
            "erakoko_pyydetty": erakoko,
            "era_nro": era_nro,
            "eria_yhteensa": len(erat),
            **mittaus,
        }
        _kirjaa(polku, tietue)
        tietueet.append(tietue)
        if edistyminen_cb:
            edistyminen_cb(era_nro, len(erat))

    return {"ajo_id": ajo_id, "eria": len(erat), "tilastopolku": polku, "tietueet": tietueet}
