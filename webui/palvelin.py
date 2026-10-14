"""Opserver web-käyttöliittymän FastAPI-palvelin: kokoaa reitit (webui/reitit_*.py,
webui/yhteistyo.py), middlewaret ja staattiset tiedostot. Käynnistys:
uvicorn webui.palvelin:sovellus."""
import functools
import html
import os
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from webui import yhteistyo, reitit_katalogi, reitit_luokitukset, reitit_arvioinnit, reitit_raportti, reitit_info
from webui.autentikointi import PerusAutentikointi

sovellus = FastAPI(title="Opserver")
sovellus.add_middleware(PerusAutentikointi)
# Pakkaus: JSON/JS pienenee ~5–10× — ratkaisevaa huonolla yhteydellä (tuotanto ei pakkaa muualla).
sovellus.add_middleware(GZipMiddleware, minimum_size=1000)

# Järjestys = alkuperäinen rekisteröintijärjestys; SPA:n catch-all viimeisenä.
for moduuli in (yhteistyo, reitit_katalogi, reitit_luokitukset, reitit_arvioinnit, reitit_raportti, reitit_info):
    sovellus.include_router(moduuli.reititin)

STAATTINEN = os.path.join(os.path.dirname(__file__), "staattinen")
_INDEX = os.path.join(STAATTINEN, "index.html")
_NO_STORE = {"Cache-Control": "no-store"}


_VALIMUISTIT = [reitit_katalogi._korkeakoulut_valimuistissa, reitit_katalogi._lukuvuodet_valimuistissa,
                reitit_katalogi._tasot_valimuistissa, reitit_katalogi._kurssit_valimuistissa,
                reitit_raportti._raportti_tilanne_valimuistissa]


def tyhjenna_valimuistit() -> None:
    """Nollaa kaikki staattiset välimuistit (esim. hakurobotin ajon jälkeen / testit)."""
    for f in _VALIMUISTIT:
        f.tyhjenna()


@functools.cache
def _index_html() -> str:
    """index.html, johon upotettu ajossa oleva versio: SPA:n versiotarkistuksen lähtötaso on
    aina se versio, jonka JS oikeasti ladattiin (ei erillistä /api/info-hakua, #117)."""
    with open(_INDEX, encoding="utf-8") as f:
        return f.read().replace("__OPSERVER_VERSIO__", html.escape(reitit_info._versio()[0]))


@sovellus.get("/")
def juuri():
    return HTMLResponse(_index_html(), headers=_NO_STORE)


sovellus.mount("/staattinen", StaticFiles(directory=STAATTINEN), name="staattinen")


# Catch-all: SPA-reititys — palautetaan index.html kaikille ei-API -poluille
@sovellus.get("/{polku:path}")
def spa_reitti(polku: str):
    return juuri()
