"""Opserver web-käyttöliittymän FastAPI-palvelin."""
import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import uuid
from datetime import datetime
from typing import Annotated, Optional
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from tietokanta import mallit
from tietokanta.valimuisti import ttl_valimuisti
from llm import tiiviste, kehotteet
from raportti import llmraportti


_AUTH_EVASTE = "opserver_auth"


def _auth_token(kayttaja: str, salasana: str) -> str:
    """Auth-evästeen arvo: HMAC-SHA256 käyttäjästä salasana-avaimella. Väärentämätön
    ilman salasanaa; saadaan vain Basic-todennetun HTTP-vastauksen kautta."""
    return hmac.new(salasana.encode(), kayttaja.encode(), hashlib.sha256).hexdigest()


def _evasteesta(cookie_otsikko: str, nimi: str) -> str:
    for osa in cookie_otsikko.split(";"):
        avain, _, arvo = osa.strip().partition("=")
        if avain == nimi:
            return arvo
    return ""


class PerusAutentikointi:
    """HTTP Basic Auth -välikerros demojen suojaukseen (esim. Tailscale Funnel).

    Aktivoituu vain kun .env:ssä on sekä WEBUI_AUTH_KAYTTAJA että
    WEBUI_AUTH_SALASANA; tyhjänä = pois päältä (LAN-oletus muuttumaton). Suojaa
    sekä HTTP- että WebSocket-yhteydet. Tunnusvertailu on vakioaikainen
    (secrets.compare_digest). Turvallinen vain HTTPS:n yli (Funnel päättää TLS:n).

    Selain ei lähetä Authorization-otsikkoa WebSocket-kättelyssä, joten authatun
    HTTP-vastauksen yhteydessä asetetaan auth-eväste; selain lähettää sen WS-
    kättelyssä ja _kelpaa hyväksyy joko Basic-otsikon tai evästeen.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        kayttaja = os.environ.get("WEBUI_AUTH_KAYTTAJA", "")
        salasana = os.environ.get("WEBUI_AUTH_SALASANA", "")
        if not (kayttaja and salasana):
            await self.app(scope, receive, send)
            return
        if self._kelpaa(scope, kayttaja, salasana):
            if scope["type"] == "http":
                await self.app(scope, receive, self._evasteen_kanssa(send, kayttaja, salasana))
            else:
                await self.app(scope, receive, send)
            return
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
        else:
            await send({"type": "http.response.start", "status": 401, "headers": [
                (b"www-authenticate", b'Basic realm="Opserver"'),
                (b"content-type", b"text/plain; charset=utf-8"),
            ]})
            await send({"type": "http.response.body", "body": "Kirjautuminen vaaditaan.".encode()})

    @staticmethod
    def _evasteen_kanssa(send, kayttaja: str, salasana: str):
        """Kääre, joka lisää auth-evästeen HTTP-vastauksen alkuun."""
        evaste = (f"{_AUTH_EVASTE}={_auth_token(kayttaja, salasana)}"
                  "; Path=/; HttpOnly; SameSite=Strict").encode("latin-1")

        async def kaaritty(viesti):
            if viesti["type"] == "http.response.start":
                viesti = dict(viesti)
                viesti["headers"] = list(viesti.get("headers") or []) + [(b"set-cookie", evaste)]
            await send(viesti)

        return kaaritty

    @staticmethod
    def _kelpaa(scope, kayttaja: str, salasana: str) -> bool:
        otsikot = dict(scope.get("headers") or [])
        auth = otsikot.get(b"authorization", b"").decode("latin-1")
        if auth.startswith("Basic "):
            try:
                nimi, _, sala = base64.b64decode(auth[6:]).decode("utf-8").partition(":")
                if (secrets.compare_digest(nimi, kayttaja)
                        and secrets.compare_digest(sala, salasana)):
                    return True
            except (ValueError, UnicodeDecodeError):
                pass
        # WebSocket-kättely: selain lähettää evästeen muttei Authorization-otsikkoa.
        token = _evasteesta(otsikot.get(b"cookie", b"").decode("latin-1"), _AUTH_EVASTE)
        if token:
            return secrets.compare_digest(token, _auth_token(kayttaja, salasana))
        return False


sovellus = FastAPI(title="Opserver")
sovellus.add_middleware(PerusAutentikointi)
# Pakkaus: JSON/JS pienenee ~5–10× — ratkaisevaa huonolla yhteydellä (tuotanto ei pakkaa muualla).
sovellus.add_middleware(GZipMiddleware, minimum_size=1000)


def _tutkimus_slugista(slug: str) -> dict:
    """Polun {slug} → tutkimusrivi, tai 404."""
    tutkimus = mallit.hae_tutkimus_slugilla(slug)
    if tutkimus is None:
        raise HTTPException(status_code=404, detail="Tutkimusta ei löydy")
    return tutkimus


TutkimusSlugista = Annotated[dict, Depends(_tutkimus_slugista)]


def _vaadi_nimi(nimi: str) -> str:
    """Korjauksen/hyväksynnän tekijä on pakollinen (400, ei pydanticin 422)."""
    if not nimi.strip():
        raise HTTPException(status_code=400, detail="Nimi puuttuu")
    return nimi.strip()


def _tarkista_juurisyy(juurisyy: str | None) -> None:
    if juurisyy is not None and juurisyy not in mallit.JUURISYYT:
        raise HTTPException(status_code=400, detail="Tuntematon juurisyy")

# --- Reaaliaikainen läsnäolo ja muokkaussessiot (WebSocket) ---

_yhteydet: dict[str, tuple[WebSocket, dict]] = {}

# Jaetut korjauslomakkeet (HITL-modaalit): avain (esim. "hitl:1:7", "arvio:1:7:3") →
# {"arvot": {kentta: arvo}, "jasenet": {uid: {"kentta": str|None, "kursori": int}}}.
# Ensimmäisen avaajan arvot alustavat lomakkeen; myöhemmät liittyjät saavat ne.
_lomakkeet: dict[str, dict] = {}

# avain = (tid, avain_str) → {uid: {nimimerkki, profiili, kursori}}
_raportti_sessiot: dict[tuple, dict[str, dict]] = {}
# avain = (tid, avain_str) → nykyinen tekstisisältö sessiossa
_raportti_teksti: dict[tuple, str] = {}

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
    """Lomakekentän arvo selaimelta (luottamusraja): teksti, None tai tekstilista."""
    if arvo is None or (isinstance(arvo, str) and len(arvo) <= 20000):
        return True
    return isinstance(arvo, list) and len(arvo) <= 100 and all(
        isinstance(x, str) and len(x) <= 1000 for x in arvo)


def _kelpo_lomakearvot(arvot) -> bool:
    return isinstance(arvot, dict) and len(arvot) <= 30 and all(
        isinstance(k, str) and len(k) <= 50 and _kelpo_lomakearvo(v) for k, v in arvot.items())


async def _laheta(viesti: str, uidit=None) -> None:
    """Viesti annetuille (oletus: kaikille) yhteyksille. Katkennut yhteys poistetaan;
    sen oma ws-käsittelijä siivoaa lomake- ja raporttisessiot."""
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
    await _laheta(viesti, _raportti_sessiot[avain])


async def _poistu_raportista(avain: tuple, uid: str) -> None:
    sessio = _raportti_sessiot.get(avain)
    if sessio and sessio.pop(uid, None) is not None:
        if sessio:
            await _laheta_raportti_sessio(avain)
        else:
            del _raportti_sessiot[avain]
            _raportti_teksti.pop(avain, None)


async def _laheta_kaikille() -> None:
    kayttajat = [{"id": uid, **data} for uid, (_, data) in _yhteydet.items() if data]
    await _laheta(json.dumps({"tyyppi": "kayttajat", "data": kayttajat}))


@sovellus.post("/api/nakymat")
async def api_nakyma_luo(data: dict) -> dict:
    """Uusi jaettu suodatinnäkymä (HTTP, jotta WebUI voi lähettää uudelleen ja näyttää tilan)."""
    if not _lisaa_nakyma(data):
        raise HTTPException(status_code=400, detail="Virheellinen näkymä")
    await _laheta(json.dumps({"tyyppi": "nakymat", "data": _nakymat}))
    return {"ok": True}


class RaporttiOsioPyynto(BaseModel):
    teksti: str


@sovellus.post("/api/tutkimukset/{slug}/raportti/{avain}")
def api_raportti_osio_tallenna(tutkimus: TutkimusSlugista, avain: str, pyynto: RaporttiOsioPyynto) -> dict:
    """Raporttiosion tallennus (idempotentti: sama teksti uudelleen = sama tila)."""
    mallit.aseta_raportti_osio(tutkimus["TID"], avain, pyynto.teksti)
    if (tutkimus["TID"], avain) in _raportti_teksti:
        _raportti_teksti[(tutkimus["TID"], avain)] = pyynto.teksti
    return {"ok": True}


@sovellus.websocket("/ws")
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
            elif tyyppi == "raportti-liity":
                avain = (data.get("tid"), data.get("avain"))
                if avain not in _raportti_sessiot:
                    _raportti_sessiot[avain] = {}
                    _raportti_teksti[avain] = mallit.hae_raportti_osio(*avain)
                _raportti_sessiot[avain][uid] = {**_kayttajatiedot(uid), "kursori": 0}
                await _laheta_raportti_sessio(avain)
            elif tyyppi == "raportti-teksti":
                avain = (data.get("tid"), data.get("avain"))
                if avain in _raportti_sessiot:
                    _raportti_teksti[avain] = data.get("teksti", "")
                    if uid in _raportti_sessiot[avain]:
                        _raportti_sessiot[avain][uid]["kursori"] = data.get("kursori", 0)
                    await _laheta_raportti_sessio(avain)
            elif tyyppi == "raportti-poistu":
                await _poistu_raportista((data.get("tid"), data.get("avain")), uid)
            else:
                _yhteydet[uid] = (ws, data)
                await _laheta_kaikille()
    except WebSocketDisconnect:
        _yhteydet.pop(uid, None)
        for avain in list(_lomakkeet):
            await _poistu_lomakkeesta(avain, uid)
        for avain in list(_raportti_sessiot):
            await _poistu_raportista(avain, uid)
        await _laheta_kaikille()

STAATTINEN = os.path.join(os.path.dirname(__file__), "staattinen")
_INDEX = os.path.join(STAATTINEN, "index.html")
_NO_STORE = {"Cache-Control": "no-store"}

# Kentät jotka jätetään pois kurssilistasta (suuri JSON-kenttä)
_KURSSI_LISTA_KENTAT = {"OpsKuvaus"}


# --- Staattisten referenssikyselyjen TTL-välimuisti ---
# Vain demon aikana muuttumaton data (kurssikatalogi, korkeakoulut, lukuvuodet,
# tasot). EI annotointiriippuvaista dataa (luokitukset/arvioinnit) — ne pidetään
# tuoreina reaaliaikaista yhteisöllistä annotointia varten.
_VALIMUISTI_TTL = float(os.environ.get("WEBUI_VALIMUISTI_TTL", "60"))


@ttl_valimuisti(_VALIMUISTI_TTL)
def _korkeakoulut_valimuistissa() -> list[dict]:
    koulut = mallit.hae_korkeakoulut()
    maarat = mallit.hae_kurssimaarat_kouluittain()
    for k in koulut:
        k["KurssitKausittain"] = maarat.get(k["KKID"], [])
    return koulut


@ttl_valimuisti(_VALIMUISTI_TTL)
def _lukuvuodet_valimuistissa() -> list[str]:
    return mallit.hae_lukuvuodet()


@ttl_valimuisti(_VALIMUISTI_TTL)
def _tasot_valimuistissa(kkid, lukuvuosi) -> list[str]:
    return mallit.hae_tasot(kkid=kkid, lukuvuosi=lukuvuosi)


@ttl_valimuisti(_VALIMUISTI_TTL)
def _kurssit_valimuistissa(kkid, lukuvuosi) -> list[dict]:
    rivit = mallit.hae_kurssit(kkid=kkid, lukuvuosi=lukuvuosi)
    return [{k: v for k, v in r.items() if k not in _KURSSI_LISTA_KENTAT} for r in rivit]


# Raskas tuoreuslaskenta (raporttitiiviste) ajetaan taustalla — ei estä pollausta.
# Rajoitetaan uudelleenlaskenta korkeintaan yhteen per tutkimus kerrallaan JA
# harvennetaan aikavälillä, ettei jatkuva 15 s pollaus laukaise laskentaa alati.
_TUOREUS_PAIVITYS_VALI = float(os.environ.get("WEBUI_TUOREUS_VALI_S", "300"))
_tuoreus_lukko = threading.Lock()
_tuoreus_kaynnissa: set[int] = set()


def _kaynnista_taustatuoreus(tutkimus: dict) -> None:
    """Käynnistää raportin tuoreuslaskennan taustasäikeessä, jos tallennettu tuoreus
    puuttuu tai on vanhempi kuin _TUOREUS_PAIVITYS_VALI. Ei blokkaa pyyntöä; tulos
    näkyy seuraavalla pollauksella (tilanne näyttää 'tarkistettu'-aikaleiman)."""
    tid = tutkimus["TID"]
    tuoreus = mallit.hae_raportti_tuoreus(tid)
    tarkistettu = tuoreus.get("Tarkistettu") if tuoreus else None
    if tarkistettu and (datetime.now() - tarkistettu).total_seconds() < _TUOREUS_PAIVITYS_VALI:
        return
    with _tuoreus_lukko:
        if tid in _tuoreus_kaynnissa:
            return
        _tuoreus_kaynnissa.add(tid)

    def aja():
        try:
            llmraportti.paivita_tuoreus(tutkimus)
        except Exception:
            pass  # parhaan yrityksen mukaan; pollaus ei riipu taustapäivityksestä
        finally:
            with _tuoreus_lukko:
                _tuoreus_kaynnissa.discard(tid)

    threading.Thread(target=aja, daemon=True).start()


@ttl_valimuisti(_VALIMUISTI_TTL)
def _raportti_tilanne_valimuistissa(slug: str):
    """Raportin tuoreus (koosta_tilanne) — KEVYT: lukee viimeksi lasketun
    tuoreustuloksen tallennettuna (raskas tiivistelaskenta ajetaan taustalla).
    Välimuistitettu, koska WebUI:n raporttinäkymä päivittyy 15 s välein.
    Välimuistin ohittuessa (≤ TTL) laukaistaan taustatuoreuden päivitys (harvennettu
    _TUOREUS_PAIVITYS_VALI:llä). None jos tutkimusta ei ole."""
    tutkimus = mallit.hae_tutkimus_slugilla(slug)
    if tutkimus is None:
        return None
    tilanne = llmraportti.koosta_tilanne(tutkimus)
    if tilanne.get("generoitu"):
        _kaynnista_taustatuoreus(tutkimus)
    return tilanne


_VALIMUISTIT = [_korkeakoulut_valimuistissa, _lukuvuodet_valimuistissa,
                _tasot_valimuistissa, _kurssit_valimuistissa,
                _raportti_tilanne_valimuistissa]


def tyhjenna_valimuistit() -> None:
    """Nollaa kaikki staattiset välimuistit (esim. hakurobotin ajon jälkeen / testit)."""
    for f in _VALIMUISTIT:
        f.tyhjenna()


@sovellus.get("/api/korkeakoulut")
def api_korkeakoulut() -> list[dict]:
    return _korkeakoulut_valimuistissa()


@sovellus.get("/api/lukuvuodet")
def api_lukuvuodet() -> list[str]:
    return _lukuvuodet_valimuistissa()


@sovellus.get("/api/tasot")
def api_tasot(kkid: Optional[int] = None, lukuvuosi: Optional[str] = None) -> list[str]:
    return _tasot_valimuistissa(kkid, lukuvuosi)


@sovellus.get("/api/kurssit")
def api_kurssit(kkid: Optional[int] = None, lukuvuosi: Optional[str] = None,
                alku: int = 0, koko: Optional[int] = None) -> list[dict]:
    """koko annettu → vain rivit alku..alku+koko (WebUI lataa osissa; lyhyt osa = viimeinen)."""
    rivit = _kurssit_valimuistissa(kkid, lukuvuosi)
    return rivit if koko is None else rivit[alku:alku + koko]


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
def api_tutkimus_kurssit(tutkimus: TutkimusSlugista) -> list[dict]:
    rivit = mallit.hae_valitut_kurssit(tutkimus["TID"], kuvaukset=False)
    return [{k: v for k, v in r.items() if k not in _KURSSI_LISTA_KENTAT} for r in rivit]


@sovellus.get("/api/tutkimukset/{slug}/luokitukset/maarat")
def api_tutkimus_luokitukset_maarat(tutkimus: TutkimusSlugista, kkid: Optional[int] = None,
                                    taso: Optional[str] = None,
                                    hakusana: Optional[str] = None) -> dict:
    return mallit.hae_tutkimuksen_tilamaarat(tutkimus["TID"], kkid=kkid, taso=taso, hakusana=hakusana)


@sovellus.get("/api/tutkimukset/{slug}/luokitukset")
def api_tutkimus_luokitukset(tutkimus: TutkimusSlugista, tila: Optional[str] = None,
                             sivu: int = 0, koko: int = 200,
                             kkid: Optional[int] = None, taso: Optional[str] = None,
                             hakusana: Optional[str] = None,
                             jarjesta: Optional[str] = None,
                             suunta: Optional[str] = None) -> list[dict]:
    tid = tutkimus["TID"]
    rivit = mallit.hae_kurssit_luokituksilla(tid, tila=tila, sivu=sivu, koko=koko,
                                             kkid=kkid, taso=taso, hakusana=hakusana,
                                             jarjesta=jarjesta, suunta=suunta)

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
def api_tutkimus_arvioinnit(tutkimus: TutkimusSlugista, sivu: int = 0, koko: Optional[int] = None) -> dict:
    """koko annettu → vain sivun kurssit (WebUI lataa osissa) + yhteensa kaikista."""
    tid = tutkimus["TID"]
    kysymykset = mallit.hae_kysymykset(tid)
    if koko is None:
        kurssit = mallit.hae_valitut_kurssit(tid, kuvaukset=False)
        yhteensa = len(kurssit)
    else:
        kurssit = mallit.hae_valitut_kurssit(tid, raja=koko, siirto=sivu * koko, kuvaukset=False)
        yhteensa = mallit.laske_valitut_kurssit(tid)
    # ponytail: vastaukset haetaan koko tutkimukselle joka sivulla (~1600 lyhyttä riviä,
    # ms-luokkaa); rajaa KID-listalla jos vastausmäärä kasvaa kertaluokkia.
    vastaukset_lista = mallit.hae_vastaukset(tid)
    hitl_lista = mallit.hae_hitl_vastaukset(tid)

    # Nykyiset kysymystiivisteet: tunnistavat vastaukset jotka on generoitu
    # vanhentuneeseen kysymykseen/kehotteeseen (ennen seuraavaa LLM-ajoa).
    jarjestelma = kehotteet.lue("arviointijarjestelma.txt")
    nyky_tiiviste = tiiviste.kysymystiivisteet(
        tutkimus.get("Arviointikehote") or "", jarjestelma, kysymykset
    )

    vastaus_kartta: dict[int, dict[int, dict]] = {}
    for v in vastaukset_lista:
        if v.get("Malli") is None:
            continue  # ihmisen korjaus → korjaus_kartta
        kid = v["KID"]
        if kid not in vastaus_kartta:
            vastaus_kartta[kid] = {}
        on_vastaus = (bool((v.get("Vastaus") or "").strip()) or v.get("Luokka") is not None
                      or v.get("Pisteet") is not None or v.get("Lista") is not None)
        vastaus_kartta[kid][v["KysID"]] = {
            "vastaus": v.get("Vastaus") or "",
            "luokka": v.get("Luokka"),
            "pisteet": v.get("Pisteet"),
            "lista": v.get("Lista"),
            "vanhentunut": on_vastaus and v.get("Kehotetiiviste") != nyky_tiiviste.get(v["KysID"]),
            "hyvaksyja": v.get("HyvaksyjaNimi"),  # ei sähköpostia: WebUI on julkinen
        }

    # Ihmisen korjaukset omaan karttaansa: WebUI näyttää korjatun arvon ja kertoo
    # kuka sen teki, mutta tekoälyn alkuperäinen vastaus jää näkyviin vertailuun.
    # hae_hitl_vastaukset palauttaa uusimman ensin → ensimmäinen osuma voittaa.
    korjaus_kartta: dict[int, dict[int, dict]] = {}
    for h in hitl_lista:
        per_kysymys = korjaus_kartta.setdefault(h["KID"], {})
        if h["KysID"] in per_kysymys:
            continue
        per_kysymys[h["KysID"]] = {
            "vastaus": h.get("Vastaus") or "",
            "luokka": h.get("Luokka"),
            "pisteet": h.get("Pisteet"),
            "lista": h.get("Lista"),
            "nimi": h.get("KayttajaNimi") or "",
            "juurisyy": h.get("Juurisyy"),
            "aikaleima": str(h.get("Aikaleima") or ""),
        }

    kys_idt = [k["KysID"] for k in kysymykset]
    tyhjä_vastaus = {"vastaus": "", "luokka": None, "pisteet": None, "lista": None,
                     "vanhentunut": False, "hyvaksyja": None}
    return {
        "yhteensa": yhteensa,
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
                "korjaukset": {kys_id: korjaus_kartta.get(k["KID"], {}).get(kys_id)
                               for kys_id in kys_idt},
            }
            for k in kurssit
        ],
    }


class HitlPyynto(BaseModel):
    uusi_tila: bool
    perustelu: str
    nimi: str
    sahkoposti: str
    juurisyy: str | None = None


@sovellus.post("/api/tutkimukset/{slug}/kurssit/{kid}/hitl")
def api_hitl_korjaus(tutkimus: TutkimusSlugista, kid: int, pyynto: HitlPyynto) -> dict:
    _tarkista_juurisyy(pyynto.juurisyy)
    mallit.tallenna_hitl_korjaus(
        tutkimus["TID"], kid, pyynto.uusi_tila,
        pyynto.perustelu, pyynto.nimi, pyynto.sahkoposti, pyynto.juurisyy,
    )
    return {"ok": True}


class HyvaksyntaPyynto(BaseModel):
    nimi: str
    sahkoposti: str = ""


@sovellus.post("/api/tutkimukset/{slug}/kurssit/{kid}/hyvaksy")
def api_hyvaksy_luokitus(tutkimus: TutkimusSlugista, kid: int, pyynto: HyvaksyntaPyynto) -> dict:
    """Peukutus: LLM:n mukaan ottama kurssi merkitään ihmisen hyväksymäksi."""
    mallit.hyvaksy_luokitus(tutkimus["TID"], kid, _vaadi_nimi(pyynto.nimi), pyynto.sahkoposti.strip())
    return {"ok": True}


@sovellus.post("/api/tutkimukset/{slug}/kurssit/{kid}/kysymykset/{kysid}/hyvaksy")
def api_hyvaksy_vastaus(tutkimus: TutkimusSlugista, kid: int, kysid: int, pyynto: HyvaksyntaPyynto) -> dict:
    """Peukutus: LLM:n arviointivastaus merkitään ihmisen hyväksymäksi."""
    mallit.hyvaksy_vastaus(tutkimus["TID"], kid, kysid, _vaadi_nimi(pyynto.nimi),
                           pyynto.sahkoposti.strip())
    return {"ok": True}


class ArvioKorjausPyynto(BaseModel):
    """Ihmisen korjaus yhteen arviointivastaukseen.

    Kysymystyyppi ratkaisee mitkä kentät ovat merkityksellisiä: luokittelu → luokka,
    asteikko → pisteet, lista → lista, vapaa teksti → pelkkä vastaus. Muut jäävät
    Noneksi, kuten LLM:n vastauksissakin.
    """
    vastaus: str = ""
    luokka: str | None = None
    pisteet: float | None = None
    lista: list[str] | None = None
    nimi: str
    sahkoposti: str
    juurisyy: str | None = None


@sovellus.post("/api/tutkimukset/{slug}/kurssit/{kid}/kysymykset/{kysid}/korjaus")
def api_arvio_korjaus(tutkimus: TutkimusSlugista, kid: int, kysid: int, pyynto: ArvioKorjausPyynto) -> dict:
    _tarkista_juurisyy(pyynto.juurisyy)
    nimi = _vaadi_nimi(pyynto.nimi)
    tid = tutkimus["TID"]
    kysymykset = {k["KysID"]: k for k in mallit.hae_kysymykset(tid)}
    kysymys = kysymykset.get(kysid)
    if kysymys is None:
        raise HTTPException(status_code=404, detail="Kysymystä ei löydy tästä tutkimuksesta")
    # Tyyppitarkistus: luokka on oltava kysymyksen määrittelemien joukossa, pisteet
    # asteikon sisällä. Väärä arvo rikkoisi raporttitilastot hiljaa.
    maarittely = kysymys.get("LuokitteluMaarittely") or {}  # hae_kysymykset jäsentää JSONin
    tyyppi = kysymys.get("Luokittelu") or "vapaa_teksti"
    if tyyppi == "luokittelu" and pyynto.luokka:
        sallitut = [l.get("nimi") for l in maarittely.get("luokat", [])]
        if sallitut and pyynto.luokka not in sallitut:
            raise HTTPException(status_code=400, detail=f"Tuntematon luokka: {pyynto.luokka}")
    if tyyppi == "asteikko" and pyynto.pisteet is not None:
        minimi, maksimi = maarittely.get("minimi", 1), maarittely.get("maksimi", 5)
        if not (minimi <= pyynto.pisteet <= maksimi):
            raise HTTPException(status_code=400, detail=f"Pisteet {minimi}–{maksimi} ulkopuolella")
    mallit.tallenna_hitl_vastaus(
        tid, kid, kysid, pyynto.vastaus, nimi, pyynto.sahkoposti.strip(),
        pisteet=pyynto.pisteet, luokka=pyynto.luokka, lista=pyynto.lista,
        juurisyy=pyynto.juurisyy,
    )
    return {"ok": True}


@sovellus.get("/api/tutkimukset/{slug}/raportti")
def api_raportti(tutkimus: TutkimusSlugista) -> dict:
    osiot = mallit.hae_raportti_osiot(tutkimus["TID"])
    return {"tid": tutkimus["TID"], "osiot": osiot}


@sovellus.get("/api/tutkimukset/{slug}/raportti/tilastot")
def api_raportti_tilastot(tutkimus: TutkimusSlugista) -> dict:
    """Palauttaa per-kysymys-tilastot rakenteellisille arvioinneille ilman LLM-kutsua."""
    tid = tutkimus["TID"]
    kysymykset = mallit.hae_kysymykset(tid)
    vastaukset_lista = mallit.hae_vastaukset(tid)

    # Rakenna per-kysymys indeksi vastauksista. hae_vastaukset palauttaa saman
    # (kurssi, kysymys) -parin HITL-rivin ennen LLM-riviä → ensimmäinen voittaa,
    # eikä ihmisen korjaama pari tule tilastoon kahdesti.
    v_per_kys: dict[int, list[dict]] = {k["KysID"]: [] for k in kysymykset}
    nahdyt: set[tuple[int, int]] = set()
    for v in vastaukset_lista:
        kysid = v["KysID"]
        if kysid in v_per_kys and (v["KID"], kysid) not in nahdyt:
            nahdyt.add((v["KID"], kysid))
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

        elif luokittelu == "lista":
            jakauma_lista: dict[str, int] = {}
            vastattuja = 0
            for v in vastaukset:
                kohdat = v.get("Lista") or []
                if kohdat:
                    vastattuja += 1
                for kohde in kohdat:
                    jakauma_lista[kohde] = jakauma_lista.get(kohde, 0) + 1
            kohta["jakauma"] = dict(sorted(jakauma_lista.items(), key=lambda p: -p[1]))
            kohta["yhteensa"] = vastattuja

        else:  # vapaa_teksti
            kohta["yhteensa"] = sum(1 for v in vastaukset if v.get("Vastaus"))

        tulos_kysymykset.append(kohta)

    # HITL-laatumittarit (CLAUDE.md vaihe 4): käsin-muutos-% + juurisyyjakauma.
    # Rakenteellinen, auktoritatiivinen luku — ei LLM-generoitua proosaa.
    tilastot = mallit.hae_tilastot_yliopistoittain(tid)
    hitl = llmraportti.hitl_mittarit(tilastot)

    return {"kysymykset": tulos_kysymykset, "hitl": hitl}


@sovellus.get("/api/tutkimukset/{slug}/raportti/tilanne")
def api_raportti_tilanne(slug: str) -> dict:
    """Raportin tuoreus: milloin generoitu, ajan tasalla / vanhentunut ja
    montako HITL-korjausta/kommenttia tehty generoinnin jälkeen."""
    tilanne = _raportti_tilanne_valimuistissa(slug)
    if tilanne is None:
        raise HTTPException(status_code=404, detail="Tutkimusta ei löydy")
    return tilanne


@sovellus.get("/api/tutkimukset/{slug}")
def api_tutkimus(tutkimus: TutkimusSlugista) -> dict:
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
