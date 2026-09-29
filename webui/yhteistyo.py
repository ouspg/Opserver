"""Reaaliaikainen yhteistyö (WebSocket): läsnäolo, jaetut lomakkeet (HITL-korjaukset ja
raporttiosioiden yhteismuokkaus) ja jaetut suodatinnäkymät. Tila on vain muistissa."""
import asyncio
import json
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from tietokanta import mallit
from webui.riippuvuudet import TutkimusSlugista


reititin = APIRouter()


# --- Reaaliaikainen läsnäolo ja muokkaussessiot (WebSocket) ---

_yhteydet: dict[str, tuple[WebSocket, dict]] = {}

# Jaetut korjauslomakkeet (HITL-modaalit): avain (esim. "hitl:1:7", "arvio:1:7:3") →
# {"arvot": {kentta: arvo}, "jasenet": {uid: {"kentta": str|None, "kursori": int}}}.
# Ensimmäisen avaajan arvot alustavat lomakkeen; myöhemmät liittyjät saavat ne.
_lomakkeet: dict[str, dict] = {}

# Jaetut suodatinnäkymät (välilehdet): sivupolku → [{id, nimi, suodatin}].
# ponytail: vain muistissa — katoavat palvelimen uudelleenkäynnistyksessä; kantaan jos pitää säilyä.
_nakymat: dict[str, list[dict]] = {}
_NAKYMIA_MAX = 30


def _lisaa_nakyma(data: dict) -> bool:
    """Validoi ja lisää asiakkaan luoma näkymä (luottamusraja: selain).
    Jo olemassa oleva id = onnistunut uudelleenlähetys → True, ei tuplaa."""
    sivu, nid, nimi, suodatin = (data.get(k) for k in ("sivu", "id", "nimi", "suodatin"))
    if not all(isinstance(x, str) and 0 < len(x) <= 200 for x in (sivu, nid, nimi)):
        return False
    if not isinstance(suodatin, dict) or len(suodatin) > 10 or not all(
            isinstance(k, str) and (v is None or (isinstance(v, str) and len(v) <= 200))
            for k, v in suodatin.items()):
        return False
    lista = _nakymat.setdefault(sivu, [])
    if any(n["id"] == nid for n in lista):
        return True
    if len(lista) >= _NAKYMIA_MAX:
        return False
    lista.append({"id": nid, "nimi": nimi[:40], "suodatin": suodatin})
    return True


def _kelpo_lomakearvo(arvo) -> bool:
    """Lomakekentän arvo selaimelta (luottamusraja): teksti, None tai tekstilista.
    Teksti voi olla koko raporttiosio (raporttimuokkain on jaettu lomake)."""
    if arvo is None or (isinstance(arvo, str) and len(arvo) <= 200000):
        return True
    return isinstance(arvo, list) and len(arvo) <= 100 and all(
        isinstance(x, str) and len(x) <= 1000 for x in arvo)


def _kelpo_lomakearvot(arvot) -> bool:
    return isinstance(arvot, dict) and len(arvot) <= 30 and all(
        isinstance(k, str) and len(k) <= 50 and _kelpo_lomakearvo(v) for k, v in arvot.items())


async def _laheta(viesti: str, uidit=None) -> None:
    """Viesti annetuille (oletus: kaikille) yhteyksille. Katkennut yhteys poistetaan;
    sen oma ws-käsittelijä siivoaa lomakesessiot."""
    for uid in list(_yhteydet if uidit is None else uidit):
        yht = _yhteydet.get(uid)
        if yht is None:
            continue
        try:
            await yht[0].send_text(viesti)
        except Exception:
            _yhteydet.pop(uid, None)


def _kayttajatiedot(uid: str) -> dict:
    tiedot = _yhteydet.get(uid, (None, {}))[1]
    return {"nimimerkki": tiedot.get("nimimerkki", "?"), "profiili": tiedot.get("profiili", {})}


async def _laheta_lomake(avain: str, lahettaja: str | None = None, tyyppi: str = "lomake-sessio") -> None:
    """Lomakkeen koko tila jäsenille. lahettaja = kenen muutos tämän laukaisi
    (selain ei sovella omia muutoksiaan takaisin, ettei kirjoitus nyi)."""
    lomake = _lomakkeet.get(avain)
    if not lomake:
        return
    muokkaajat = [{"id": uid, **_kayttajatiedot(uid), **tila}
                  for uid, tila in lomake["jasenet"].items()]
    viesti = json.dumps({"tyyppi": tyyppi, "avain": avain, "lahettaja": lahettaja,
                         "arvot": lomake["arvot"], "muokkaajat": muokkaajat})
    await _laheta(viesti, [uid for uid in lomake["jasenet"]
                           if tyyppi == "lomake-sessio" or uid != lahettaja])


