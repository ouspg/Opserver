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


# --- Kurssin paikannus (autocomplete + siirtyminen oikealle sivulle) ---

def test_api_paikanna_valittaa_nakyman_ja_haun():
    # Paikannus etsii samasta näkymästä kuin listaus: tila, suodattimet ja järjestys.
    osumat = [{"KID": 7, "KurssiNimi": "Kyber", "Koodi": "K1", "KKID": 1, "Indeksi": 230}]
    with patch("tietokanta.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("tietokanta.mallit.paikanna_kurssit", return_value=osumat) as mock:
        data = asiakas.get("/api/tutkimukset/kyber-2025/luokitukset/paikanna?haku=kyb&tila=hylätty"
                           "&kkid=3&taso=aine&hakusana=x&jarjesta=op&suunta=laskeva").json()
        tyhja = asiakas.get("/api/tutkimukset/kyber-2025/luokitukset/paikanna?haku=%20&tila=mukana").json()
    assert data == osumat and tyhja == []
    mock.assert_called_once_with(1, "kyb", tila="hylätty", kkid=3, taso="aine", hakusana="x",
                                 jarjesta="op", suunta="laskeva")


def test_paikannus_laskee_sijainnin_listauksen_jarjestyksella():
    # Indeksi = paikka listauksen järjestyksessä (sivu = Indeksi // koko), joten ROW_NUMBER():n
    # järjestyksen on oltava sama kuin listauksen ORDER BY — ja KID ratkaisee tasatilanteet,
    # muuten samannimiset kurssit voisivat vaihtaa sivua kyselystä toiseen.
    import re
    from tietokanta import luokitukset
    sql = []
    with patch("tietokanta.luokitukset._hae_kaikki", side_effect=lambda q, p: sql.append((q, p)) or []), \
         patch("tietokanta.luokitukset._tutkimus_kurssi_scope", return_value=("1=1", [])):
        luokitukset.hae_kurssit_luokituksilla(1, tila="hylätty", sivu=2, koko=100, jarjesta="op", suunta="laskeva")
        luokitukset.paikanna_kurssit(1, "50%_x", tila="hylätty", jarjesta="op", suunta="laskeva")
    listaus = re.search(r"ORDER BY (.+?) LIMIT", sql[0][0]).group(1)
    ikkuna = re.search(r"ROW_NUMBER\(\) OVER \(ORDER BY (.+?)\)", sql[1][0]).group(1)
    assert listaus == ikkuna and listaus.endswith("k.KID")
    assert r"%50\%\_x%" in sql[1][1]  # LIKE-erikoismerkit kirjaimellisina
