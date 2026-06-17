"""Korkeakoulun API-konfiguraation selvitys opinto-opasjärjestelmästä.

"Lisää korkeakoulu" -toiminto kutsuu tätä: selvittää API-origin-osoitteen ja
varmistaa että se vastaa. Tulos kirjataan Korkeakoulu.ApiOsoite-sarakkeeseen, ja
haku lukee kohdepalvelimen sieltä — ei kovakoodattuja per-korkeakoulu-osoitteita.

- Peppi: frontendin JS-bundle julistaa backend-originin (backendUrl). Sama
  mekanismi kaikilla instansseilla — Oulu osoittaa erilliseen opasbe-hostiin,
  muut omaan host­iinsa, kaikki samasta lähteestä luettuna.
- Sisu: API on samassa originissa kuin opinto-opas.
"""
import re

import requests

_AIKAKATKAISU = 30


def _normalisoi_host(arvo: str) -> str:
    """Siistii hostin: riisuu lainausmerkit/kauttaviivan, lisää https:// jos puuttuu."""
    arvo = arvo.strip().strip('"\'')
    if not re.match(r"^https?://", arvo):
        arvo = "https://" + arvo
    return arvo.rstrip("/")


def _etsi_backend_bundlesta(js: str) -> str:
    """Lukee Peppi-frontendin julistaman backend-originin sen JS-bundlesta.

    Peppi-SPA asettaa backendUrl-konfiguraation, esim. backendUrl:"opasbe.peppi.oulu.fi"
    tai backendUrl="https://opas.peppi.utu.fi" (kaksoispiste- tai yhtäsuuruus-syntaksi,
    skeemalla tai ilman).
    """
    osuma = re.search(r'backendUrl["\']?\s*[:=]\s*["\']([^"\']+)["\']', js)
    if not osuma:
        raise ValueError("backendUrl ei löytynyt Peppi-bundlesta")
    return _normalisoi_host(osuma.group(1))


def _bundle_url(frontend: str) -> str:
    html = requests.get(frontend.rstrip("/"), timeout=_AIKAKATKAISU).text
    osuma = re.search(r"(main\.[a-f0-9]+\.js)", html)
    if not osuma:
        raise ValueError(f"Peppi-frontendin JS-bundlea ei löytynyt: {frontend}")
    return f"{frontend.rstrip('/')}/{osuma.group(1)}"


def _varmista(url: str) -> None:
    requests.get(url, timeout=_AIKAKATKAISU).raise_for_status()


def selvita_konfiguraatio(ops_osoite: str, ops_tyyppi: str) -> dict:
    """Selvittää korkeakoulun API-originin. Palauttaa {'api_osoite': ...}.

    Nostaa ValueError / requests-poikkeuksen jos selvitys tai varmistus epäonnistuu.
    """
    front = ops_osoite.rstrip("/")
    if ops_tyyppi == "Peppi":
        js = requests.get(_bundle_url(front), timeout=_AIKAKATKAISU).text
        api = _etsi_backend_bundlesta(js)
        _varmista(f"{api}/api/navigation")
        return {"api_osoite": api}
    if ops_tyyppi == "Sisu":
        api = _normalisoi_host(front)
        _varmista(f"{api}/kori/api/curriculum-periods")
        return {"api_osoite": api}
    raise ValueError(f"Tuntematon OPS-tyyppi: {ops_tyyppi}")