async def _poistu_lomakkeesta(avain: str, uid: str) -> None:
    lomake = _lomakkeet.get(avain)
    if lomake and lomake["jasenet"].pop(uid, None) is not None:
        if lomake["jasenet"]:
            await _laheta_lomake(avain)
        else:
            del _lomakkeet[avain]  # viimeinen poistui → seuraava avaaja alustaa uudelleen


# Läsnäolon koonti: tilapäivitykset (hiiren liike 80 ms välein/käyttäjä) kerätään
# yhteen lähetykseen enintään _KOONTI_S välein — muuten jokainen liike lähettäisi
# kaikkien tilan kaikille (O(käyttäjät²) viestiä jaetussa WiFissä).
_KOONTI_S = 0.1
_koonti: asyncio.Task | None = None


async def _laheta_kootusti() -> None:
    await asyncio.sleep(_KOONTI_S)
    kayttajat = [{"id": uid, **data} for uid, (_, data) in _yhteydet.items() if data]
    await _laheta(json.dumps({"tyyppi": "kayttajat", "data": kayttajat}))


async def _laheta_kaikille() -> None:
    """Ajastaa kootun läsnäololähetyksen (uusin tila lähtöhetkellä); ei odota sitä."""
    global _koonti
    if _koonti is None or _koonti.done():
        _koonti = asyncio.create_task(_laheta_kootusti())


@reititin.post("/api/nakymat")
async def api_nakyma_luo(data: dict) -> dict:
    """Uusi jaettu suodatinnäkymä (HTTP, jotta WebUI voi lähettää uudelleen ja näyttää tilan)."""
    if not _lisaa_nakyma(data):
        raise HTTPException(status_code=400, detail="Virheellinen näkymä")
    await _laheta(json.dumps({"tyyppi": "nakymat", "data": _nakymat}))
    return {"ok": True}


class RaporttiOsioPyynto(BaseModel):
    teksti: str


@reititin.post("/api/tutkimukset/{slug}/raportti/{avain}")
def api_raportti_osio_tallenna(tutkimus: TutkimusSlugista, avain: str, pyynto: RaporttiOsioPyynto) -> dict:
    """Raporttiosion tallennus (idempotentti: sama teksti uudelleen = sama tila)."""
    mallit.aseta_raportti_osio(tutkimus["TID"], avain, pyynto.teksti)
    return {"ok": True}


@reititin.websocket("/ws")
async def ws_kayttajat(ws: WebSocket) -> None:
    await ws.accept()
    uid = str(uuid.uuid4())[:8]
    _yhteydet[uid] = (ws, {})
    try:
        await ws.send_text(json.dumps({"tyyppi": "oma-id", "id": uid}))
        await ws.send_text(json.dumps({"tyyppi": "nakymat", "data": _nakymat}))
        while True:
            data = await ws.receive_json()
            tyyppi = data.get("tyyppi")
            if tyyppi == "uutinen":
                aika = datetime.now().strftime("%H:%M")
                await _laheta(json.dumps({"tyyppi": "uutinen", "teksti": data.get("teksti", ""), "aika": aika}))
            elif tyyppi and tyyppi.startswith("lomake-"):
                avain = data.get("avain")
                if not (isinstance(avain, str) and 0 < len(avain) <= 100):
                    continue
                lomake = _lomakkeet.get(avain)
                if tyyppi == "lomake-liity" and _kelpo_lomakearvot(data.get("arvot")):
                    if lomake is None:
                        lomake = _lomakkeet[avain] = {"arvot": data["arvot"], "jasenet": {}}
                    lomake["jasenet"][uid] = {"kentta": None, "kursori": 0}
                    await _laheta_lomake(avain)
                elif lomake is None or uid not in lomake["jasenet"]:
                    continue
                elif tyyppi == "lomake-arvo":
                    kentta = data.get("kentta")
                    if not (isinstance(kentta, str) and len(kentta) <= 50):
                        continue
                    if "arvo" in data:
                        if not _kelpo_lomakearvo(data["arvo"]) or (
                                kentta not in lomake["arvot"] and len(lomake["arvot"]) >= 30):
                            continue
                        lomake["arvot"][kentta] = data["arvo"]
                    kursori = data.get("kursori")
                    lomake["jasenet"][uid] = {"kentta": kentta,
                                              "kursori": kursori if isinstance(kursori, int) else 0}
                    await _laheta_lomake(avain, lahettaja=uid)
                elif tyyppi == "lomake-tallennettu":
                    await _laheta_lomake(avain, lahettaja=uid, tyyppi="lomake-tallennettu")
                elif tyyppi == "lomake-poistu":
                    await _poistu_lomakkeesta(avain, uid)
            else:
                _yhteydet[uid] = (ws, data)
                await _laheta_kaikille()
    except WebSocketDisconnect:
        _yhteydet.pop(uid, None)
        for avain in list(_lomakkeet):
            await _poistu_lomakkeesta(avain, uid)
        await _laheta_kaikille()
