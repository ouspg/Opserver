"""LLM-arviointi: lähettää mukaan otetut kurssit LLM:lle kysymysvastauksiin."""
import json
from tietokanta import mallit
from llm import kutsu, tiiviste, kehoteet

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
    return kehoteet.lue("arviointi_jarjestelma.txt")


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
        elif luokittelu == "lista":
            maks = maarittely.get("max_kohdat")
            raja = f" (enintään {maks} kohtaa)" if maks else ""
            rivit.append(f'   Luettele asiat erillisinä kohtina{raja}.')
            rivit.append('   Palauta objekti: {"kohdat": ["<kohta1>", "<kohta2>", …], "perustelu": "<selitys>"}')
    return "\n".join(rivit)


def _tallenna_tulokset(tulokset: list[dict], kysymykset: list[dict], malli: str,
                       kys_tiiviste: dict | None = None) -> None:
    for tulos in tulokset:
        kid = tulos["id"]
        for i, k in enumerate(kysymykset):
            vastaukset_lista = tulos.get("vastaukset", [])
            raw = vastaukset_lista[i] if i < len(vastaukset_lista) else ""
            luokittelu = k.get("Luokittelu") or "vapaa_teksti"

            pisteet = luokka = lista = None
            if luokittelu == "luokittelu" and isinstance(raw, dict):
                vastaus = raw.get("perustelu", "")
                luokka = raw.get("luokka", "")
            elif luokittelu == "asteikko" and isinstance(raw, dict):
                vastaus = raw.get("perustelu", "")
                pisteet = float(raw["pisteet"]) if raw.get("pisteet") is not None else None
            elif luokittelu == "lista" and isinstance(raw, dict):
                vastaus = raw.get("perustelu", "")
                kohdat = raw.get("kohdat", [])
                lista = [str(x) for x in kohdat] if isinstance(kohdat, list) else []
            else:
                vastaus = str(raw) if raw else ""

            tiiv = (kys_tiiviste or {}).get(k["KysID"])
            mallit.aseta_vastaus(k["KysID"], kid, vastaus, malli,
                                 pisteet=pisteet, luokka=luokka, lista=lista, tiiviste=tiiv)


def _arvioi_erä(erä: list[dict], arviointikehote: str, kysymykset: list[dict], jarjestelma: str) -> list[dict]:
    kurssit_json = json.dumps(
        [_kurssi_json_promptiin(k) for k in erä],
        ensure_ascii=False,
        indent=2,
    )
    kysymysteksti = _rakenna_kysymysteksti(kysymykset)
    vakaa_prefix = f"{arviointikehote}\n\n{kysymysteksti}\n\nArvioi seuraavat kurssit:\n"
    viesti = f"{vakaa_prefix}{kurssit_json}"
    try:
        vastaus = kutsu.kysy(viesti, jarjestelma, json_muoto=True, vakaa_prefix=vakaa_prefix)
        return _erittele_json(vastaus)
    except (ValueError, json.JSONDecodeError):
        vastaus2 = kutsu.kysy(viesti + "\n\nPalauta PELKKÄ JSON-objekti muodossa {\"tulokset\": [...]}.", jarjestelma, json_muoto=True, vakaa_prefix=vakaa_prefix)
        return _erittele_json(vastaus2)


def _tarvitsee_ajon(tila: dict | None, nyky_tiiviste: str) -> bool:
    """True jos (kurssi, kysymys) -vastaus puuttuu, on tyhjä tai tehty vanhalla kehotteella."""
    if tila is None or not tila["vastattu"]:
        return True
    return tila["tiiviste"] != nyky_tiiviste


