"""Kurssin tietojen muotoilu LLM-kehotteeseen.

Jaettu luokittelun ja arvioinnin kesken (DRY). Kuvausta EI katkaista: mallin
täytyy saada käyttöönsä kaikki opinto-oppaassa näkyvä tieto — kuvaus on tärkein
tieto, jonka perusteella luokittelu ja arviointi tehdään.
"""
import json
import re

# Sisu KORI -course-unit -objektin tekstikentät (avain → otsikko kehotteeseen).
_SISU_KENTAT = [
    ("tweetText", "Tiivistelmä"),
    ("outcomes", "Osaamistavoitteet"),
    ("content", "Sisältö"),
    ("prerequisites", "Esitiedot"),
    ("additional", "Lisätiedot"),
]

# completionMethods.studyType → suomenkielinen opintotyyppi (tunnistamaton jätetään pois).
_SUORITUS_TYYPPI = {
    "DEGREE_STUDIES": "tutkinto-opinnot",
    "OPEN_UNIVERSITY_STUDIES": "avoin yliopisto",
    "SEPARATE_STUDIES": "erillisopinnot",
}


SISU_KIELET = ("fi", "sv", "en")
PEPPI_KIELET = ("valueFi", "valueSv", "valueEn")


def kieliketju(arvo, avaimet) -> str:
    """Monikielinen kenttä → ensimmäinen ei-tyhjä kieliversio järjestyksessä fi → sv → en.

    Åbo Akademi kuvaa kurssit usein vain ruotsiksi ja osa kursseista on vain
    englanniksi — ilman ketjua ne päätyisivät LLM:lle tyhjinä (#141).
    """
    if not isinstance(arvo, dict):
        return ""
    return next((t.strip() for a in avaimet if isinstance(t := arvo.get(a), str) and t.strip()), "")


def _monikielinen_teksti(arvo) -> str:
    """Sisun monikielinen kenttä ({fi/sv/en: html}) → teksti ilman HTML:ää."""
    return re.sub(r"<[^>]+>", " ", kieliketju(arvo, SISU_KIELET)).strip()


def _peppi_kuvaus(data: dict) -> str:
    osat = []
    for osio in data.get("contentList", []):
        otsikko = kieliketju(osio.get("title"), PEPPI_KIELET)
        teksti = kieliketju(osio.get("content"), PEPPI_KIELET)
        if teksti:
            osat.append(f"{otsikko}: {teksti}" if otsikko else teksti)
    return "\n".join(osat)


def _sisu_suoritustavat(data: dict) -> str:
    """Sisun completionMethods → 'Suoritustavat'-osio + avoimen yo:n merkintä.

    Suoritustavat ovat jo tallennetussa KORI-objektissa, joten tämä ei vaadi
    lisäpyyntöjä. Mukaan tulee kunkin tavan opintotyyppi, kuvaus ja
    arviointikriteerit; avoimen yliopiston suoritustapa merkitään erikseen
    (keskeinen signaali jatkuvan oppimisen / ESR-tutkimuksen kannalta).
    """
    rivit = []
    avoin = False
    for tapa in data.get("completionMethods") or []:
        if tapa.get("studyType") == "OPEN_UNIVERSITY_STUDIES":
            avoin = True
        kuvaus = _monikielinen_teksti(tapa.get("description"))
        kriteerit = _monikielinen_teksti(tapa.get("evaluationCriteria"))
        if not (kuvaus or kriteerit):
            continue
        osat = []
        tyyppi = _SUORITUS_TYYPPI.get(tapa.get("studyType"))
        if tyyppi:
            osat.append(f"({tyyppi})")
        if kuvaus:
            osat.append(kuvaus)
        if kriteerit:
            osat.append(f"Arviointi: {kriteerit}")
        rivit.append("- " + " ".join(osat))
    tulos = []
    if rivit:
        tulos.append("Suoritustavat:\n" + "\n".join(rivit))
    if avoin:
        tulos.append("Avoimen yliopiston suoritustapa: kyllä")
    return "\n".join(tulos)


def _sisu_kuvaus(data: dict) -> str:
    osat = []
    for avain, otsikko in _SISU_KENTAT:
        teksti = _monikielinen_teksti(data.get(avain))
        if teksti:
            osat.append(f"{otsikko}: {teksti}")
    suoritustavat = _sisu_suoritustavat(data)
    if suoritustavat:
        osat.append(suoritustavat)
    return "\n".join(osat)


def kuvaus_tekstina(ops_kuvaus: str | None) -> str:
    """Muuntaa Peppi- tai Sisu-OpsKuvaus-JSONin luettavaksi tekstiksi.

    Peppi: contentList-rakenne. Sisu (KORI): course-unit -objektin tekstikentät
    (tweetText/outcomes/content/prerequisites/additional). Ilman Sisu-haaraa
    Sisu-kurssit päätyisivät LLM:lle ilman kuvausta.
    """
    if not ops_kuvaus:
        return ""
    try:
        data = json.loads(ops_kuvaus)
    except (ValueError, TypeError):
        return str(ops_kuvaus)
    if not isinstance(data, dict):
        return str(ops_kuvaus)
    if "contentList" in data:
        return _peppi_kuvaus(data)
    return _sisu_kuvaus(data)


def kurssi_json_promptiin(kurssi: dict) -> dict:
    """Rakentaa kurssin tiiviin JSON-esityksen LLM-kehotteeseen (täysi kuvaus)."""
    return {
        "id": kurssi["KID"],
        "nimi": kurssi["KurssiNimi"],
        "koodi": kurssi.get("Koodi") or "",
        "taso": kurssi.get("Taso") or "",
        "oppiaine": kurssi.get("Oppiaine") or "",
        "kuvaus": kuvaus_tekstina(kurssi.get("OpsKuvaus")),
    }


def siivoa_tulokset(raaka: list[dict], odotetut: set) -> list[dict]:
    """Suodattaa mallin tulokset vain erän kursseihin ja normalisoi id:t kokonaisluvuiksi.

    Torjuu hallusinoidut / väärät id:t ennen tallennusta (opas: 'IDs must exist') —
    muuten tallennus INSERTtäisi rivin kurssille jota erässä ei ollut.
    """
    siivotut = []
    for t in raaka:
        try:
            kid = int(t.get("id"))
        except (TypeError, ValueError):
            continue
        if kid in odotetut:
            siivotut.append({**t, "id": kid})
    return siivotut
