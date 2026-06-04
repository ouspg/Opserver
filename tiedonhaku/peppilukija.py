"""Peppi-järjestelmän opinto-oppaan lukija (esim. Oulun yliopisto).

Rajapinnan rakenne dokumentoitu tiedostossa tiedonhaku/PEPPI.md.
"""
from tiedonhaku.opslukija import OpsLukija

BACKEND = "https://opasbe.peppi.oulu.fi/api"
KAUSI = "2025-2026"

# Kurssikuvauksen "Taso"-osion teksti -> Kurssi-taulun Taso-enum.
TASO_KARTTA = {
    "yleisopinnot": "yleis",
    "perusopinnot": "perus",
    "aineopinnot": "aine",
    "syventävät opinnot": "syventävä",
}

# contentList-osiot, jotka kootaan kurssikuvaukseksi LLM:ää varten.
KUVAUS_OSIOT = [
    "Osaamistavoitteet",
    "Sisältö",
    "Suoritustavat",
    "Toteutustavat",
    "Esitietovaatimukset",
    "Lisätiedot",
]


def _fi(monikielinen: dict | None) -> str:
    """Poimii suomenkielisen arvon, fallbackina englanti."""
    if not monikielinen:
        return ""
    return (monikielinen.get("valueFi") or monikielinen.get("valueEn") or "").strip()


def paattele_taso(taso_teksti: str) -> str | None:
    return TASO_KARTTA.get(taso_teksti.strip().lower())


def _kokoa_kuvaus(sisalto: dict) -> str:
    osat = []
    for otsikko in KUVAUS_OSIOT:
        teksti = (sisalto.get(otsikko) or "").strip()
        if teksti:
            osat.append(f"{otsikko}:\n{teksti}")
    return "\n\n".join(osat)


class PeppiLukija(OpsLukija):
    def hae_kurssi(self, kurssi_id: str) -> dict:
        """Hakee ja jäsentää yhden kurssin Peppi-rajapinnasta."""
        url = f"{BACKEND}/course/{kurssi_id}?period={KAUSI}"
        return self._jasenna_kurssi(self._hae_json(url))

    def _jasenna_kurssi(self, data: dict) -> dict:
        sisalto = {
            _fi(osio.get("title")): (osio.get("content") or {}).get("valueFi", "") or ""
            for osio in data.get("contentList", [])
        }
        return {
            "kurssi_nimi": _fi(data.get("name")),
            "koodi": data.get("code"),
            "taso": paattele_taso(sisalto.get("Taso", "")),
            "oppiaine": (sisalto.get("Oppiaine") or "").strip(),
            "opintopisteet": data.get("credits"),
            "ops_kuvaus": _kokoa_kuvaus(sisalto),
            "lahde_id": data.get("id"),
        }

    def hae_kurssit(self) -> list[dict]:
        raise NotImplementedError("Koko opinto-oppaan läpikäynti toteutetaan seuraavassa vaiheessa.")
