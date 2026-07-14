"""Ohut LLM-kääre — toimittaja vaihdetaan .env:n LLM_*-muuttujilla.

Käyttää OpenAI-yhteensopivaa chat completions -rajapintaa, joten mikä tahansa
sellaista tarjoava palvelu (OpenRouter, OpenAI, paikallinen palvelin) käy.
"""
import os
import threading
import time
import requests
from dotenv import load_dotenv
from llm import asetukset

load_dotenv()

_MAX_TOKENIT = 4096
_AIKAKATKAISU_S = 120

# Suojaa globaalin tahdistus-/backoff-tilan, kun useat säikeet (rinnakkainen
# eräajo) kutsuvat kysy():tä samanaikaisesti. Vain pienet tilapäivitykset ja
# tahdistus-uni pidetään lukon sisällä; itse HTTP-pyyntö tehdään lukon
# ulkopuolella, jotta kutsut etenevät rinnakkain.
_lukko = threading.Lock()

# TCP slow start -tyylinen pyyntövälin säätö: jokainen onnistunut pyyntö
# puolittaa viiveen, 429 tuplaa sen ja pyyntö yritetään uudelleen.
_ALKUVIIVE_S = 1.0
_MAKSIMIVIIVE_S = 64.0
_MAX_YRITYKSET = 8
_viive_s = 0.0

# Ennakoiva tahdistus: vähimmäisväli peräkkäisten pyyntöjen välillä. Toisin kuin
# yllä oleva reaktiivinen backoff (joka käynnistyy vasta 429:n jälkeen), tämä
# pitää pyyntötahdin valmiiksi rajojen alapuolella eikä tuhlaa vrk-kiintiötä
# 429-törmäyksiin. ":free"-mallit noudattavat OpenRouterin 20 pyyntöä/min -rajaa
# (= 3.0 s/pyyntö); 3.5 s antaa turvamarginaalin (~17/min). Maksulliset mallit
# saavat lyhyemmän välin, koska niiden rajat ovat korkeammat.
_TAHDISTUS_FREE_S = 3.5
_TAHDISTUS_MAKSU_S = 0.5
_edellinen_pyynto = 0.0

# Viimeisimmän onnistuneen pyynnön token-käyttö + finish_reason. Mittauksia
# (esim. eräkoon viritys) varten; pipelinen logiikka ei riipu tästä.
_viimeisin_kaytto: dict = {}


def hae_malli() -> str:
    """Palauttaa käytössä olevan LLM-mallin nimen."""
    return os.environ.get("LLM_MODEL", "")


def hae_viimeisin_kaytto() -> dict:
    """Palauttaa viimeisimmän onnistuneen pyynnön usage-tiedot ja finish_reasonin."""
    return dict(_viimeisin_kaytto)


def _on_free_malli(malli: str) -> bool:
    """Tunnistaa OpenRouterin ilmaismallit ":free"-suffiksista."""
    return malli.strip().endswith(":free")


def _tahdistusvali(malli: str) -> float:
    """Vähimmäisväli pyyntöjen välillä mallin hintaluokan mukaan (.env ohittaa oletuksen)."""
    if _on_free_malli(malli):
        return asetukset.lue_float("LLM_TAHDISTUS_FREE_S", _TAHDISTUS_FREE_S)
    return asetukset.lue_float("LLM_TAHDISTUS_MAKSU_S", _TAHDISTUS_MAKSU_S)


def _tahdista(malli: str) -> None:
    """Nukkuu tarvittaessa niin, että edellisestä pyynnöstä on kulunut
    vähintään mallin tahdistusväli. Päivittää lähetyshetken globaaliin tilaan.

    Lukko pidetään unen ajan, jolloin rinnakkaisetkin säikeet läpäisevät portin
    yksitellen vähintään tahdistusvälin päässä toisistaan → kokonaispyyntötahti
    pysyy rajan alapuolella riippumatta rinnakkaisuusasteesta."""
    global _edellinen_pyynto
    vali = _tahdistusvali(malli)
    with _lukko:
        kulunut = time.monotonic() - _edellinen_pyynto
        if kulunut < vali:
            time.sleep(vali - kulunut)
        _edellinen_pyynto = time.monotonic()


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
    global _viive_s, _viimeisin_kaytto
    perus_url = os.environ.get("LLM_PROVIDER")
    api_avain = os.environ.get("LLM_API_KEY")
    malli = os.environ.get("LLM_MODEL")
    if not (perus_url and api_avain and malli):
        raise EnvironmentError(
            "LLM_PROVIDER, LLM_API_KEY tai LLM_MODEL puuttuu .env-tiedostosta"
        )
    _tahdista(malli)
    for _ in range(_MAX_YRITYKSET):
        with _lukko:
            viive = _viive_s
        if viive:
            time.sleep(viive)
        runko = {
            "model": malli,
            "max_tokens": asetukset.lue_int("LLM_MAX_TOKENIT", _MAX_TOKENIT),
            "messages": _rakenna_viestit(viesti, jarjestelma, vakaa_prefix),
        }
        if json_muoto:
            runko["response_format"] = {"type": "json_object"}
            # Reititä vain tarjoajille jotka oikeasti tukevat response_formatia —
            # muuten OpenRouter voi valita tarjoajan joka ohittaa sen ja palauttaa
            # roskaa/tyhjää (ks. lokin "OpenInference"-502:t). OpenRouter-kohtainen.
            runko["provider"] = {"require_parameters": True}
        vastaus = requests.post(
            f"{perus_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_avain}"},
            json=runko,
            timeout=_AIKAKATKAISU_S,
        )
        if vastaus.status_code == 429:
            with _lukko:
                _viive_s = min(max(_viive_s * 2, _ALKUVIIVE_S), _MAKSIMIVIIVE_S)
            continue
        vastaus.raise_for_status()
        with _lukko:
            _viive_s = _viive_s / 2
        data = vastaus.json()
        if "error" in data:
            virhe = data["error"]
            koodi = virhe.get("code", 0)
            viesti_teksti = virhe.get("message", str(virhe))
            if koodi == 429:
                with _lukko:
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
        kaytto = dict(data.get("usage") or {})
        kaytto["finish_reason"] = valinnat[0].get("finish_reason")
        with _lukko:
            _viimeisin_kaytto = kaytto
        return sisalto
    raise RuntimeError(f"LLM-pyyntö epäonnistui: {_MAX_YRITYKSET} peräkkäistä 429-vastausta")
