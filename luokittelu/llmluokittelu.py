"""LLM-luokittelu: lähettää meta-suodatuksen läpäisseet kurssit LLM:lle."""
import json
from tietokanta import mallit
from llm import kutsu, tiiviste, kehoteet, kurssimuoto, asetukset

_OLETUS_ERAKOKO = 20  # kursseja per LLM-kutsu; .env:n LUOKITTELU_ERAKOKO ohittaa


def erakoko() -> int:
    """Kursseja per LLM-kutsu (.env: LUOKITTELU_ERAKOKO)."""
    return asetukset.lue_int("LUOKITTELU_ERAKOKO", _OLETUS_ERAKOKO)


def _lue_jarjestelma_kehote() -> str:
    return kehoteet.lue("luokittelu_jarjestelma.txt")


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
        [kurssimuoto.kurssi_json_promptiin(k) for k in erä],
        ensure_ascii=False,
        indent=2,
    )
    vakaa_prefix = f"{luokittelukehote}\n\nArvioi seuraavat kurssit:\n"
    viesti = f"{vakaa_prefix}{kurssit_json}"
    vastaus = kutsu.kysy(viesti, jarjestelma, vakaa_prefix=vakaa_prefix)
    try:
        return _erittele_json(vastaus)
    except (ValueError, json.JSONDecodeError):
        # Yksi uusintayritys
        vastaus2 = kutsu.kysy(viesti + "\n\nPalauta PELKKÄ JSON-taulukko.", jarjestelma, vakaa_prefix=vakaa_prefix)
        return _erittele_json(vastaus2)


def laske_tiiviste(tutkimus: dict) -> str:
    """Nykyisen luokittelukehotteen tiiviste (kehote + järjestelmäkehote)."""
    return tiiviste.luokittelu(tutkimus["Luokittelukehote"], _lue_jarjestelma_kehote())


def aja(tutkimus: dict, edistyminen_cb=None) -> tuple[int, int, int]:
    """Luokittelee meta-suodatuksen läpäisseet kurssit LLM:llä.

    Palauttaa (mukana, hylätty, virhe_erat). Idempotentti. Yksittäisen erän
    epäonnistuminen (esim. katkennut/viallinen LLM-JSON) ei kaada koko ajoa:
    erä ohitetaan ja sen kurssit tulevat mukaan seuraavalla ajolla.
    """
    tid = tutkimus["TID"]
    luokittelukehote = tutkimus["Luokittelukehote"]
    jarjestelma = _lue_jarjestelma_kehote()
    tiiv = tiiviste.luokittelu(luokittelukehote, jarjestelma)

    # Tiiviste mukana → ajaa myös vanhentuneen kehotteen tulokset uudelleen,
    # mutta ei jo täsmäävän kehotteen tuloksia (säästää LLM-kuluja).
    kandidaatit = mallit.hae_luokittelemattomat(tid, tiiv)
    if not kandidaatit:
        return 0, 0, 0

    malli = kutsu.hae_malli()
    koko = erakoko()
    erat = [kandidaatit[i : i + koko] for i in range(0, len(kandidaatit), koko)]
    mukana = 0
    hylätty = 0
    virhe_erat = 0
    käsitelty = 0

    for erä_nro, erä in enumerate(erat, 1):
        try:
            tulokset = _luokittele_erä(erä, luokittelukehote, jarjestelma)
        except Exception:
            virhe_erat += 1  # viallinen erä ohitetaan; kurssit jäävät seuraavalle ajolle
            tulokset = []
        for tulos in tulokset:
            kid = tulos.get("id")
            if kid is None:
                continue
            on_mukana = bool(tulos.get("mukana"))
            perustelu = tulos.get("perustelu", "")
            mallit.aseta_luokitus(tid, kid, on_mukana, perustelu, malli, tiiviste=tiiv)
            if on_mukana:
                mukana += 1
            else:
                hylätty += 1
        käsitelty += len(erä)
        if edistyminen_cb:
            edistyminen_cb(käsitelty, len(kandidaatit), erä_nro, len(erat))

    return mukana, hylätty, virhe_erat
