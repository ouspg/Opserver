"""kyberESR web-käyttöliittymän FastAPI-palvelin."""
import os
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from tietokanta import mallit

sovellus = FastAPI(title="kyberESR")

STAATTINEN = os.path.join(os.path.dirname(__file__), "staattinen")


@sovellus.get("/api/korkeakoulut")
def api_korkeakoulut() -> list[dict]:
    return mallit.hae_korkeakoulut()


@sovellus.get("/")
def juuri() -> FileResponse:
    return FileResponse(os.path.join(STAATTINEN, "index.html"))


sovellus.mount("/staattinen", StaticFiles(directory=STAATTINEN), name="staattinen")
