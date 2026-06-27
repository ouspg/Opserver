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


def _monikielinen_teksti(arvo) -> str:
    """Sisun monikielinen kenttä ({fi/en: html}) → suomenkielinen teksti ilman HTML:ää."""
    if not isinstance(arvo, dict):
        return ""
    teksti = arvo.get("fi") or arvo.get("en") or ""
    return re.sub(r"<[^>]+>", " ", teksti).strip()


def _peppi_kuvaus(data: dict) -> str:
    osat = []
    for osio in data.get("contentList", []):
        otsikko = (osio.get("title") or {}).get("valueFi", "")
        teksti = ((osio.get("content") or {}).get("valueFi") or "").strip()
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
