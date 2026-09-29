"""Luokittelun testierä-mittaus: ajaa muutaman erän valitulla eräkoolla,
kirjaa tulokset kantaan (testitauluun) ja tilastot vertailua varten.

Tulokset talletetaan Kurssiluokitus_testi-tauluun ajotunnuksella (Ajo), jotta
LLM-kutsuja ei haaskata ja kukin testiajo voidaan poistaa kohdennetusti oikeita
tuloksia koskematta. Tilastot kirjataan lisäksi append-only JSONL-tiedostoon,
joten uusi ajo ei pyyhi aiempia: esim. 3×30, 3×40 ja 3×50 kertyvät samaan
tiedostoon vertailtaviksi.
"""
import random
import time
from datetime import datetime

from tietokanta import mallit, testimallit
from llm import kutsu, tiiviste, kurssimuoto, erakutsu
from luokittelu import llmluokittelu

TILASTOPOLKU = "testitulokset/luokittelu_testierat.jsonl"


def _mittaa_era(era: list[dict], luokittelukehote: str, jarjestelma: str) -> tuple[dict, list[dict]]:
    """Lähettää yhden erän LLM:lle kuten tuotantoajo. Palauttaa (mittaustiedot, tulokset)."""
    vakaa_prefix = f"{luokittelukehote}\n\nArvioi seuraavat kurssit:\n"
    viesti = erakutsu.rakenna_viesti(era, vakaa_prefix)
    alku = time.monotonic()
    try:
        tulokset, jasennys = erakutsu.kysy_json(viesti, jarjestelma, vakaa_prefix,
                                                llmluokittelu._erittele_json, llmluokittelu._UUSINTAOHJE)
    except Exception:
        tulokset, jasennys = [], "epaonnistui"
    kesto = time.monotonic() - alku
    mukana = sum(1 for t in tulokset if t.get("mukana"))

    mittaus = {
        "kursseja_lahetetty": len(era),
        "tuloksia_saatu": len(tulokset),
        "pudonneet": len(era) - len(tulokset),
        "jasennys": jasennys,
        "kesto_s": round(kesto, 2),
        **erakutsu.token_mittaus(),
        "mukana": mukana,
        "hylatty": len(tulokset) - mukana,
        "paatokset": [{"id": t.get("id"), "mukana": bool(t.get("mukana"))} for t in tulokset],
    }
    return mittaus, tulokset


def aja_testierat(tutkimus: dict, erakoko: int, montako_era: int,
                  edistyminen_cb=None, tilastopolku: str | None = None) -> dict:
    """Ajaa enintään `montako_era` erää kooltaan `erakoko`, kirjaa tulokset kantaan
    (testitauluun, ajotunnuksella) ja tilastot tiedostoon. Palauttaa yhteenvedon."""
    polku = tilastopolku or TILASTOPOLKU
    tid = tutkimus["TID"]
    luokittelukehote = tutkimus["Luokittelukehote"]
    jarjestelma = llmluokittelu._lue_jarjestelmakehote()
    tiiv = tiiviste.luokittelu(luokittelukehote, jarjestelma)
    malli = kutsu.hae_malli()

    # Satunnaisotos ilman takaisinpanoa → sama kurssi ei voi osua kahteen erään.
    kandidaatit = mallit.hae_luokittelemattomat_kevyet(tid, tiiv)
    otos = random.sample(kandidaatit, min(erakoko * montako_era, len(kandidaatit)))
    erat = [otos[i : i + erakoko] for i in range(0, len(otos), erakoko)]

    ajo_id = datetime.now().strftime("%Y%m%dT%H%M%S")
    tietueet = []
    for era_nro, era in enumerate(erat, 1):
        mittaus, tulokset = _mittaa_era(era, luokittelukehote, jarjestelma)

        # Kirjaa kunkin kurssin tulos testitauluun (ajotunnuksella, poistettavissa)
        for tulos in kurssimuoto.siivoa_tulokset(tulokset, {k["KID"] for k in era}):
            testimallit.aseta_testiluokitus(
                ajo=ajo_id, erakoko=erakoko, tid=tid, kid=tulos["id"],
                mukana=bool(tulos.get("mukana")), perustelu=tulos.get("perustelu", ""),
                malli=malli, tiiviste=tiiv,
            )

        tietue = erakutsu.testitietue(ajo_id, tutkimus, malli, erakoko, era_nro, len(erat), mittaus)
        erakutsu.kirjaa_jsonl(polku, tietue)
        tietueet.append(tietue)
        if edistyminen_cb:
            edistyminen_cb(era_nro, len(erat))

    return {"ajo_id": ajo_id, "eria": len(erat), "tilastopolku": polku, "tietueet": tietueet}
