"""LLM-luokittelu: lähettää meta-suodatuksen läpäisseet kurssit LLM:lle."""
import json
import os
from tietokanta import mallit
from llm import kutsu

ERÄKOKO = 20  # kursseja per LLM-kutsu


def _kuvaus_tekstina(ops_kuvaus: str | None, max_merkit: int = 800) -> str:
    if not ops_kuvaus:
        return ""
    try:
        data = json.loads(ops_kuvaus)
        osat = []
        for osio in data.get("contentList", []):
            otsikko = (osio.get("title") or {}).get("valueFi", "")
            teksti = ((osio.get("content") or {}).get("valueFi") or "").strip()
            if teksti:
                osat.append(f"{otsikko}: {teksti}" if otsikko else teksti)
        return "\n".join(osat)[:max_merkit]
    except (ValueError, AttributeError):
        return str(ops_kuvaus)[:max_merkit]


def _kurssi_json_promptiin(kurssi: dict) -> dict:
    return {
        "id": kurssi["KID"],
        "nimi": kurssi["KurssiNimi"],
        "koodi": kurssi.get("Koodi") or "",
        "taso": kurssi.get("Taso") or "",
        "oppiaine": kurssi.get("Oppiaine") or "",
        "kuvaus": _kuvaus_tekstina(kurssi.get("OpsKuvaus")),
    }


def _lue_jarjestelma_kehote() -> str:
    polku = os.path.join(
        os.path.dirname(__file__), "..", "kehoteet", "luokittelu_jarjestelma.txt"
    )
    with open(polku, encoding="utf-8") as f:
        return f.read().strip()


def _erittele_json(teksti: str) -> list[dict]:
    """Erottaa JSON-taulukon LLM:n vastauksesta; sietokykyinen ylimääräisille merkeille."""
    teksti = teksti.strip()
    alku = teksti.find("[")
    loppu = teksti.rfind("]")
    if alku == -1 or loppu == -1:
        raise ValueError(f"Ei JSON-taulukkoa vastauksessa: {teksti[:200]}")
    return json.loads(teksti[alku : loppu + 1])


def _luokittele_erä(erä: list[dict], luokittelukehote: str, jarjestelma: str) -> list[dict]:
    """Lähettää yhden erän LLM:lle ja palauttaa jäsennetyn vastauksen."""
    kurssit_json = json.dumps(
        [_kurssi_json_promptiin(k) for k in erä],
        ensure_ascii=False,
        indent=2,
    )
    viesti = f"{luokittelukehote}\n\nArvioi seuraavat kurssit:\n{kurssit_json}"
    vastaus = kutsu.kysy(viesti, jarjestelma)
    try:
        return _erittele_json(vastaus)
    except (ValueError, json.JSONDecodeError):
        # Yksi uusintayritys
        vastaus2 = kutsu.kysy(viesti + "\n\nPalauta PELKKÄ JSON-taulukko.", jarjestelma)
        return _erittele_json(vastaus2)


def aja(tutkimus: dict, edistyminen_cb=None) -> tuple[int, int]:
    """Luokittelee meta-suodatuksen läpäisseet kurssit LLM:llä.

    Palauttaa (mukana, hylätty). Idempotentti.
    """
    tid = tutkimus["TID"]
    luokittelukehote = tutkimus["Luokittelukehote"]
    jarjestelma = _lue_jarjestelma_kehote()

    kandidaatit = mallit.hae_luokittelemattomat(tid)
    if not kandidaatit:
        return 0, 0

    erat = [kandidaatit[i : i + ERÄKOKO] for i in range(0, len(kandidaatit), ERÄKOKO)]
    mukana = 0
    hylätty = 0
    käsitelty = 0

    for erä_nro, erä in enumerate(erat, 1):
        tulokset = _luokittele_erä(erä, luokittelukehote, jarjestelma)
        for tulos in tulokset:
            kid = tulos["id"]
            on_mukana = bool(tulos.get("mukana"))
            perustelu = tulos.get("perustelu", "")
            mallit.aseta_luokitus(tid, kid, on_mukana, perustelu)
            if on_mukana:
                mukana += 1
            else:
                hylätty += 1
        käsitelty += len(erä)
        if edistyminen_cb:
            edistyminen_cb(käsitelty, len(kandidaatit), erä_nro, len(erat))

    return mukana, hylätty