def _selvita_tyo(tutkimus: dict) -> dict:
    """Selvittää mitkä kysymykset kullekin mukana-kurssille tarvitsevat (uudelleen)arvioinnin.

    Vain muuttunut tai puuttuva (kurssi, kysymys) -pari otetaan työn alle —
    samalla kehotteella jo arvioituja ei kysytä LLM:ltä uudelleen.
    """
    tid = tutkimus["TID"]
    arviointikehote = tutkimus["Arviointikehote"]
    kysymykset = mallit.hae_kysymykset(tid)
    if not kysymykset:
        return {"kysymykset": [], "jarjestelma": "", "kys_tiiviste": {},
                "arviointikehote": arviointikehote, "kurssi_kartta": {}, "olemassa": {}, "tyo": {}}

    jarjestelma = _lue_jarjestelma_kehote()
    kys_tiiviste = tiiviste.kysymystiivisteet(arviointikehote, jarjestelma, kysymykset)
    kurssit = mallit.hae_valitut_kurssit(tid)
    olemassa = mallit.hae_vastaus_tiivisteet(tid)

    tyo: dict[int, list[dict]] = {}
    for kurssi in kurssit:
        kid = kurssi["KID"]
        tarvitsee = [
            k for k in kysymykset
            if _tarvitsee_ajon(olemassa.get((kid, k["KysID"])), kys_tiiviste[k["KysID"]])
        ]
        if tarvitsee:
            tyo[kid] = tarvitsee

    return {"kysymykset": kysymykset, "jarjestelma": jarjestelma, "kys_tiiviste": kys_tiiviste,
            "arviointikehote": arviointikehote, "kurssi_kartta": {k["KID"]: k for k in kurssit},
            "olemassa": olemassa, "tyo": tyo}


def laske_tyomaara(tutkimus: dict) -> tuple[int, int]:
    """(uudet, vanhentuneet) — montako mukana-kurssia arvioidaan: täysin uudet
    (ei aiempia vastauksia) vs. osin vanhentuneet (kehote/kysymys muuttunut)."""
    tieto = _selvita_tyo(tutkimus)
    uudet = vanhentuneet = 0
    for kid in tieto["tyo"]:
        oli_vastauksia = any(
            (s := tieto["olemassa"].get((kid, k["KysID"]))) and s["vastattu"]
            for k in tieto["kysymykset"]
        )
        if oli_vastauksia:
            vanhentuneet += 1
        else:
            uudet += 1
    return uudet, vanhentuneet


def aja(tutkimus: dict, edistyminen_cb=None, max_erat: int | None = None) -> int:
    """Arvioi mukaan otetut kurssit LLM:llä. Palauttaa arvioitujen kurssien määrän.

    Idempotentti ja kehotetietoinen: kysyy LLM:ltä vain ne (kurssi, kysymys) -parit,
    joiden vastaus puuttuu tai joiden kehote/kysymys on muuttunut.

    max_erat: jos annettu, ajetaan korkeintaan tämän verran eräpyyntöjä (esim. 1 =
    yksi LLM-pyyntö, kätevä testaukseen). Loput jäävät seuraavalle ajolle.
    """
    tieto = _selvita_tyo(tutkimus)
    tyo = tieto["tyo"]
    if not tyo:
        return 0

    kysymykset = tieto["kysymykset"]
    arviointikehote = tieto["arviointikehote"]
    jarjestelma = tieto["jarjestelma"]
    kys_tiiviste = tieto["kys_tiiviste"]
    kurssi_kartta = tieto["kurssi_kartta"]

    # Ryhmittele kurssit tarvittavien kysymysten mukaan, jotta yhdessä erässä
    # kysytään vain sama (mahdollisesti osittainen) kysymysjoukko.
    ryhmat: dict[tuple, list[dict]] = {}
    for kid, kys_lista in tyo.items():
        avain = tuple(sorted(k["KysID"] for k in kys_lista))
        ryhmat.setdefault(avain, []).append(kurssi_kartta[kid])

    erat: list[tuple[list[dict], list[dict]]] = []
    for avain, ryhman_kurssit in ryhmat.items():
        osa_kysymykset = [k for k in kysymykset if k["KysID"] in avain]
        for i in range(0, len(ryhman_kurssit), ERÄKOKO):
            erat.append((osa_kysymykset, ryhman_kurssit[i:i + ERÄKOKO]))

    if max_erat is not None:
        erat = erat[:max_erat]

    malli = kutsu.hae_malli()
    yhteensa = sum(len(erä) for _, erä in erat)
    arvioidut: set = set()
    käsitelty = 0

    for erä_nro, (osa_kysymykset, erä) in enumerate(erat, 1):
        if edistyminen_cb:
            edistyminen_cb(käsitelty, yhteensa, erä_nro, len(erat))
        tulokset = _arvioi_erä(erä, arviointikehote, osa_kysymykset, jarjestelma)
        _tallenna_tulokset(tulokset, osa_kysymykset, malli, kys_tiiviste)
        for t in tulokset:
            arvioidut.add(t.get("id"))
        käsitelty += len(erä)
        if edistyminen_cb:
            edistyminen_cb(käsitelty, yhteensa, erä_nro, len(erat))

    return len(arvioidut)
