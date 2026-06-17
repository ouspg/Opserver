"""kyberESR web-käyttöliittymän FastAPI-palvelin."""
import json
import os
import uuid
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from tietokanta import mallit
from llm import tiiviste, kehoteet

sovellus = FastAPI(title="kyberESR")

# --- Reaaliaikainen läsnäolo ja muokkaussessiot (WebSocket) ---

_yhteydet: dict[str, tuple[WebSocket, dict]] = {}

# avain = (tid, kid, kysid) → {uid: {nimimerkki, profiili, kursori}}
_muokkaussessiot: dict[tuple, dict[str, dict]] = {}
# avain = (tid, kid, kysid) → nykyinen tekstisisältö sessiossa
_muokkaus_teksti: dict[tuple, str] = {}

# avain = (tid, avain_str) → {uid: {nimimerkki, profiili, kursori}}
_raportti_sessiot: dict[tuple, dict[str, dict]] = {}
# avain = (tid, avain_str) → nykyinen tekstisisältö sessiossa
_raportti_teksti: dict[tuple, str] = {}


async def _laheta_muokkaussessio(avain: tuple) -> None:
    if avain not in _muokkaussessiot:
        return
    tid, kid, kysid = avain
    muokkaajat = [{"id": uid, **tiedot} for uid, tiedot in _muokkaussessiot[avain].items()]
    viesti = json.dumps({
        "tyyppi": "muokkaus-sessio",
        "tid": tid, "kid": kid, "kysid": kysid,
        "teksti": _muokkaus_teksti.get(avain, ""),
        "muokkaajat": muokkaajat,
    })
    for uid in list(_muokkaussessiot[avain].keys()):
        if uid in _yhteydet:
            try:
                await _yhteydet[uid][0].send_text(viesti)
            except Exception:
                pass


