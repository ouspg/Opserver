"""kyberESR web-käyttöliittymän FastAPI-palvelin."""
import os
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from tietokanta import mallit

sovellus = FastAPI(title="kyberESR")

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
                "KurssiNimi": k["KurssiNimi"],
                "Koodi": k.get("Koodi") or "",
                "Taso": k.get("Taso") or "",
                "Oppiaine": k.get("Oppiaine") or "",
                "Opintopisteet": k.get("Opintopisteet"),
                "vastaukset": [vastaus_kartta.get(k["KID"], {}).get(kys_id, "") for kys_id in kys_idt],
            }
            for k in kurssit
        ],
    }


@sovellus.get("/api/tutkimukset/{slug}")
def api_tutkimus(slug: str) -> dict:
    tutkimus = mallit.hae_tutkimus_slugilla(slug)
    if tutkimus is None:
        raise HTTPException(status_code=404, detail="Tutkimusta ei löydy")
    return tutkimus


@sovellus.get("/")
def juuri():
    return FileResponse(_INDEX, headers=_NO_STORE)


sovellus.mount("/staattinen", StaticFiles(directory=STAATTINEN), name="staattinen")


# Catch-all: SPA-reititys — palautetaan index.html kaikille ei-API -poluille
@sovellus.get("/{polku:path}")
def spa_reitti(polku: str):
    return FileResponse(_INDEX, headers=_NO_STORE)
