"""kyberESR web-käyttöliittymän FastAPI-palvelin."""
import os
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from tietokanta import mallit

sovellus = FastAPI(title="kyberESR")

STAATTINEN = os.path.join(os.path.dirname(__file__), "staattinen")

# Kentät jotka jätetään pois kurssilistasta (suuri JSON-kenttä)
_KURSSI_LISTA_KENTAT = {"OpsKuvaus"}


@sovellus.get("/api/korkeakoulut")
def api_korkeakoulut() -> list[dict]:
    return mallit.hae_korkeakoulut()


@sovellus.get("/api/kurssit")
def api_kurssit(kkid: Optional[int] = None) -> list[dict]:
    rivit = mallit.hae_kurssit(kkid=kkid)
    return [{k: v for k, v in r.items() if k not in _KURSSI_LISTA_KENTAT} for r in rivit]


@sovellus.get("/api/kurssit/{kid}")
def api_kurssi(kid: int) -> dict:
    kurssi = mallit.hae_kurssi(kid)
    if kurssi is None:
        raise HTTPException(status_code=404, detail="Kurssia ei löydy")
    return kurssi


@sovellus.get("/")
def juuri() -> FileResponse:
    return FileResponse(os.path.join(STAATTINEN, "index.html"))


sovellus.mount("/staattinen", StaticFiles(directory=STAATTINEN), name="staattinen")
