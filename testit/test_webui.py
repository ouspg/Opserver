from unittest.mock import patch
from fastapi.testclient import TestClient
from webui.palvelin import sovellus

asiakas = TestClient(sovellus)


def test_api_korkeakoulut_palauttaa_listan():
    rivit = [{"KKID": 1, "KouluNimi": "Tampereen yliopisto", "OpsOsoite": "https://esim.fi", "OpsTyyppi": "Peppi"}]
    with patch("webui.palvelin.mallit.hae_korkeakoulut", return_value=rivit):
        vastaus = asiakas.get("/api/korkeakoulut")
    assert vastaus.status_code == 200
    data = vastaus.json()
    assert len(data) == 1
    assert data[0]["KouluNimi"] == "Tampereen yliopisto"


def test_juuri_palauttaa_html():
    vastaus = asiakas.get("/")
    assert vastaus.status_code == 200
    assert "text/html" in vastaus.headers["content-type"]