async def _laheta_raportti_sessio(avain: tuple) -> None:
    if avain not in _raportti_sessiot:
        return
    tid, osio_avain = avain
    muokkaajat = [{"id": uid, **tiedot} for uid, tiedot in _raportti_sessiot[avain].items()]
    viesti = json.dumps({
        "tyyppi": "raportti-sessio",
        "tid": tid, "avain": osio_avain,
        "teksti": _raportti_teksti.get(avain, ""),
        "muokkaajat": muokkaajat,
    })
    for uid in list(_raportti_sessiot[avain].keys()):
        if uid in _yhteydet:
            try:
                await _yhteydet[uid][0].send_text(viesti)
            except Exception:
                pass


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
            tyyppi = data.get("tyyppi")
            if tyyppi == "uutinen":
                aika = datetime.now().strftime("%H:%M")
                viesti = json.dumps({"tyyppi": "uutinen", "teksti": data.get("teksti", ""), "aika": aika})
                katkaistut = []
                for u, (ws2, _) in list(_yhteydet.items()):
                    try:
                        await ws2.send_text(viesti)
                    except Exception:
                        katkaistut.append(u)
                for u in katkaistut:
                    _yhteydet.pop(u, None)
            elif tyyppi == "muokkaus-liity":
                avain = (data.get("tid"), data.get("kid"), data.get("kysid"))
                if avain not in _muokkaussessiot:
                    _muokkaussessiot[avain] = {}
                    _muokkaus_teksti[avain] = mallit.hae_arviokommentti(*avain)
                kayttaja = _yhteydet.get(uid, (None, {}))[1]
                _muokkaussessiot[avain][uid] = {
                    "nimimerkki": kayttaja.get("nimimerkki", "?"),
                    "profiili": kayttaja.get("profiili", {}),
                    "kursori": 0,
                }
                await _laheta_muokkaussessio(avain)
            elif tyyppi == "muokkaus-teksti":
                avain = (data.get("tid"), data.get("kid"), data.get("kysid"))
                if avain in _muokkaussessiot:
                    _muokkaus_teksti[avain] = data.get("teksti", "")
                    if uid in _muokkaussessiot[avain]:
                        _muokkaussessiot[avain][uid]["kursori"] = data.get("kursori", 0)
                    await _laheta_muokkaussessio(avain)
            elif tyyppi == "muokkaus-poistu":
                avain = (data.get("tid"), data.get("kid"), data.get("kysid"))
                if avain in _muokkaussessiot:
                    _muokkaussessiot[avain].pop(uid, None)
                    if not _muokkaussessiot[avain]:
                        del _muokkaussessiot[avain]
                        _muokkaus_teksti.pop(avain, None)
                    else:
                        await _laheta_muokkaussessio(avain)
            elif tyyppi == "muokkaus-tallenna":
                avain = (data.get("tid"), data.get("kid"), data.get("kysid"))
                teksti = data.get("teksti", "")
                if avain[0] and avain[1] and avain[2]:
                    mallit.aseta_arviokommentti(*avain, teksti)
                    if avain in _muokkaus_teksti:
                        _muokkaus_teksti[avain] = teksti
            elif tyyppi == "raportti-liity":
                avain = (data.get("tid"), data.get("avain"))
                if avain not in _raportti_sessiot:
                    _raportti_sessiot[avain] = {}
                    _raportti_teksti[avain] = mallit.hae_raportti_osio(*avain)
                kayttaja = _yhteydet.get(uid, (None, {}))[1]
                _raportti_sessiot[avain][uid] = {
                    "nimimerkki": kayttaja.get("nimimerkki", "?"),
                    "profiili": kayttaja.get("profiili", {}),
                    "kursori": 0,
                }
                await _laheta_raportti_sessio(avain)
            elif tyyppi == "raportti-teksti":
                avain = (data.get("tid"), data.get("avain"))
                if avain in _raportti_sessiot:
                    _raportti_teksti[avain] = data.get("teksti", "")
                    if uid in _raportti_sessiot[avain]:
                        _raportti_sessiot[avain][uid]["kursori"] = data.get("kursori", 0)
                    await _laheta_raportti_sessio(avain)
            elif tyyppi == "raportti-poistu":
                avain = (data.get("tid"), data.get("avain"))
                if avain in _raportti_sessiot:
                    _raportti_sessiot[avain].pop(uid, None)
                    if not _raportti_sessiot[avain]:
                        del _raportti_sessiot[avain]
                        _raportti_teksti.pop(avain, None)
                    else:
                        await _laheta_raportti_sessio(avain)
            elif tyyppi == "raportti-tallenna":
                avain = (data.get("tid"), data.get("avain"))
                teksti = data.get("teksti", "")
                if avain[0] and avain[1]:
                    mallit.aseta_raportti_osio(*avain, teksti)
                    if avain in _raportti_teksti:
                        _raportti_teksti[avain] = teksti
            else:
                _yhteydet[uid] = (ws, data)
                await _laheta_kaikille()
    except WebSocketDisconnect:
        _yhteydet.pop(uid, None)
        for avain in list(_muokkaussessiot.keys()):
            if uid in _muokkaussessiot[avain]:
                del _muokkaussessiot[avain][uid]
                if not _muokkaussessiot[avain]:
                    del _muokkaussessiot[avain]
                    _muokkaus_teksti.pop(avain, None)
        for avain in list(_raportti_sessiot.keys()):
            if uid in _raportti_sessiot[avain]:
                del _raportti_sessiot[avain][uid]
                if not _raportti_sessiot[avain]:
                    del _raportti_sessiot[avain]
                    _raportti_teksti.pop(avain, None)
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
    tid = tutkimus["TID"]
    rivit = mallit.hae_kurssit_luokituksilla(tid)

    # Ryhmittele HITL-historia kursseittain (vanhimmasta uusimpaan)
    historia: dict[int, list[dict]] = {}
    for h in mallit.hae_hitl_historia(tid):
        kid = h["KID"]
        if kid not in historia:
            historia[kid] = []
        historia[kid].append({
            "UusiTila": bool(h["UusiTila"]),
            "Perustelu": h["Perustelu"],
            "KayttajaNimi": h["KayttajaNimi"],
        })

    tulos = []
    for r in rivit:
        d = {k: v for k, v in r.items() if k not in _KURSSI_LISTA_KENTAT}
        kid = d["KID"]
        korjaukset = historia.get(kid, [])
        d["HitlKorjaukset"] = korjaukset
        # Tekoälyn alkuperäinen tila: ensimmäisen korjauksen käänteinen
        d["AiMukana"] = (not korjaukset[0]["UusiTila"]) if korjaukset else d.get("Mukana")
        tulos.append(d)
    return tulos


