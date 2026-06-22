"""Luokittelun testierä-mittaus: ajaa muutaman erän valitulla eräkoolla,
kirjaa tulokset kantaan (testitauluun) ja tilastot vertailua varten.

Tulokset talletetaan Kurssiluokitus_testi-tauluun ajotunnuksella (Ajo), jotta
LLM-kutsuja ei haaskata ja kukin testiajo voidaan poistaa kohdennetusti oikeita
tuloksia koskematta. Tilastot kirjataan lisäksi append-only JSONL-tiedostoon,
joten uusi ajo ei pyyhi aiempia: esim. 3×30, 3×40 ja 3×50 kertyvät samaan
tiedostoon vertailtaviksi.
"""
import json
import os
import random
import time
from datetime import datetime

from tietokanta import mallit, testimallit
from llm import kutsu, tiiviste, kurssimuoto, asetukset
from luokittelu import llmluokittelu

TILASTOPOLKU = "testitulokset/luokittelu_testierat.jsonl"


def _mittaa_era(era: list[dict], luokittelukehote: str, jarjestelma: str) -> tuple[dict, list[dict]]:
    """Lähettää yhden erän LLM:lle. Palauttaa (mittaustiedot, jäsennetyt tulokset)."""
    kurssit_json = json.dumps(
        [kurssimuoto.kurssi_json_promptiin(k) for k in era],
        ensure_ascii=False,
        indent=2,
    )
    vakaa_prefix = f"{luokittelukehote}\n\nArvioi seuraavat kurssit:\n"
    viesti = f"{vakaa_prefix}{kurssit_json}"

    alku = time.monotonic()
    jasennys = "ok"
    tulokset: list[dict] = []
    try:
        vastaus = kutsu.kysy(viesti, jarjestelma, vakaa_prefix=vakaa_prefix)
        try:
            tulokset = llmluokittelu._erittele_json(vastaus)
        except (ValueError, json.JSONDecodeError):
            jasennys = "uusinta"
            vastaus = kutsu.kysy(
                viesti + "\n\nPalauta PELKKÄ JSON-taulukko.", jarjestelma, vakaa_prefix=vakaa_prefix
            )
            tulokset = llmluokittelu._erittele_json(vastaus)
    except Exception:
        jasennys = "epaonnistui"
        tulokset = []
    kesto = time.monotonic() - alku

    kaytto = kutsu.hae_viimeisin_kaytto()
    katto = asetukset.lue_int("LLM_MAX_TOKENIT", kutsu._MAX_TOKENIT)
    ulostulo = kaytto.get("completion_tokens")
    tayttoaste = round(ulostulo / katto, 3) if ulostulo else None
    mukana = sum(1 for t in tulokset if t.get("mukana"))

    mittaus = {
        "kursseja_lahetetty": len(era),
        "tuloksia_saatu": len(tulokset),
        "pudonneet": len(era) - len(tulokset),
        "jasennys": jasennys,
        "kesto_s": round(kesto, 2),
        "syote_tokenit": kaytto.get("prompt_tokens"),
        "ulostulo_tokenit": ulostulo,
        "ulostulo_katto": katto,
        "ulostulo_tayttoaste": tayttoaste,
        "finish_reason": kaytto.get("finish_reason"),
        "mukana": mukana,
        "hylatty": len(tulokset) - mukana,
        "paatokset": [{"id": t.get("id"), "mukana": bool(t.get("mukana"))} for t in tulokset],
    }
    return mittaus, tulokset


def _kirjaa(polku: str, tietue: dict) -> None:
    """Lisää tietueen JSONL-tiedoston loppuun (ei koskaan ylikirjoita)."""
    kansio = os.path.dirname(polku)
    if kansio:
        os.makedirs(kansio, exist_ok=True)
    with open(polku, "a", encoding="utf-8") as f:
        f.write(json.dumps(tietue, ensure_ascii=False) + "\n")


def aja_testierat(tutkimus: dict, erakoko: int, montako_era: int,
                  edistyminen_cb=None, tilastopolku: str | None = None) -> dict:
    """Ajaa enintään `montako_era` erää kooltaan `erakoko`, kirjaa tulokset kantaan
    (testitauluun, ajotunnuksella) ja tilastot tiedostoon. Palauttaa yhteenvedon."""
    polku = tilastopolku or TILASTOPOLKU
    tid = tutkimus["TID"]
    luokittelukehote = tutkimus["Luokittelukehote"]
    jarjestelma = llmluokittelu._lue_jarjestelma_kehote()
    tiiv = tiiviste.luokittelu(luokittelukehote, jarjestelma)
    malli = kutsu.hae_malli()

    # Satunnaisotos ilman takaisinpanoa → sama kurssi ei voi osua kahteen erään.
    kandidaatit = mallit.hae_luokittelemattomat(tid, tiiv)
    otos = random.sample(kandidaatit, min(erakoko * montako_era, len(kandidaatit)))
    erat = [otos[i : i + erakoko] for i in range(0, len(otos), erakoko)]

    ajo_id = datetime.now().strftime("%Y%m%dT%H%M%S")
    tietueet = []
    for era_nro, era in enumerate(erat, 1):
        mittaus, tulokset = _mittaa_era(era, luokittelukehote, jarjestelma)

        # Kirjaa kunkin kurssin tulos testitauluun (ajotunnuksella, poistettavissa)
        lahetetyt = {k["KID"] for k in era}
        for tulos in tulokset:
            kid = tulos.get("id")
            if kid in lahetetyt:
                testimallit.aseta_testiluokitus(
                    ajo=ajo_id, erakoko=erakoko, tid=tid, kid=kid,
                    mukana=bool(tulos.get("mukana")), perustelu=tulos.get("perustelu", ""),
                    malli=malli, tiiviste=tiiv,
                )

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
