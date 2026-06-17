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


def hae_malli() -> str:
    """Palauttaa käytössä olevan LLM-mallin nimen."""
    return os.environ.get("LLM_MODEL", "")


def _tekstilohko(teksti: str, kakku: bool = False) -> dict:
    lohko = {"type": "text", "text": teksti}
    if kakku:
        lohko["cache_control"] = {"type": "ephemeral"}
    return lohko


def _rakenna_viestit(viesti: str, jarjestelma: str, vakaa_prefix: str | None) -> list[dict]:
    """Rakentaa chat-viestit. Jos vakaa_prefix annetaan, järjestelmäkehote ja viestin
    vakaa alkuosa merkitään välimuistiin (cache_control) — palveluntarjoaja joka ei
    tue välimuistia jättää merkinnän huomiotta (OpenRouter normalisoi)."""
    jarj = jarjestelma or "Olet tarkka ja analyyttinen apuri."
    if not vakaa_prefix:
        return [
            {"role": "system", "content": jarj},
            {"role": "user", "content": viesti},
        ]
    system = {"role": "system", "content": [_tekstilohko(jarj, kakku=True)]}
    if viesti.startswith(vakaa_prefix):
        loppu = viesti[len(vakaa_prefix):]
        user_sisalto = [_tekstilohko(vakaa_prefix, kakku=True)]
        if loppu:
            user_sisalto.append(_tekstilohko(loppu))
    else:
        user_sisalto = [_tekstilohko(viesti)]
    return [system, {"role": "user", "content": user_sisalto}]


def kysy(viesti: str, jarjestelma: str = "", json_muoto: bool = False,
         vakaa_prefix: str | None = None) -> str:
    """Lähettää viestin LLM:lle ja palauttaa vastauksen tekstinä.

    json_muoto=True lisää response_format: json_object pyyntöön, jolloin
    malli pakotetaan API-tasolla palauttamaan kelvollinen JSON-objekti.

    vakaa_prefix: viestin muuttumaton alkuosa (esim. järjestelmä + kehote +
    kysymykset), joka merkitään kehotevälimuistiin. Kun useat erät jakavat saman
    etuliitteen, sitä ei laskuteta/prosessoida uudelleen tukevilla malleilla.
    """
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
        runko = {
            "model": malli,
            "max_tokens": _MAX_TOKENIT,
            "messages": _rakenna_viestit(viesti, jarjestelma, vakaa_prefix),
        }
        if json_muoto:
            runko["response_format"] = {"type": "json_object"}
        vastaus = requests.post(
            f"{perus_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_avain}"},
            json=runko,
            timeout=_AIKAKATKAISU_S,
        )
        if vastaus.status_code == 429:
            _viive_s = min(max(_viive_s * 2, _ALKUVIIVE_S), _MAKSIMIVIIVE_S)
            continue
        vastaus.raise_for_status()
        _viive_s = _viive_s / 2
        data = vastaus.json()
        if "error" in data:
            virhe = data["error"]
            koodi = virhe.get("code", 0)
            viesti_teksti = virhe.get("message", str(virhe))
            if koodi == 429:
                _viive_s = min(max(_viive_s * 2, _ALKUVIIVE_S), _MAKSIMIVIIVE_S)
                continue
            raise RuntimeError(f"OpenRouter-virhe ({koodi}): {viesti_teksti}")
        valinnat = data.get("choices") or []
        if not valinnat:
            raise ValueError("LLM palautti tyhjän choices-listan")
        sisalto = valinnat[0]["message"]["content"]
        if sisalto is None:
            finish = valinnat[0].get("finish_reason", "?")
            raise ValueError(f"LLM palautti tyhjän vastauksen (finish_reason: {finish})")
        return sisalto
    raise RuntimeError(f"LLM-pyyntö epäonnistui: {_MAX_YRITYKSET} peräkkäistä 429-vastausta")
