"""Mallitiedot: hakee saatavilla olevat mallit ja niiden ominaisuudet palveluntarjoajalta.

Käytetään mallin saatavuustarkistukseen (ennen LLM-ajoa), LLM-asetusvalikkoon ja
välimuistituen tunnistukseen. Erillään kutsu.py:stä, joka on pelkkä pyyntökääre.
"""
import os
import requests

_AIKAKATKAISU_S = 30
_mallit_kakku: list[dict] | None = None  # prosessin sisäinen välimuisti


def _perus_url() -> str:
    url = os.environ.get("LLM_PROVIDER")
    if not url:
        raise EnvironmentError("LLM_PROVIDER puuttuu .env-tiedostosta")
    return url.rstrip("/")


def hae_mallit(paivita: bool = False) -> list[dict]:
    """Saatavilla olevat mallit palveluntarjoajalta (OpenAI-yhteensopiva /models).

    Tulos kakutetaan prosessiin; paivita=True hakee listan uudelleen.
    """
    global _mallit_kakku
    if _mallit_kakku is not None and not paivita:
        return _mallit_kakku
    api_avain = os.environ.get("LLM_API_KEY")
    headers = {"Authorization": f"Bearer {api_avain}"} if api_avain else {}
    vastaus = requests.get(f"{_perus_url()}/models", headers=headers, timeout=_AIKAKATKAISU_S)
    vastaus.raise_for_status()
    _mallit_kakku = vastaus.json().get("data", [])
    return _mallit_kakku


def hae_malli_tiedot(malli: str) -> dict | None:
    """Yhden mallin tietuerivi /models-listasta, tai None jos ei löydy."""
    return next((m for m in hae_mallit() if m.get("id") == malli), None)


def on_saatavilla(malli: str) -> bool:
    return hae_malli_tiedot(malli) is not None


def tarkista_saatavuus(malli: str | None = None) -> None:
    """Nostaa virheen jos malli ei ole saatavilla. Oletuksena .env:n LLM_MODEL.

    EnvironmentError jos mallia ei ole asetettu, RuntimeError jos sitä ei
    löydy palveluntarjoajan listalta.
    """
    malli = malli or os.environ.get("LLM_MODEL", "")
    if not malli:
        raise EnvironmentError("LLM_MODEL puuttuu .env-tiedostosta")
    if not on_saatavilla(malli):
        raise RuntimeError(
            f"Malli '{malli}' ei ole saatavilla palveluntarjoajalla. "
            f"Tarkista LLM_MODEL .env-tiedostossa (ks. LLM-asetukset-valikko)."
        )
