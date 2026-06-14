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


def test_spa_reitti_palauttaa_html():
    vastaus = asiakas.get("/tutkimukset/kyber-2025")
    assert vastaus.status_code == 200
    assert "text/html" in vastaus.headers["content-type"]


TUTKIMUS = {
    "TID": 1, "LuokittelunNimi": "Kyber 2025", "Slug": "kyber-2025",
    "Luokittelukehote": "valintakehote", "Tasorajaus": "aine",
    "Oppiainerajaus": None, "Arviointikehote": "arviointikehote",
}


def test_api_tutkimukset_palauttaa_listan():
    with patch("webui.palvelin.mallit.hae_tutkimukset_yhteenvedolla", return_value=[{**TUTKIMUS, "MukanaLkm": 0}]):
        vastaus = asiakas.get("/api/tutkimukset")
    assert vastaus.status_code == 200
    assert vastaus.json()[0]["Slug"] == "kyber-2025"


def test_api_tutkimus_slugilla_palauttaa_yhden():
    with patch("webui.palvelin.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS):
        vastaus = asiakas.get("/api/tutkimukset/kyber-2025")
    assert vastaus.status_code == 200
    assert vastaus.json()["LuokittelunNimi"] == "Kyber 2025"


def test_api_tutkimus_404_kun_ei_loydy():
    with patch("webui.palvelin.mallit.hae_tutkimus_slugilla", return_value=None):
        vastaus = asiakas.get("/api/tutkimukset/ei-ole")
    assert vastaus.status_code == 404


KURSSI_MUKANA = {
    "KID": 1, "KKID": 1, "LahdeId": "45690", "Koodi": "IC00AU61",
    "KurssiNimi": "Kyberturvallisuuden perusteet", "Taso": "aine",
    "Oppiaine": "Tietotekniikka", "Opintopisteet": "5",
    "Opetusvuosi": "2025-2026", "OpsKuvaus": None,
}

KYSYMYS = {"KysID": 10, "TID": 1, "Kysymys": "Liittyykö kurssi kyberturvallisuuteen?"}


def test_api_tutkimus_arvioinnit_palauttaa_rakenteen():
    vastaus_rivi = {"VasID": 1, "KysID": 10, "KID": 1, "Vastaus": "Kyllä"}
    with patch("webui.palvelin.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("webui.palvelin.mallit.hae_kysymykset", return_value=[KYSYMYS]), \
         patch("webui.palvelin.mallit.hae_valitut_kurssit", return_value=[KURSSI_MUKANA]), \
         patch("webui.palvelin.mallit.hae_vastaukset", return_value=[vastaus_rivi]):
        vastaus = asiakas.get("/api/tutkimukset/kyber-2025/arvioinnit")
    assert vastaus.status_code == 200
    data = vastaus.json()
    assert "kysymykset" in data
    assert "kurssit" in data
    assert data["kysymykset"][0]["Kysymys"] == KYSYMYS["Kysymys"]
    assert data["kurssit"][0]["vastaukset"] == ["Kyllä"]
    assert "OpsKuvaus" not in data["kurssit"][0]


def test_api_tutkimus_arvioinnit_tyhjat_vastaukset():
    with patch("webui.palvelin.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("webui.palvelin.mallit.hae_kysymykset", return_value=[KYSYMYS]), \
         patch("webui.palvelin.mallit.hae_valitut_kurssit", return_value=[KURSSI_MUKANA]), \
         patch("webui.palvelin.mallit.hae_vastaukset", return_value=[]):
        vastaus = asiakas.get("/api/tutkimukset/kyber-2025/arvioinnit")
    assert vastaus.status_code == 200
    data = vastaus.json()
    assert data["kurssit"][0]["vastaukset"] == [""]


def test_api_hitl_korjaus_tallentaa():
    with patch("webui.palvelin.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("webui.palvelin.mallit.tallenna_hitl_korjaus") as mock_tallenna:
        vastaus = asiakas.post(
            "/api/tutkimukset/kyber-2025/kurssit/7/hitl",
            json={"uusi_tila": False, "perustelu": "Epärelevant", "nimi": "Matti", "sahkoposti": "m@esim.fi"},
        )
    assert vastaus.status_code == 200
    assert vastaus.json()["ok"] is True
    mock_tallenna.assert_called_once_with(1, 7, False, "Epärelevant", "Matti", "m@esim.fi")


def test_api_hitl_korjaus_404_kun_tutkimusta_ei_loydy():
    with patch("webui.palvelin.mallit.hae_tutkimus_slugilla", return_value=None):
        vastaus = asiakas.post(
            "/api/tutkimukset/ei-ole/kurssit/7/hitl",
            json={"uusi_tila": False, "perustelu": "Perustelu", "nimi": "Matti", "sahkoposti": "m@esim.fi"},
        )
    assert vastaus.status_code == 404


def test_api_tutkimus_arvioinnit_404_kun_ei_loydy():
    with patch("webui.palvelin.mallit.hae_tutkimus_slugilla", return_value=None):
        vastaus = asiakas.get("/api/tutkimukset/ei-ole/arvioinnit")
    assert vastaus.status_code == 404
