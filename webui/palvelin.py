"""kyberESR web-käyttöliittymän FastAPI-palvelin."""
import json
import os
import uuid
from typing import Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from tietokanta import mallit

sovellus = FastAPI(title="kyberESR")

# --- Reaaliaikainen läsnäolo (WebSocket) ---

_yhteydet: dict[str, tuple[WebSocket, dict]] = {}


async def _laheta_kaikille() -> None:
    kayttajat = [{"id": uid, **data} for uid, (_, data) in _yhteydet.items() if data]
    viesti = json.dumps({"tyyppi": "kayttajat", "data": kayttajat})
    katkaistut = []
    for uid, (ws, _) in list(_yhteydet.items()):
        try:
            await ws.send_text(viesti)
        except Exception:
            katkaistut.append(uid)
    for uid in katkaistut:
        _yhteydet.pop(uid, None)


@sovellus.websocket("/ws")
async def ws_kayttajat(ws: WebSocket) -> None:
    await ws.accept()
    uid = str(uuid.uuid4())[:8]
    _yhteydet[uid] = (ws, {})
    try:
        await ws.send_text(json.dumps({"tyyppi": "oma-id", "id": uid}))
        while True:
            data = await ws.receive_json()
            _yhteydet[uid] = (ws, data)
            await _laheta_kaikille()
    except WebSocketDisconnect:
        _yhteydet.pop(uid, None)
        await _laheta_kaikille()

STAATTINEN = os.path.join(os.path.dirname(__file__), "staattinen")
_INDEX = os.path.join(STAATTINEN, "index.html")
_NO_STORE = {"Cache-Control": "no-store"}

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


@sovellus.get("/api/tutkimukset")
def api_tutkimukset() -> list[dict]:
    return mallit.hae_tutkimukset_yhteenvedolla()


@sovellus.get("/api/tutkimukset/{slug}/kurssit")
def api_tutkimus_kurssit(slug: str) -> list[dict]:
    tutkimus = mallit.hae_tutkimus_slugilla(slug)
    if tutkimus is None:
        raise HTTPException(status_code=404, detail="Tutkimusta ei löydy")
    rivit = mallit.hae_valitut_kurssit(tutkimus["TID"])
    return [{k: v for k, v in r.items() if k not in _KURSSI_LISTA_KENTAT} for r in rivit]


@sovellus.get("/api/tutkimukset/{slug}/luokitukset")
def api_tutkimus_luokitukset(slug: str) -> list[dict]:
    tutkimus = mallit.hae_tutkimus_slugilla(slug)
    if tutkimus is None:
        raise HTTPException(status_code=404, detail="Tutkimusta ei löydy")
    rivit = mallit.hae_kurssit_luokituksilla(tutkimus["TID"])
    return [{k: v for k, v in r.items() if k not in _KURSSI_LISTA_KENTAT} for r in rivit]


@sovellus.get("/api/tutkimukset/{slug}/arvioinnit")
def api_tutkimus_arvioinnit(slug: str) -> dict:
    tutkimus = mallit.hae_tutkimus_slugilla(slug)
    if tutkimus is None:
        raise HTTPException(status_code=404, detail="Tutkimusta ei löydy")
    tid = tutkimus["TID"]
    kysymykset = mallit.hae_kysymykset(tid)
    kurssit = mallit.hae_valitut_kurssit(tid)
    vastaukset_lista = mallit.hae_vastaukset(tid)

    vastaus_kartta: dict[int, dict[int, str]] = {}
    for v in vastaukset_lista:
        kid = v["KID"]
        if kid not in vastaus_kartta:
            vastaus_kartta[kid] = {}
        vastaus_kartta[kid][v["KysID"]] = v["Vastaus"]

    kys_idt = [k["KysID"] for k in kysymykset]
    return {
        "kysymykset": [{"KysID": k["KysID"], "Kysymys": k["Kysymys"]} for k in kysymykset],
        "kurssit": [
            {
                "KID": k["KID"],
                "KKID": k.get("KKID"),
                "LahdeId": k.get("LahdeId") or "",
                "KurssiNimi": k["KurssiNimi"],
                "Koodi": k.get("Koodi") or "",
                "Opetusvuosi": k.get("Opetusvuosi") or "",
                "Taso": k.get("Taso") or "",
                "Oppiaine": k.get("Oppiaine") or "",
                "Opintopisteet": k.get("Opintopisteet"),
                "vastaukset": [vastaus_kartta.get(k["KID"], {}).get(kys_id, "") for kys_id in kys_idt],
            }
            for k in kurssit
        ],
    }


class HitlPyynto(BaseModel):
    uusi_tila: bool
    perustelu: str
    nimi: str
    sahkoposti: str


@sovellus.post("/api/tutkimukset/{slug}/kurssit/{kid}/hitl")
def api_hitl_korjaus(slug: str, kid: int, pyynto: HitlPyynto) -> dict:
    tutkimus = mallit.hae_tutkimus_slugilla(slug)
    if tutkimus is None:
        raise HTTPException(status_code=404, detail="Tutkimusta ei löydy")
    mallit.tallenna_hitl_korjaus(
        tutkimus["TID"], kid, pyynto.uusi_tila,
        pyynto.perustelu, pyynto.nimi, pyynto.sahkoposti,
    )
    return {"ok": True}


@sovellus.get("/api/tutkimukset/{slug}")
def api_tutkimus(slug: str) -> dict:
    tutkimus = mallit.hae_tutkimus_slugilla(slug)
    if tutkimus is None:
        raise HTTPException(status_code=404, detail="Tutkimusta ei löydy")
    tutkimus["Kysymykset"] = mallit.hae_kysymykset(tutkimus["TID"])
    return tutkimus


@sovellus.get("/")
def juuri():
    return FileResponse(_INDEX, headers=_NO_STORE)


sovellus.mount("/staattinen", StaticFiles(directory=STAATTINEN), name="staattinen")


# Catch-all: SPA-reititys — palautetaan index.html kaikille ei-API -poluille
@sovellus.get("/{polku:path}")
def spa_reitti(polku: str):
    return FileResponse(_INDEX, headers=_NO_STORE)
