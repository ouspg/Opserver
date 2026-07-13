"""Mallitiedot: hakee saatavilla olevat mallit ja niiden ominaisuudet palveluntarjoajalta.

Käytetään mallin saatavuustarkistukseen (ennen LLM-ajoa), LLM-asetusvalikkoon ja
välimuistituen tunnistukseen. Erillään kutsu.py:stä, joka on pelkkä pyyntökääre.
"""
import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

_AIKAKATKAISU_S = 30
_mallit_kakku: list[dict] | None = None  # prosessin sisäinen välimuisti
_haettu: float | None = None              # milloin kakku täytettiin (epoch-sekunnit)


def _perus_url() -> str:
    url = os.environ.get("LLM_PROVIDER")
    if not url:
        raise EnvironmentError("LLM_PROVIDER puuttuu .env-tiedostosta")
    return url.rstrip("/")


def hae_mallit(paivita: bool = False) -> list[dict]:
    """Saatavilla olevat mallit palveluntarjoajalta (OpenAI-yhteensopiva /models).

    Tulos kakutetaan prosessiin; paivita=True hakee listan uudelleen.
    """
    global _mallit_kakku, _haettu
    if _mallit_kakku is not None and not paivita:
        return _mallit_kakku
    api_avain = os.environ.get("LLM_API_KEY")
    headers = {"Authorization": f"Bearer {api_avain}"} if api_avain else {}
    vastaus = requests.get(f"{_perus_url()}/models", headers=headers, timeout=_AIKAKATKAISU_S)
    vastaus.raise_for_status()
    _mallit_kakku = vastaus.json().get("data", [])
    _haettu = time.time()
    return _mallit_kakku


def tuoreus_teksti() -> str | None:
    """Ihmisluettava kuvaus mallilistan iästä, tai None jos listaa ei ole vielä haettu."""
    if _haettu is None:
        return None
    ika = max(0, int(time.time() - _haettu))
    if ika < 60:
        ikateksti = f"{ika} s sitten"
    elif ika < 3600:
        ikateksti = f"{ika // 60} min sitten"
    else:
        ikateksti = f"{ika // 3600} h {ika % 3600 // 60} min sitten"
    return f"haettu {time.strftime('%H:%M', time.localtime(_haettu))} ({ikateksti})"


def hae_malli_tiedot(malli: str) -> dict | None:
    """Yhden mallin tietuerivi /models-listasta, tai None jos ei löydy."""
    return next((m for m in hae_mallit() if m.get("id") == malli), None)


def on_saatavilla(malli: str) -> bool:
    return hae_malli_tiedot(malli) is not None


def tukee_valimuistia(malli_tiedot: dict) -> bool:
    """True jos malli tukee kehotevälimuistia (palveluntarjoaja hinnoittelee cache-luvun)."""
    return "input_cache_read" in (malli_tiedot.get("pricing") or {})


def muoto_kentta(malli_tiedot: dict) -> str:
    """Lyhyt merkintä mallin rakenteisen ulostulon tuesta (OpenRouterin
    supported_parameters) — vahvin ensin. Tyhjä kenttä → '?' (ei tietoa)."""
    tuetut = malli_tiedot.get("supported_parameters")
    if not tuetut:
        return "?"
    tuetut = set(tuetut)
    if "structured_outputs" in tuetut:
        return "skeema"
    if "response_format" in tuetut:
        return "json"
    if "tools" in tuetut:
        return "tools"
    return "—"


def muototuki_varoitus(malli: str | None = None) -> str | None:
    """Varoitusteksti jos malli EI ilmoita tukevansa response_formatia, muuten None.

    Perustuu jo haetun /models-listan supported_parameters-kenttään — ei uutta
    pyyntöä. Palauttaa None jos mallia ei löydy tai kenttää ei ole (ei voida
    päätellä; saatavuus tarkistetaan erikseen)."""
    malli = malli or os.environ.get("LLM_MODEL", "")
    tiedot = hae_malli_tiedot(malli)
    tuetut = tiedot.get("supported_parameters") if tiedot else None
    if not tuetut:
        return None
    if "response_format" not in set(tuetut):
        return ("Malli ei ilmoita tukevansa response_formatia — JSON-tila ei "
                "välttämättä toimi. Valitse malli jonka 'muoto?' on json tai skeema.")
    return None


def _hinta_per_milj(arvo: str | None) -> float:
    """OpenRouterin per-token-hinta ($/token) → $/miljoona tokenia."""
    try:
        return float(arvo or 0) * 1_000_000
    except (TypeError, ValueError):
        return 0.0


_SARAKEOTSIKOT = ("Mallin nimi", "Hinta", "konteksti", "muoto?", "välimuisti?")
_EROTIN = "  |  "


def _mallin_kentat(malli_tiedot: dict) -> tuple[str, str, str, str, str]:
    """Yhden mallin sarakearvot: (id, hinta, konteksti, muoto, välimuisti)."""
    pricing = malli_tiedot.get("pricing") or {}
    sisaan = _hinta_per_milj(pricing.get("prompt"))
    ulos = _hinta_per_milj(pricing.get("completion"))
    hinta = "ilmainen" if sisaan == 0 and ulos == 0 else f"${sisaan:.2f}/${ulos:.2f} per Mtok"
    ctx = malli_tiedot.get("context_length") or 0
    konteksti = f"{ctx // 1000}k" if ctx else "?"
    muoto = muoto_kentta(malli_tiedot)
    valimuisti = "kyllä" if tukee_valimuistia(malli_tiedot) else "—"
    return malli_tiedot.get("id", "?"), hinta, konteksti, muoto, valimuisti


def muotoile_taulukko(mallit: list[dict]) -> tuple[list[str], list[str]]:
    """Muotoilee mallit tasatuksi taulukoksi.

    Palauttaa (otsikkorivit, datarivit), missä otsikkorivit = [sarakeotsikot, erotinviiva].
    Sarakkeet tasataan leveimmän arvon mukaan: nimi ja hinta vasemmalle, konteksti
    keskelle, välimuisti vasemmalle (viimeinen sarake). Kaikki rivit ovat samanlevyisiä.
    """
    kentat = [_mallin_kentat(m) for m in mallit]
    n = len(_SARAKEOTSIKOT)
    lev = [len(_SARAKEOTSIKOT[s]) for s in range(n)]
    for rivi in kentat:
        for s in range(n):
            lev[s] = max(lev[s], len(rivi[s]))

    def koosta(nimi, hinta, ktx, muoto, valimuisti):
        return _EROTIN.join([nimi.ljust(lev[0]), hinta.ljust(lev[1]),
                             ktx.center(lev[2]), muoto.ljust(lev[3]), valimuisti.ljust(lev[4])])

    otsikkorivi = koosta(*_SARAKEOTSIKOT)
    viiva = "-" * len(otsikkorivi)
    datarivit = [koosta(*rivi) for rivi in kentat]
    return [otsikkorivi, viiva], datarivit


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