@sovellus.get("/api/tutkimukset/{slug}/arvioinnit")
def api_tutkimus_arvioinnit(slug: str) -> dict:
    tutkimus = mallit.hae_tutkimus_slugilla(slug)
    if tutkimus is None:
        raise HTTPException(status_code=404, detail="Tutkimusta ei löydy")
    tid = tutkimus["TID"]
    kysymykset = mallit.hae_kysymykset(tid)
    kurssit = mallit.hae_valitut_kurssit(tid)
    vastaukset_lista = mallit.hae_vastaukset(tid)
    kommentit_lista = mallit.hae_arviokommentit_kaikki(tid)

    # Nykyiset kysymystiivisteet: tunnistavat vastaukset jotka on generoitu
    # vanhentuneeseen kysymykseen/kehotteeseen (ennen seuraavaa LLM-ajoa).
    jarjestelma = kehoteet.lue("arviointi_jarjestelma.txt")
    nyky_tiiviste = tiiviste.kysymystiivisteet(
        tutkimus.get("Arviointikehote") or "", jarjestelma, kysymykset
    )

    vastaus_kartta: dict[int, dict[int, dict]] = {}
    for v in vastaukset_lista:
        kid = v["KID"]
        if kid not in vastaus_kartta:
            vastaus_kartta[kid] = {}
        on_vastaus = bool((v.get("Vastaus") or "").strip()) or v.get("Luokka") is not None or v.get("Pisteet") is not None
        vastaus_kartta[kid][v["KysID"]] = {
            "vastaus": v.get("Vastaus") or "",
            "luokka": v.get("Luokka"),
            "pisteet": v.get("Pisteet"),
            "vanhentunut": on_vastaus and v.get("Kehotetiiviste") != nyky_tiiviste.get(v["KysID"]),
        }

    kommentti_kartta: dict[int, dict[int, str]] = {}
    for k in kommentit_lista:
        kid = k["KID"]
        if kid not in kommentti_kartta:
            kommentti_kartta[kid] = {}
        kommentti_kartta[kid][k["KysID"]] = k["Kommentti"]

    kys_idt = [k["KysID"] for k in kysymykset]
    tyhjä_vastaus = {"vastaus": "", "luokka": None, "pisteet": None, "vanhentunut": False}
    return {
        "kysymykset": [
            {
                "KysID": k["KysID"],
                "Kysymys": k["Kysymys"],
                "Luokittelu": k.get("Luokittelu", "vapaa_teksti"),
                "LuokitteluMaarittely": k.get("LuokitteluMaarittely"),
            }
            for k in kysymykset
        ],
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
                "vastaukset": [vastaus_kartta.get(k["KID"], {}).get(kys_id, tyhjä_vastaus) for kys_id in kys_idt],
                "kommentit": {kys_id: kommentti_kartta.get(k["KID"], {}).get(kys_id, "") for kys_id in kys_idt},
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


@sovellus.get("/api/tutkimukset/{slug}/raportti")
def api_raportti(slug: str) -> dict:
    tutkimus = mallit.hae_tutkimus_slugilla(slug)
    if tutkimus is None:
        raise HTTPException(status_code=404, detail="Tutkimusta ei löydy")
    osiot = mallit.hae_raportti_osiot(tutkimus["TID"])
    return {"tid": tutkimus["TID"], "osiot": osiot}


@sovellus.get("/api/tutkimukset/{slug}/raportti/tilastot")
def api_raportti_tilastot(slug: str) -> dict:
    """Palauttaa per-kysymys-tilastot rakenteellisille arvioinneille ilman LLM-kutsua."""
    tutkimus = mallit.hae_tutkimus_slugilla(slug)
    if tutkimus is None:
        raise HTTPException(status_code=404, detail="Tutkimusta ei löydy")
    tid = tutkimus["TID"]
    kysymykset = mallit.hae_kysymykset(tid)
    vastaukset_lista = mallit.hae_vastaukset(tid)

    # Rakenna per-kysymys indeksi vastauksista
    v_per_kys: dict[int, list[dict]] = {k["KysID"]: [] for k in kysymykset}
    for v in vastaukset_lista:
        kysid = v["KysID"]
        if kysid in v_per_kys:
            v_per_kys[kysid].append(v)

    tulos_kysymykset = []
    for k in kysymykset:
        kysid = k["KysID"]
        luokittelu = k.get("Luokittelu", "vapaa_teksti")
        vastaukset = v_per_kys.get(kysid, [])
        kohta: dict = {"kysid": kysid, "kysymys": k["Kysymys"], "luokittelu": luokittelu}

        if luokittelu == "luokittelu":
            jakauma: dict[str, int] = {}
            for v in vastaukset:
                luokka = v.get("Luokka") or ""
                if luokka:
                    jakauma[luokka] = jakauma.get(luokka, 0) + 1
            kohta["jakauma"] = jakauma
            kohta["yhteensa"] = sum(jakauma.values())

        elif luokittelu == "asteikko":
            pisteet_arvot = [v["Pisteet"] for v in vastaukset if v.get("Pisteet") is not None]
            jakauma_num: dict[str, int] = {}
            for p in pisteet_arvot:
                avain = str(int(round(p)))
                jakauma_num[avain] = jakauma_num.get(avain, 0) + 1
            kohta["yhteensa"] = len(pisteet_arvot)
            kohta["jakauma"] = jakauma_num
            if pisteet_arvot:
                kohta["keskiarvo"] = round(sum(pisteet_arvot) / len(pisteet_arvot), 2)
                kohta["minimi"] = min(pisteet_arvot)
                kohta["maksimi"] = max(pisteet_arvot)
            else:
                kohta["keskiarvo"] = None
                kohta["minimi"] = None
                kohta["maksimi"] = None

        else:  # vapaa_teksti
            kohta["yhteensa"] = sum(1 for v in vastaukset if v.get("Vastaus"))

        tulos_kysymykset.append(kohta)

    return {"kysymykset": tulos_kysymykset}


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
