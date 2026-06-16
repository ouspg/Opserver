"""LLM-arviointi: lähettää mukaan otetut kurssit LLM:lle kysymysvastauksiin."""
import json
import os
from tietokanta import mallit
from llm import kutsu

ERÄKOKO = 5


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
        os.path.dirname(__file__), "..", "kehoteet", "arviointi_jarjestelma.txt"
    )
    with open(polku, encoding="utf-8") as f:
        return f.read().strip()


def _erittele_json(teksti: str) -> list[dict]:
    """Jäsentää JSON-objektin ja palauttaa tuloslistan siitä."""
    teksti = teksti.strip()
    alku = teksti.find("{")
    if alku != -1:
        loppu = teksti.rfind("}")
        if loppu != -1:
            data = json.loads(teksti[alku:loppu + 1])
            for arvo in data.values():
                if isinstance(arvo, list):
                    return arvo
            raise ValueError(f"Vastaus ei sisällä lista-kenttää: {teksti[:200]}")
    raise ValueError(f"Ei JSON-objektia vastauksessa: {teksti[:200]}")


def _rakenna_kysymysteksti(kysymykset: list[dict]) -> str:
    rivit = ["Vastaa jokaiselle kurssille seuraaviin kysymyksiin:"]
    for i, k in enumerate(kysymykset, 1):
        luokittelu = k.get("Luokittelu") or "vapaa_teksti"
        maarittely = k.get("LuokitteluMaarittely") or {}
        rivit.append(f"{i}. {k['Kysymys']}")
        if luokittelu == "luokittelu":
            luokat = maarittely.get("luokat", [])
            nimet = ", ".join(f'"{l["nimi"]}"' for l in luokat)
            rivit.append(f'   Valitse yksi luokka: {nimet}')
            for l in luokat:
                rivit.append(f'   - {l["nimi"]}: {l["kuvaus"]}')
            rivit.append('   Palauta objekti: {"luokka": "<valittu>", "perustelu": "<selitys>"}')
        elif luokittelu == "asteikko":
            minimi = maarittely.get("minimi", 1)
            maksimi = maarittely.get("maksimi", 5)
            pisteet = maarittely.get("pisteet", [])
            rivit.append(f'   Anna kokonaislukupisteet väliltä {minimi}–{maksimi}:')
            for p in pisteet:
                rivit.append(f'   - {p["arvo"]}/{maksimi}: {p["kuvaus"]}')
            rivit.append(f'   Palauta objekti: {{"pisteet": <{minimi}-{maksimi}>, "perustelu": "<selitys>"}}')
    return "\n".join(rivit)


def _tallenna_tulokset(tulokset: list[dict], kysymykset: list[dict], malli: str) -> None:
    for tulos in tulokset:
        kid = tulos["id"]
        for i, k in enumerate(kysymykset):
            vastaukset_lista = tulos.get("vastaukset", [])
            raw = vastaukset_lista[i] if i < len(vastaukset_lista) else ""
            luokittelu = k.get("Luokittelu") or "vapaa_teksti"

            if luokittelu == "luokittelu" and isinstance(raw, dict):
                vastaus = raw.get("perustelu", "")
                luokka = raw.get("luokka", "")
                pisteet = None
            elif luokittelu == "asteikko" and isinstance(raw, dict):
                vastaus = raw.get("perustelu", "")
                pisteet = float(raw["pisteet"]) if raw.get("pisteet") is not None else None
                luokka = None
            else:
                vastaus = str(raw) if raw else ""
                pisteet = None
                luokka = None

            mallit.aseta_vastaus(k["KysID"], kid, vastaus, malli, pisteet=pisteet, luokka=luokka)


def _arvioi_erä(erä: list[dict], arviointikehote: str, kysymykset: list[dict], jarjestelma: str) -> list[dict]:
    kurssit_json = json.dumps(
        [_kurssi_json_promptiin(k) for k in erä],
        ensure_ascii=False,
        indent=2,
    )
    kysymysteksti = _rakenna_kysymysteksti(kysymykset)
    viesti = f"{arviointikehote}\n\n{kysymysteksti}\n\nArvioi seuraavat kurssit:\n{kurssit_json}"
    try:
        vastaus = kutsu.kysy(viesti, jarjestelma, json_muoto=True)
        return _erittele_json(vastaus)
    except (ValueError, json.JSONDecodeError):
        vastaus2 = kutsu.kysy(viesti + "\n\nPalauta PELKKÄ JSON-objekti muodossa {\"tulokset\": [...]}.", jarjestelma, json_muoto=True)
        return _erittele_json(vastaus2)


def aja(tutkimus: dict, edistyminen_cb=None) -> int:
    """Arvioi mukaan otetut kurssit LLM:llä. Palauttaa arvioitujen kurssien määrän. Idempotentti."""
    tid = tutkimus["TID"]
    arviointikehote = tutkimus["Arviointikehote"]

    kysymykset = mallit.hae_kysymykset(tid)
    if not kysymykset:
        return 0

    kandidaatit = mallit.hae_arvioimattomat(tid)
    if not kandidaatit:
        return 0

    jarjestelma = _lue_jarjestelma_kehote()
    malli = kutsu.hae_malli()
    erat = [kandidaatit[i:i + ERÄKOKO] for i in range(0, len(kandidaatit), ERÄKOKO)]
    arvioitu = 0
    käsitelty = 0

    for erä_nro, erä in enumerate(erat, 1):
        if edistyminen_cb:
            edistyminen_cb(käsitelty, len(kandidaatit), erä_nro, len(erat))
        tulokset = _arvioi_erä(erä, arviointikehote, kysymykset, jarjestelma)
        _tallenna_tulokset(tulokset, kysymykset, malli)
        arvioitu += len(tulokset)
        käsitelty += len(erä)
        if edistyminen_cb:
            edistyminen_cb(käsitelty, len(kandidaatit), erä_nro, len(erat))

    return arvioitu
