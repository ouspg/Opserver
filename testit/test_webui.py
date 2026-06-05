from unittest.mock import patch
from fastapi.testclient import TestClient
from webui.palvelin import sovellus

asiakas = TestClient(sovellus)

KURSSI = {
    "KID": 1, "KKID": 1, "LahdeId": "45690", "Koodi": "IC00AU61",
    "KurssiNimi": "Kyberturvallisuuden perusteet", "Taso": "aine",
    "Oppiaine": "Tietotekniikka", "Opintopisteet": 5.0,
    "Opetusvuosi": "2025-2026", "OpsKuvaus": '{"id":"45690"}',
}


def test_api_korkeakoulut_palauttaa_listan():
    rivit = [{"KKID": 1, "KouluNimi": "Tampereen yliopisto", "OpsOsoite": "https://esim.fi", "OpsTyyppi": "Peppi"}]
    with patch("webui.palvelin.mallit.hae_korkeakoulut", return_value=rivit):
        vastaus = asiakas.get("/api/korkeakoulut")
    assert vastaus.status_code == 200
    assert vastaus.json()[0]["KouluNimi"] == "Tampereen yliopisto"


def test_api_kurssit_palauttaa_listan():
    with patch("webui.palvelin.mallit.hae_kurssit", return_value=[KURSSI]):
        vastaus = asiakas.get("/api/kurssit")
    assert vastaus.status_code == 200
    data = vastaus.json()
    assert len(data) == 1
    assert data[0]["KurssiNimi"] == "Kyberturvallisuuden perusteet"
    assert "OpsKuvaus" not in data[0]  # suuri kenttä jätetään pois listanäkymästä


def test_api_kurssit_suodattaa_kkid_perusteella():
    with patch("webui.palvelin.mallit.hae_kurssit", return_value=[]) as mock:
        asiakas.get("/api/kurssit?kkid=2")
    mock.assert_called_once_with(kkid=2)


def test_api_kurssi_palauttaa_ops_kuvauksen():
    with patch("webui.palvelin.mallit.hae_kurssi", return_value=KURSSI):
        vastaus = asiakas.get("/api/kurssit/1")
    assert vastaus.status_code == 200
    assert vastaus.json()["OpsKuvaus"] is not None


def test_api_kurssi_404_kun_ei_loydy():
    with patch("webui.palvelin.mallit.hae_kurssi", return_value=None):
        vastaus = asiakas.get("/api/kurssit/999")
    assert vastaus.status_code == 404


def test_juuri_palauttaa_html():
    vastaus = asiakas.get("/")
    assert vastaus.status_code == 200
    assert "text/html" in vastaus.headers["content-type"]
