"""WebUI-testit: arvioinnit ja HITL-B (webui/reitit_arvioinnit.py)."""
from unittest.mock import patch
from testit.webui_apu import _auth_pois  # noqa: F401 — autouse-fixture
from testit.webui_apu import asiakas, TUTKIMUS, KURSSI_MUKANA, KYSYMYS, KYSYMYS_LUOKITTELU, KYSYMYS_ASTEIKKO


def test_api_tutkimus_arvioinnit_palauttaa_rakenteen():
    vastaus_rivi = {"VasID": 1, "KysID": 10, "KID": 1, "Vastaus": "Kyllä", "Pisteet": None,
                    "Luokka": None, "Malli": "testimalli"}
    with patch("tietokanta.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("tietokanta.mallit.hae_kysymykset", return_value=[KYSYMYS]), \
         patch("tietokanta.mallit.hae_valitut_kurssit", return_value=[KURSSI_MUKANA]), \
         patch("tietokanta.mallit.hae_vastaukset", return_value=[vastaus_rivi]):
        vastaus = asiakas.get("/api/tutkimukset/kyber-2025/arvioinnit")
    assert vastaus.status_code == 200
    data = vastaus.json()
    assert "kysymykset" in data
    assert "kurssit" in data
    assert data["kysymykset"][0]["Kysymys"] == KYSYMYS["Kysymys"]
    assert data["kysymykset"][0]["Luokittelu"] == "vapaa_teksti"
    v = data["kurssit"][0]["vastaukset"][0]
    assert v["vastaus"] == "Kyllä"
    assert v["luokka"] is None
    assert v["pisteet"] is None
    assert "OpsKuvaus" not in data["kurssit"][0]
    assert v["hyvaksyja"] is None


def test_api_tutkimus_arvioinnit_palauttaa_hyvaksyjan_ilman_sahkopostia():
    vastaus_rivi = {"VasID": 1, "KysID": 10, "KID": 1, "Vastaus": "Kyllä", "Malli": "m",
                    "HyvaksyjaNimi": "Liisa", "HyvaksyjaSahkoposti": "l@e.fi"}
    with patch("tietokanta.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("tietokanta.mallit.hae_kysymykset", return_value=[KYSYMYS]), \
         patch("tietokanta.mallit.hae_valitut_kurssit", return_value=[KURSSI_MUKANA]), \
         patch("tietokanta.mallit.hae_vastaukset", return_value=[vastaus_rivi]):
        data = asiakas.get("/api/tutkimukset/kyber-2025/arvioinnit").json()
    assert data["kurssit"][0]["vastaukset"][0]["hyvaksyja"] == "Liisa"
    assert "l@e.fi" not in str(data)


def test_api_tutkimus_arvioinnit_lista_vastaus():
    kysymys_lista = {**KYSYMYS, "KysID": 20, "Luokittelu": "lista", "LuokitteluMaarittely": {"max_kohdat": 5}}
    vastaus_rivi = {"VasID": 2, "KysID": 20, "KID": 1, "Vastaus": "Opetussuunnitelman mukaan",
                    "Pisteet": None, "Luokka": None, "Lista": ["Matematiikka", "Ohjelmointi"],
                    "Malli": "testimalli"}
    with patch("tietokanta.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("tietokanta.mallit.hae_kysymykset", return_value=[kysymys_lista]), \
         patch("tietokanta.mallit.hae_valitut_kurssit", return_value=[KURSSI_MUKANA]), \
         patch("tietokanta.mallit.hae_vastaukset", return_value=[vastaus_rivi]):
        vastaus = asiakas.get("/api/tutkimukset/kyber-2025/arvioinnit")
    assert vastaus.status_code == 200
    data = vastaus.json()
    assert data["kysymykset"][0]["Luokittelu"] == "lista"
    v = data["kurssit"][0]["vastaukset"][0]
    assert v["lista"] == ["Matematiikka", "Ohjelmointi"]
    assert v["vastaus"] == "Opetussuunnitelman mukaan"


def test_api_tutkimus_arvioinnit_tyhjat_vastaukset():
    with patch("tietokanta.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("tietokanta.mallit.hae_kysymykset", return_value=[KYSYMYS]), \
         patch("tietokanta.mallit.hae_valitut_kurssit", return_value=[KURSSI_MUKANA]), \
         patch("tietokanta.mallit.hae_vastaukset", return_value=[]):
        vastaus = asiakas.get("/api/tutkimukset/kyber-2025/arvioinnit")
    assert vastaus.status_code == 200
    data = vastaus.json()
    v = data["kurssit"][0]["vastaukset"][0]
    assert v["vastaus"] == ""
    assert v["luokka"] is None
    assert v["pisteet"] is None


def test_api_hyvaksy_vastaus():
    with patch("tietokanta.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("tietokanta.mallit.hyvaksy_vastaus") as mock_hyv:
        vastaus = asiakas.post("/api/tutkimukset/kyber-2025/kurssit/7/kysymykset/3/hyvaksy",
                               json={"nimi": "Matti"})
    assert vastaus.status_code == 200
    mock_hyv.assert_called_once_with(1, 7, 3, "Matti", "")


def test_api_hyvaksy_vastaus_vaatii_nimen():
    with patch("tietokanta.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("tietokanta.mallit.hyvaksy_vastaus") as mock_hyv:
        vastaus = asiakas.post("/api/tutkimukset/kyber-2025/kurssit/7/kysymykset/3/hyvaksy",
                               json={"nimi": ""})
    assert vastaus.status_code == 400
    mock_hyv.assert_not_called()


def test_api_tutkimus_arvioinnit_404_kun_ei_loydy():
    with patch("tietokanta.mallit.hae_tutkimus_slugilla", return_value=None):
        vastaus = asiakas.get("/api/tutkimukset/ei-ole/arvioinnit")
    assert vastaus.status_code == 404


def _korjaus(kysymykset, runko, kysid=30):
    with patch("tietokanta.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("tietokanta.mallit.hae_kysymykset", return_value=kysymykset), \
         patch("tietokanta.mallit.tallenna_hitl_vastaus") as tallenna:
        vastaus = asiakas.post(
            f"/api/tutkimukset/kyber-2025/kurssit/7/kysymykset/{kysid}/korjaus", json=runko)
    return vastaus, tallenna


def test_korjaus_tallentaa_luokan_ja_juurisyyn():
    runko = {"vastaus": "Ihmisen perustelu", "luokka": "Täysin",
             "nimi": "Testi Tekijä", "sahkoposti": "t@example.fi", "juurisyy": "llm_virhe"}
    vastaus, tallenna = _korjaus([KYSYMYS_LUOKITTELU], runko)
    assert vastaus.status_code == 200
    args, kwargs = tallenna.call_args
    assert args[:6] == (1, 7, 30, "Ihmisen perustelu", "Testi Tekijä", "t@example.fi")
    assert kwargs["luokka"] == "Täysin" and kwargs["juurisyy"] == "llm_virhe"


def test_korjaus_hylkaa_tuntemattoman_luokan():
    """Väärä luokka rikkoisi raporttitilastot hiljaa → 400 eikä tallennusta."""
    runko = {"vastaus": "p", "luokka": "Keksitty", "nimi": "T", "sahkoposti": "t@e.fi"}
    vastaus, tallenna = _korjaus([KYSYMYS_LUOKITTELU], runko)
    assert vastaus.status_code == 400
    tallenna.assert_not_called()


def test_korjaus_hylkaa_asteikon_ulkopuoliset_pisteet():
    runko = {"vastaus": "p", "pisteet": 9, "nimi": "T", "sahkoposti": "t@e.fi"}
    vastaus, tallenna = _korjaus([KYSYMYS_ASTEIKKO], runko, kysid=31)
    assert vastaus.status_code == 400
    tallenna.assert_not_called()


def test_korjaus_hyvaksyy_asteikon_rajalla():
    runko = {"vastaus": "p", "pisteet": 5, "nimi": "T", "sahkoposti": "t@e.fi"}
    vastaus, tallenna = _korjaus([KYSYMYS_ASTEIKKO], runko, kysid=31)
    assert vastaus.status_code == 200
    assert tallenna.call_args.kwargs["pisteet"] == 5


KYSYMYS_LISTA = {**KYSYMYS, "KysID": 32, "Luokittelu": "lista", "LuokitteluMaarittely": {"max_kohdat": 2}}


def test_korjaus_hylkaa_liian_pitkan_listan():
    """max_kohdat rajataan myös palvelimella, ei vain frontissa (#119)."""
    runko = {"vastaus": "p", "lista": ["a", "b", "c"], "nimi": "T", "sahkoposti": "t@e.fi"}
    vastaus, tallenna = _korjaus([KYSYMYS_LISTA], runko, kysid=32)
    assert vastaus.status_code == 400
    tallenna.assert_not_called()


def test_korjaus_hyvaksyy_listan_rajalla():
    runko = {"vastaus": "p", "lista": ["a", "b"], "nimi": "T", "sahkoposti": "t@e.fi"}
    vastaus, tallenna = _korjaus([KYSYMYS_LISTA], runko, kysid=32)
    assert vastaus.status_code == 200
    assert tallenna.call_args.kwargs["lista"] == ["a", "b"]


def test_korjaus_hylkaa_tuntemattoman_juurisyyn():
    runko = {"vastaus": "p", "luokka": "Täysin", "nimi": "T", "sahkoposti": "t@e.fi",
             "juurisyy": "keksitty_syy"}
    vastaus, tallenna = _korjaus([KYSYMYS_LUOKITTELU], runko)
    assert vastaus.status_code == 400
    tallenna.assert_not_called()


def test_korjaus_hylkaa_vieraan_kysymyksen():
    """Toisen tutkimuksen kysymykseen ei voi kirjoittaa korjausta."""
    runko = {"vastaus": "p", "nimi": "T", "sahkoposti": "t@e.fi"}
    vastaus, tallenna = _korjaus([KYSYMYS_LUOKITTELU], runko, kysid=999)
    assert vastaus.status_code == 404
    tallenna.assert_not_called()


def test_korjaus_vaatii_nimen():
    runko = {"vastaus": "p", "luokka": "Täysin", "nimi": "   ", "sahkoposti": "t@e.fi"}
    vastaus, tallenna = _korjaus([KYSYMYS_LUOKITTELU], runko)
    assert vastaus.status_code == 400
    tallenna.assert_not_called()


def test_arvioinnit_erottaa_llm_vastauksen_ja_korjauksen():
    llm_rivi = {"VasID": 1, "KysID": 10, "KID": 1, "Vastaus": "LLM sanoi", "Pisteet": None,
                "Luokka": None, "Malli": "testimalli"}
    hitl_rivi = {"KID": 1, "KysID": 10, "Vastaus": "Ihminen korjasi", "Pisteet": None,
                 "Luokka": None, "Lista": None, "KayttajaNimi": "Testi", "Malli": None,
                 "Sahkoposti": "t@e.fi", "Juurisyy": "riittamaton_opas",
                 "Aikaleima": "2026-09-25 10:00:00"}
    vanha_hitl = {**hitl_rivi, "Vastaus": "Vanhempi korjaus", "Aikaleima": "2026-09-24 10:00:00"}
    with patch("tietokanta.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("tietokanta.mallit.hae_kysymykset", return_value=[KYSYMYS]), \
         patch("tietokanta.mallit.hae_valitut_kurssit", return_value=[KURSSI_MUKANA]), \
         patch("tietokanta.mallit.hae_vastaukset", return_value=[hitl_rivi, vanha_hitl, llm_rivi]), \
         patch("tietokanta.mallit.hae_hitl_vastaukset") as ylimaarainen:
        data = asiakas.get("/api/tutkimukset/kyber-2025/arvioinnit").json()
    kurssi = data["kurssit"][0]
    assert kurssi["vastaukset"][0]["vastaus"] == "LLM sanoi"      # tekoälyn vastaus säilyy
    korjaus = kurssi["korjaukset"]["10"]  # JSON-avaimet ovat merkkijonoja
    assert korjaus["vastaus"] == "Ihminen korjasi"
    assert korjaus["nimi"] == "Testi" and korjaus["juurisyy"] == "riittamaton_opas"
    ylimaarainen.assert_not_called()   # ihmisen rivit tulevat jo hae_vastaukset-haussa


def test_api_tutkimus_arvioinnit_sivutettuna():
    # sivu/koko → SQL-rajaus (LIMIT/OFFSET) + yhteensa; vastaukset vain sivun kursseille.
    toinen = {**KURSSI_MUKANA, "KID": 2, "KurssiNimi": "Toinen"}
    vastaukset = [{"VasID": n, "KysID": 10, "KID": n, "Vastaus": f"v{n}", "Malli": "m"} for n in (1, 2)]
    with patch("tietokanta.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("tietokanta.mallit.hae_kysymykset", return_value=[KYSYMYS]), \
         patch("tietokanta.mallit.hae_valitut_kurssit", return_value=[toinen]) as valitut, \
         patch("tietokanta.mallit.laske_valitut_kurssit", return_value=2), \
         patch("tietokanta.mallit.hae_vastaukset", return_value=vastaukset):
        data = asiakas.get("/api/tutkimukset/kyber-2025/arvioinnit?sivu=1&koko=1").json()
    valitut.assert_called_once_with(TUTKIMUS["TID"], raja=1, siirto=1, kuvaukset=False)
    assert data["yhteensa"] == 2
    assert [k["KID"] for k in data["kurssit"]] == [2]
    assert data["kurssit"][0]["vastaukset"][0]["vastaus"] == "v2"
