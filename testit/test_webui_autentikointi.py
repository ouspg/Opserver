"""WebUI-testit: Basic Auth ja auth-eväste, myös WebSocket (webui/autentikointi.py)."""
from unittest.mock import patch
import pytest
from webui import autentikointi
from testit.webui_apu import _auth_pois  # noqa: F401 — autouse-fixture
from testit.webui_apu import asiakas


# --- HTTP Basic Auth -välikerros (demosuojaus) ---

def _aseta_auth(monkeypatch):
    monkeypatch.setenv("WEBUI_AUTH_KAYTTAJA", "demo")
    monkeypatch.setenv("WEBUI_AUTH_SALASANA", "salainen")


def test_auth_estaa_pyynnon_ilman_tunnuksia(monkeypatch):
    _aseta_auth(monkeypatch)
    vastaus = asiakas.get("/api/tutkimukset")
    assert vastaus.status_code == 401
    assert "www-authenticate" in {k.lower() for k in vastaus.headers}


def test_auth_hylkaa_vaarat_tunnukset(monkeypatch):
    _aseta_auth(monkeypatch)
    vastaus = asiakas.get("/api/tutkimukset", auth=("demo", "vaara"))
    assert vastaus.status_code == 401


def test_auth_paastaa_oikeilla_tunnuksilla(monkeypatch):
    _aseta_auth(monkeypatch)
    with patch("tietokanta.mallit.hae_tutkimukset_yhteenvedolla", return_value=[]):
        vastaus = asiakas.get("/api/tutkimukset", auth=("demo", "salainen"))
    assert vastaus.status_code == 200


def test_auth_pois_paalta_kun_env_tyhja():
    # Ilman WEBUI_AUTH-muuttujia (autouse-fixture poistanut) → ei vaadita tunnuksia
    with patch("tietokanta.mallit.hae_tutkimukset_yhteenvedolla", return_value=[]):
        vastaus = asiakas.get("/api/tutkimukset")
    assert vastaus.status_code == 200


# --- WebSocket-todennus Basic Authin alla (eväste, koska selain ei lähetä
#     Authorization-otsikkoa WS-kättelyssä) ---

def test_auth_asettaa_evasteen_oikeilla_tunnuksilla(monkeypatch):
    _aseta_auth(monkeypatch)
    with patch("tietokanta.mallit.hae_tutkimukset_yhteenvedolla", return_value=[]):
        vastaus = asiakas.get("/api/tutkimukset", auth=("demo", "salainen"))
    assert vastaus.status_code == 200
    assert vastaus.cookies.get("opserver_auth") == autentikointi._auth_token("demo", "salainen")


def test_ws_kelpaa_auth_evasteella(monkeypatch):
    _aseta_auth(monkeypatch)
    token = autentikointi._auth_token("demo", "salainen")
    with asiakas.websocket_connect("/ws", headers={"cookie": f"opserver_auth={token}"}) as ws:
        viesti = ws.receive_json()
    assert viesti["tyyppi"] == "oma-id"


def test_ws_hylataan_ilman_auth_evastetta(monkeypatch):
    _aseta_auth(monkeypatch)
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with asiakas.websocket_connect("/ws") as ws:
            ws.receive_json()


def test_ws_toimii_ilman_authia():
    # Ilman WEBUI_AUTH-muuttujia WS toimii normaalisti (LAN-oletus)
    with asiakas.websocket_connect("/ws") as ws:
        viesti = ws.receive_json()
    assert viesti["tyyppi"] == "oma-id"
