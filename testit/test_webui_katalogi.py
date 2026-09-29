"""WebUI-testit: katalogi, tutkimukset, staattiset tiedostot ja pakkaus (webui/reitit_katalogi.py, palvelin.py)."""
from unittest.mock import patch
from testit.webui_apu import _auth_pois  # noqa: F401 — autouse-fixture
from testit.webui_apu import asiakas, KURSSI, TUTKIMUS


def test_api_korkeakoulut_palauttaa_listan():
    rivit = [{"KKID": 1, "KouluNimi": "Tampereen yliopisto", "OpsOsoite": "https://esim.fi", "OpsTyyppi": "Peppi"}]
    with patch("tietokanta.mallit.hae_korkeakoulut", return_value=rivit), \
         patch("tietokanta.mallit.hae_kurssimaarat_kouluittain", return_value={}):
        vastaus = asiakas.get("/api/korkeakoulut")
    assert vastaus.status_code == 200
    assert vastaus.json()[0]["KouluNimi"] == "Tampereen yliopisto"


def test_api_kurssit_palauttaa_listan():
    with patch("tietokanta.mallit.hae_kurssit", return_value=[KURSSI]):
        vastaus = asiakas.get("/api/kurssit")
    assert vastaus.status_code == 200
    data = vastaus.json()
    assert len(data) == 1
    assert data[0]["KurssiNimi"] == "Kyberturvallisuuden perusteet"


def test_api_kurssit_suodattaa_kkid_perusteella():
    with patch("tietokanta.mallit.hae_kurssit", return_value=[]) as mock:
        asiakas.get("/api/kurssit?kkid=2")
    mock.assert_called_once_with(kkid=2, lukuvuosi=None)


def test_api_kurssit_valittaa_lukuvuoden():
    with patch("tietokanta.mallit.hae_kurssit", return_value=[]) as mock:
        asiakas.get("/api/kurssit?lukuvuosi=2026-2027")
    mock.assert_called_once_with(kkid=None, lukuvuosi="2026-2027")


def test_api_kurssi_palauttaa_ops_kuvauksen():
    with patch("tietokanta.mallit.hae_kurssi", return_value=KURSSI):
        vastaus = asiakas.get("/api/kurssit/1")
    assert vastaus.status_code == 200
    assert vastaus.json()["OpsKuvaus"] is not None


def test_api_kurssi_404_kun_ei_loydy():
    with patch("tietokanta.mallit.hae_kurssi", return_value=None):
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


def test_api_tutkimukset_palauttaa_listan():
    with patch("tietokanta.mallit.hae_tutkimukset_yhteenvedolla", return_value=[{**TUTKIMUS, "MukanaLkm": 0}]):
        vastaus = asiakas.get("/api/tutkimukset")
    assert vastaus.status_code == 200
    assert vastaus.json()[0]["Slug"] == "kyber-2025"


def test_api_tutkimus_slugilla_palauttaa_yhden():
    with patch("tietokanta.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("tietokanta.mallit.hae_kysymykset", return_value=[]):
        vastaus = asiakas.get("/api/tutkimukset/kyber-2025")
    assert vastaus.status_code == 200
    assert vastaus.json()["LuokittelunNimi"] == "Kyber 2025"


def test_api_tutkimus_404_kun_ei_loydy():
    with patch("tietokanta.mallit.hae_tutkimus_slugilla", return_value=None):
        vastaus = asiakas.get("/api/tutkimukset/ei-ole")
    assert vastaus.status_code == 404


def test_tasot_valimuisti_eri_argumentit_erikseen():
    with patch("tietokanta.mallit.hae_tasot", return_value=["perus"]) as mock:
        asiakas.get("/api/tasot")
        asiakas.get("/api/tasot")            # sama → välimuistista
        asiakas.get("/api/tasot?kkid=2")     # eri argumentti → uusi kysely
    assert mock.call_count == 2


# --- Osittainen lataus (huono yhteys): gzip + sivutus ---

def test_json_vastaus_pakataan_gzipilla():
    koulut = [{"KKID": i, "KouluNimi": f"Koulu {i}", "OpsOsoite": "https://esim.fi", "OpsTyyppi": "Peppi"}
              for i in range(100)]
    with patch("tietokanta.mallit.hae_korkeakoulut", return_value=koulut), \
         patch("tietokanta.mallit.hae_kurssimaarat_kouluittain", return_value={}):
        vastaus = asiakas.get("/api/korkeakoulut", headers={"Accept-Encoding": "gzip"})
    assert vastaus.headers.get("content-encoding") == "gzip"
    assert len(vastaus.json()) == 100


def test_api_kurssit_sivutettuna():
    rivit = [{**KURSSI, "KID": n} for n in range(5)]
    with patch("tietokanta.mallit.hae_kurssit", return_value=rivit):
        data = asiakas.get("/api/kurssit?alku=2&koko=2").json()
    assert [k["KID"] for k in data] == [2, 3]
def test_webui_skripteissa_ei_paallekkaisia_globaaleja_funktioita():
    # Klassiset <script>-tiedostot jakavat globaalin näkyvyysalueen: myöhemmin
    # ladatun tiedoston samanniminen funktio ylikirjoittaa aiemman hiljaa
    # (raporttimuokkaus.js:n tallenna() kaappasi arvioinnin "Tallenna korjaus").
    # Lohkoon ("{" heti "use strict":n jälkeen) kääritty tiedosto ei vuoda globaaleja.
    import re
    from pathlib import Path
    nahdyt: dict[str, str] = {}
    for polku in sorted(Path("webui/staattinen").glob("*.js")):
        teksti = polku.read_text()
        if re.match(r'"use strict";\s*(//[^\n]*\n\s*)*\{\n', teksti):
            continue
        for nimi in re.findall(r"^(?:async )?function (\w+)", teksti, re.M):
            assert nimi not in nahdyt, f"{nimi}: {nahdyt[nimi]} ja {polku.name}"
            nahdyt[nimi] = polku.name
