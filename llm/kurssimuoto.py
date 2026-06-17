"""Kurssin tietojen muotoilu LLM-kehotteeseen.

Jaettu luokittelun ja arvioinnin kesken (DRY). Kuvausta EI katkaista: mallin
täytyy saada käyttöönsä kaikki opinto-oppaassa näkyvä tieto — kuvaus on tärkein
tieto, jonka perusteella luokittelu ja arviointi tehdään.
"""
import json


def kuvaus_tekstina(ops_kuvaus: str | None) -> str:
    """Muuntaa Peppi/Sisu-OpsKuvaus-JSONin luettavaksi tekstiksi kokonaisuudessaan."""
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
        return "\n".join(osat)
    except (ValueError, AttributeError):
        return str(ops_kuvaus)


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
