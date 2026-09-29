"""WebUI-testit: luokitukset ja HITL-A (webui/reitit_luokitukset.py)."""
from unittest.mock import patch
from testit.webui_apu import _auth_pois  # noqa: F401 — autouse-fixture
from testit.webui_apu import asiakas, TUTKIMUS


def test_api_luokitukset_valittaa_jarjestyksen():
    """▲▼-napit lähettävät jarjesta+suunta, jotka välitetään malleille."""
    with patch("tietokanta.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("tietokanta.mallit.hae_kurssit_luokituksilla", return_value=[]) as mock, \
         patch("tietokanta.mallit.hae_hitl_historia", return_value=[]):
        vastaus = asiakas.get(
            "/api/tutkimukset/kyber-2025/luokitukset?tila=mukana&jarjesta=op&suunta=laskeva")
    assert vastaus.status_code == 200
    assert mock.call_args.kwargs["jarjesta"] == "op"
    assert mock.call_args.kwargs["suunta"] == "laskeva"


def test_api_hitl_korjaus_tallentaa():
    with patch("tietokanta.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("tietokanta.mallit.tallenna_hitl_korjaus") as mock_tallenna:
        vastaus = asiakas.post(
            "/api/tutkimukset/kyber-2025/kurssit/7/hitl",
            json={"uusi_tila": False, "perustelu": "Epärelevant", "nimi": "Matti",
                  "sahkoposti": "m@esim.fi", "juurisyy": "llm_virhe"},
        )
    assert vastaus.status_code == 200
    assert vastaus.json()["ok"] is True
    mock_tallenna.assert_called_once_with(1, 7, False, "Epärelevant", "Matti",
                                          "m@esim.fi", "llm_virhe")


def test_api_hitl_korjaus_juurisyy_valinnainen():
    """Juurisyy voi puuttua (None) — vanha rajapinta ja kanta sallivat sen."""
    with patch("tietokanta.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("tietokanta.mallit.tallenna_hitl_korjaus") as mock_tallenna:
        vastaus = asiakas.post(
            "/api/tutkimukset/kyber-2025/kurssit/7/hitl",
            json={"uusi_tila": False, "perustelu": "x", "nimi": "M", "sahkoposti": "m@esim.fi"},
        )
    assert vastaus.status_code == 200
    mock_tallenna.assert_called_once_with(1, 7, False, "x", "M", "m@esim.fi", None)


def test_api_hitl_korjaus_hylkaa_tuntemattoman_juurisyyn():
    with patch("tietokanta.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("tietokanta.mallit.tallenna_hitl_korjaus") as mock_tallenna:
        vastaus = asiakas.post(
            "/api/tutkimukset/kyber-2025/kurssit/7/hitl",
            json={"uusi_tila": False, "perustelu": "x", "nimi": "M",
                  "sahkoposti": "m@esim.fi", "juurisyy": "keksitty"},
        )
    assert vastaus.status_code == 400
    mock_tallenna.assert_not_called()


def test_api_hyvaksy_luokitus():
    with patch("tietokanta.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("tietokanta.mallit.hyvaksy_luokitus") as mock_hyv:
        vastaus = asiakas.post("/api/tutkimukset/kyber-2025/kurssit/7/hyvaksy",
                               json={"nimi": " Matti ", "sahkoposti": "m@esim.fi"})
    assert vastaus.status_code == 200
    mock_hyv.assert_called_once_with(1, 7, "Matti", "m@esim.fi")


def test_api_hyvaksy_luokitus_vaatii_nimen():
    with patch("tietokanta.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("tietokanta.mallit.hyvaksy_luokitus") as mock_hyv:
        vastaus = asiakas.post("/api/tutkimukset/kyber-2025/kurssit/7/hyvaksy",
                               json={"nimi": "  "})
    assert vastaus.status_code == 400
    mock_hyv.assert_not_called()


def test_api_hitl_korjaus_404_kun_tutkimusta_ei_loydy():
    with patch("tietokanta.mallit.hae_tutkimus_slugilla", return_value=None):
        vastaus = asiakas.post(
            "/api/tutkimukset/ei-ole/kurssit/7/hitl",
            json={"uusi_tila": False, "perustelu": "Perustelu", "nimi": "Matti", "sahkoposti": "m@esim.fi"},
        )
    assert vastaus.status_code == 404
