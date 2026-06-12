"""Ohut LLM-kääre — toimittaja vaihdetaan .env:n LLM_*-muuttujilla.

Käyttää OpenAI-yhteensopivaa chat completions -rajapintaa, joten mikä tahansa
sellaista tarjoava palvelu (OpenRouter, OpenAI, paikallinen palvelin) käy.
"""
import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

_MAX_TOKENIT = 4096
_AIKAKATKAISU_S = 120

# TCP slow start -tyylinen pyyntövälin säätö: jokainen onnistunut pyyntö
# puolittaa viiveen, 429 tuplaa sen ja pyyntö yritetään uudelleen.
_ALKUVIIVE_S = 1.0
_MAKSIMIVIIVE_S = 64.0
_MAX_YRITYKSET = 8
_viive_s = 0.0


def kysy(viesti: str, jarjestelma: str = "") -> str:
    """Lähettää viestin LLM:lle ja palauttaa vastauksen tekstinä."""
    global _viive_s
    perus_url = os.environ.get("LLM_PROVIDER")
    api_avain = os.environ.get("LLM_API_KEY")
    malli = os.environ.get("LLM_MODEL")
    if not (perus_url and api_avain and malli):
        raise EnvironmentError(
            "LLM_PROVIDER, LLM_API_KEY tai LLM_MODEL puuttuu .env-tiedostosta"
        )
    for _ in range(_MAX_YRITYKSET):
        if _viive_s:
            time.sleep(_viive_s)
        vastaus = requests.post(
            f"{perus_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_avain}"},
            json={
                "model": malli,
                "max_tokens": _MAX_TOKENIT,
                "messages": [
                    {"role": "system", "content": jarjestelma or "Olet tarkka ja analyyttinen apuri."},
                    {"role": "user", "content": viesti},
                ],
            },
            timeout=_AIKAKATKAISU_S,
        )
        if vastaus.status_code == 429:
            _viive_s = min(max(_viive_s * 2, _ALKUVIIVE_S), _MAKSIMIVIIVE_S)
            continue
        vastaus.raise_for_status()
        _viive_s = _viive_s / 2
        return vastaus.json()["choices"][0]["message"]["content"]
    raise RuntimeError(f"LLM-pyyntö epäonnistui: {_MAX_YRITYKSET} peräkkäistä 429-vastausta")
