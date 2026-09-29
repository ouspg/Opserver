"""Kurssierän LLM-kutsu ja testierien mittaus — jaettu luokittelun ja arvioinnin,
sekä tuotantoajon ja testierien kesken (sama viesti, sama uusintayritys)."""
import json
import os
from datetime import datetime

from tietokanta import mallit
from llm import kutsu, kurssimuoto, asetukset


def rakenna_viesti(erä: list[dict], vakaa_prefix: str) -> str:
    """Kehote + erän kurssit JSONina. Erä saapuu kevyinä riveinä (ei OpsKuvausta) —
    kuvaukset haetaan vasta tässä, jottei koko ehdokasjoukon kuvauksia ladata kerralla."""
    taydet = mallit.hae_kurssit_idlla([k["KID"] for k in erä])
    kurssit_json = json.dumps(
        [kurssimuoto.kurssi_json_promptiin(k) for k in taydet],
        ensure_ascii=False,
        indent=2,
    )
    return f"{vakaa_prefix}{kurssit_json}"


def kysy_json(viesti: str, jarjestelma: str, vakaa_prefix: str, jasenna, uusintaohje: str,
              json_muoto: bool = False) -> tuple[list[dict], str]:
    """Kysyy ja jäsentää; viallinen tai tyhjä vastaus → yksi uusintayritys uusintaohjeella.
    Palauttaa (tulokset, "ok" | "uusinta"); uusinnan epäonnistuminen nostaa poikkeuksen."""
    try:
        return jasenna(kutsu.kysy(viesti, jarjestelma, json_muoto=json_muoto,
                                  vakaa_prefix=vakaa_prefix)), "ok"
    except (ValueError, json.JSONDecodeError):
        vastaus = kutsu.kysy(viesti + uusintaohje, jarjestelma, json_muoto=json_muoto,
                             vakaa_prefix=vakaa_prefix)
        return jasenna(vastaus), "uusinta"


def token_mittaus() -> dict:
    """Viimeisimmän kutsun token-käyttö suhteessa ulostulokattoon (testierät)."""
    kaytto = kutsu.hae_viimeisin_kaytto()
    katto = asetukset.lue_int("LLM_MAX_TOKENIT", kutsu._MAX_TOKENIT)
    ulostulo = kaytto.get("completion_tokens")
    return {
        "syote_tokenit": kaytto.get("prompt_tokens"),
        "ulostulo_tokenit": ulostulo,
        "ulostulo_katto": katto,
        "ulostulo_tayttoaste": round(ulostulo / katto, 3) if ulostulo else None,
        "finish_reason": kaytto.get("finish_reason"),
    }


def testitietue(ajo_id: str, tutkimus: dict, malli: str, erakoko: int,
                era_nro: int, eria: int, mittaus: dict) -> dict:
    return {
        "aikaleima": datetime.now().isoformat(timespec="seconds"),
        "ajo_id": ajo_id,
        "tutkimus": tutkimus.get("Slug", ""),
        "tid": tutkimus["TID"],
        "malli": malli,
        "erakoko_pyydetty": erakoko,
        "era_nro": era_nro,
        "eria_yhteensa": eria,
        **mittaus,
    }


def kirjaa_jsonl(polku: str, tietue: dict) -> None:
    """Lisää tietueen JSONL-tiedoston loppuun (ei koskaan ylikirjoita)."""
    kansio = os.path.dirname(polku)
    if kansio:
        os.makedirs(kansio, exist_ok=True)
    with open(polku, "a", encoding="utf-8") as f:
        f.write(json.dumps(tietue, ensure_ascii=False) + "\n")
