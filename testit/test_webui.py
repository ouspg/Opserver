from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from webui import palvelin
from webui.palvelin import sovellus

asiakas = TestClient(sovellus)


@pytest.fixture(autouse=True)
def _auth_pois(monkeypatch):
    """API-testit ajetaan ilman Basic Authia (LAN-oletus); estää .env-saastumisen.
    Tyhjentää myös staattiset välimuistit, ettei testi näe edellisen tulosta."""
    monkeypatch.delenv("WEBUI_AUTH_KAYTTAJA", raising=False)
    monkeypatch.delenv("WEBUI_AUTH_SALASANA", raising=False)
    asiakas.cookies.clear()  # estä auth-evästeen vuoto testien välillä
    palvelin.tyhjenna_valimuistit()
    yield
    palvelin.tyhjenna_valimuistit()

KURSSI = {
    "KID": 1, "KKID": 1, "LahdeId": "45690", "Koodi": "IC00AU61",
    "KurssiNimi": "Kyberturvallisuuden perusteet", "Taso": "aine",
    "Oppiaine": "Tietotekniikka", "Opintopisteet": 5.0,
    "Opetusvuosi": "2025-2026", "OpsKuvaus": '{"id":"45690"}',
}


def test_api_korkeakoulut_palauttaa_listan():
    rivit = [{"KKID": 1, "KouluNimi": "Tampereen yliopisto", "OpsOsoite": "https://esim.fi", "OpsTyyppi": "Peppi"}]
    with patch("webui.palvelin.mallit.hae_korkeakoulut", return_value=rivit), \
         patch("webui.palvelin.mallit.hae_kurssimaarat_kouluittain", return_value={}):
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
    mock.assert_called_once_with(kkid=2, lukuvuosi=None)


def test_api_kurssit_valittaa_lukuvuoden():
    with patch("webui.palvelin.mallit.hae_kurssit", return_value=[]) as mock:
        asiakas.get("/api/kurssit?lukuvuosi=2026-2027")
    mock.assert_called_once_with(kkid=None, lukuvuosi="2026-2027")


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
    with patch("webui.palvelin.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("webui.palvelin.mallit.hae_kysymykset", return_value=[]):
        vastaus = asiakas.get("/api/tutkimukset/kyber-2025")
    assert vastaus.status_code == 200
    assert vastaus.json()["LuokittelunNimi"] == "Kyber 2025"


def test_api_tutkimus_404_kun_ei_loydy():
    with patch("webui.palvelin.mallit.hae_tutkimus_slugilla", return_value=None):
        vastaus = asiakas.get("/api/tutkimukset/ei-ole")
    assert vastaus.status_code == 404


def test_api_luokitukset_valittaa_jarjestyksen():
    """▲▼-napit lähettävät jarjesta+suunta, jotka välitetään malleille."""
    with patch("webui.palvelin.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("webui.palvelin.mallit.hae_kurssit_luokituksilla", return_value=[]) as mock, \
         patch("webui.palvelin.mallit.hae_hitl_historia", return_value=[]):
        vastaus = asiakas.get(
            "/api/tutkimukset/kyber-2025/luokitukset?tila=mukana&jarjesta=op&suunta=laskeva")
    assert vastaus.status_code == 200
    assert mock.call_args.kwargs["jarjesta"] == "op"
    assert mock.call_args.kwargs["suunta"] == "laskeva"


KURSSI_MUKANA = {
    "KID": 1, "KKID": 1, "LahdeId": "45690", "Koodi": "IC00AU61",
    "KurssiNimi": "Kyberturvallisuuden perusteet", "Taso": "aine",
    "Oppiaine": "Tietotekniikka", "Opintopisteet": "5",
    "Opetusvuosi": "2025-2026", "OpsKuvaus": None,
}

KYSYMYS = {"KysID": 10, "TID": 1, "Kysymys": "Liittyykö kurssi kyberturvallisuuteen?",
           "Luokittelu": "vapaa_teksti", "LuokitteluMaarittely": None}


def test_api_tutkimus_arvioinnit_palauttaa_rakenteen():
    vastaus_rivi = {"VasID": 1, "KysID": 10, "KID": 1, "Vastaus": "Kyllä", "Pisteet": None, "Luokka": None}
    with patch("webui.palvelin.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("webui.palvelin.mallit.hae_kysymykset", return_value=[KYSYMYS]), \
         patch("webui.palvelin.mallit.hae_valitut_kurssit", return_value=[KURSSI_MUKANA]), \
         patch("webui.palvelin.mallit.hae_vastaukset", return_value=[vastaus_rivi]), \
         patch("webui.palvelin.mallit.hae_arviokommentit_kaikki", return_value=[]):
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


def test_api_tutkimus_arvioinnit_lista_vastaus():
    kysymys_lista = {**KYSYMYS, "KysID": 20, "Luokittelu": "lista", "LuokitteluMaarittely": {"max_kohdat": 5}}
    vastaus_rivi = {"VasID": 2, "KysID": 20, "KID": 1, "Vastaus": "Opetussuunnitelman mukaan",
                    "Pisteet": None, "Luokka": None, "Lista": ["Matematiikka", "Ohjelmointi"]}
    with patch("webui.palvelin.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("webui.palvelin.mallit.hae_kysymykset", return_value=[kysymys_lista]), \
         patch("webui.palvelin.mallit.hae_valitut_kurssit", return_value=[KURSSI_MUKANA]), \
         patch("webui.palvelin.mallit.hae_vastaukset", return_value=[vastaus_rivi]), \
         patch("webui.palvelin.mallit.hae_arviokommentit_kaikki", return_value=[]):
        vastaus = asiakas.get("/api/tutkimukset/kyber-2025/arvioinnit")
    assert vastaus.status_code == 200
    data = vastaus.json()
    assert data["kysymykset"][0]["Luokittelu"] == "lista"
    v = data["kurssit"][0]["vastaukset"][0]
    assert v["lista"] == ["Matematiikka", "Ohjelmointi"]
    assert v["vastaus"] == "Opetussuunnitelman mukaan"


def test_api_tutkimus_arvioinnit_tyhjat_vastaukset():
    with patch("webui.palvelin.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("webui.palvelin.mallit.hae_kysymykset", return_value=[KYSYMYS]), \
         patch("webui.palvelin.mallit.hae_valitut_kurssit", return_value=[KURSSI_MUKANA]), \
         patch("webui.palvelin.mallit.hae_vastaukset", return_value=[]), \
         patch("webui.palvelin.mallit.hae_arviokommentit_kaikki", return_value=[]):
        vastaus = asiakas.get("/api/tutkimukset/kyber-2025/arvioinnit")
    assert vastaus.status_code == 200
    data = vastaus.json()
    v = data["kurssit"][0]["vastaukset"][0]
    assert v["vastaus"] == ""
    assert v["luokka"] is None
    assert v["pisteet"] is None


def test_api_hitl_korjaus_tallentaa():
    with patch("webui.palvelin.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("webui.palvelin.mallit.tallenna_hitl_korjaus") as mock_tallenna:
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
    with patch("webui.palvelin.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("webui.palvelin.mallit.tallenna_hitl_korjaus") as mock_tallenna:
        vastaus = asiakas.post(
            "/api/tutkimukset/kyber-2025/kurssit/7/hitl",
            json={"uusi_tila": False, "perustelu": "x", "nimi": "M", "sahkoposti": "m@esim.fi"},
        )
    assert vastaus.status_code == 200
    mock_tallenna.assert_called_once_with(1, 7, False, "x", "M", "m@esim.fi", None)


def test_api_hitl_korjaus_hylkaa_tuntemattoman_juurisyyn():
    with patch("webui.palvelin.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("webui.palvelin.mallit.tallenna_hitl_korjaus") as mock_tallenna:
        vastaus = asiakas.post(
            "/api/tutkimukset/kyber-2025/kurssit/7/hitl",
            json={"uusi_tila": False, "perustelu": "x", "nimi": "M",
                  "sahkoposti": "m@esim.fi", "juurisyy": "keksitty"},
        )
    assert vastaus.status_code == 400
    mock_tallenna.assert_not_called()


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


def test_api_raportti_palauttaa_tyhjat_osiot_kun_ei_generoitu():
    with patch("webui.palvelin.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("webui.palvelin.mallit.hae_raportti_osiot", return_value={}):
        vastaus = asiakas.get("/api/tutkimukset/kyber-2025/raportti")
    assert vastaus.status_code == 200
    data = vastaus.json()
    assert data["tid"] == 1
    assert data["osiot"] == {}


def test_api_raportti_palauttaa_osiot():
    osiot = {"johdanto": "Tämä on johdanto.", "kurssit": "Kurssit.", "arvioinnit": "Arvioinnit."}
    with patch("webui.palvelin.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("webui.palvelin.mallit.hae_raportti_osiot", return_value=osiot):
        vastaus = asiakas.get("/api/tutkimukset/kyber-2025/raportti")
    assert vastaus.status_code == 200
    data = vastaus.json()
    assert data["osiot"]["johdanto"] == "Tämä on johdanto."
    assert len(data["osiot"]) == 3


def test_api_raportti_404_kun_tutkimusta_ei_loydy():
    with patch("webui.palvelin.mallit.hae_tutkimus_slugilla", return_value=None):
        vastaus = asiakas.get("/api/tutkimukset/ei-ole/raportti")
    assert vastaus.status_code == 404


def test_api_raportti_tilastot_luokittelu():
    ks = [{"KysID": 10, "TID": 1, "Kysymys": "Taso?",
            "Luokittelu": "luokittelu", "LuokitteluMaarittely": None}]
    vs = [
        {"KysID": 10, "KID": 1, "Vastaus": "perustelu", "Pisteet": None, "Luokka": "korkea"},
        {"KysID": 10, "KID": 2, "Vastaus": "perustelu", "Pisteet": None, "Luokka": "matala"},
        {"KysID": 10, "KID": 3, "Vastaus": "perustelu", "Pisteet": None, "Luokka": "korkea"},
    ]
    with patch("webui.palvelin.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("webui.palvelin.mallit.hae_kysymykset", return_value=ks), \
         patch("webui.palvelin.mallit.hae_vastaukset", return_value=vs), \
         patch("webui.palvelin.mallit.hae_tilastot_yliopistoittain", return_value=[]):
        vastaus = asiakas.get("/api/tutkimukset/kyber-2025/raportti/tilastot")
    assert vastaus.status_code == 200
    data = vastaus.json()
    k = data["kysymykset"][0]
    assert k["luokittelu"] == "luokittelu"
    assert k["jakauma"]["korkea"] == 2
    assert k["jakauma"]["matala"] == 1
    assert k["yhteensa"] == 3


def test_api_raportti_tilastot_asteikko():
    ks = [{"KysID": 11, "TID": 1, "Kysymys": "Pisteet?",
            "Luokittelu": "asteikko", "LuokitteluMaarittely": None}]
    vs = [
        {"KysID": 11, "KID": 1, "Vastaus": "perustelu", "Pisteet": 4.0, "Luokka": None},
        {"KysID": 11, "KID": 2, "Vastaus": "perustelu", "Pisteet": 2.0, "Luokka": None},
        {"KysID": 11, "KID": 3, "Vastaus": "perustelu", "Pisteet": 4.0, "Luokka": None},
    ]
    with patch("webui.palvelin.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("webui.palvelin.mallit.hae_kysymykset", return_value=ks), \
         patch("webui.palvelin.mallit.hae_vastaukset", return_value=vs), \
         patch("webui.palvelin.mallit.hae_tilastot_yliopistoittain", return_value=[]):
        vastaus = asiakas.get("/api/tutkimukset/kyber-2025/raportti/tilastot")
    assert vastaus.status_code == 200
    data = vastaus.json()
    k = data["kysymykset"][0]
    assert k["luokittelu"] == "asteikko"
    assert k["yhteensa"] == 3
    assert abs(k["keskiarvo"] - 10/3) < 0.01
    assert k["minimi"] == 2.0
    assert k["maksimi"] == 4.0
    assert k["jakauma"]["4"] == 2
    assert k["jakauma"]["2"] == 1


def test_api_raportti_tilastot_hitl_mittarit():
    """Rakenteellinen HITL-laatumittari: käsin-muutos-% + juurisyyjakauma."""
    tilastot = [
        {"KKID": 1, "KouluNimi": "TY", "KurssiYhteensa": 100, "LLMKasitelty": 40,
         "Mukana": 12, "Hylatty": 28, "HitlLkm": 3,
         "HitlKursseja": 3, "RiittamatonOpas": 2, "LlmVirhe": 1, "TuntematonSyy": 0},
        {"KKID": 2, "KouluNimi": "AY", "KurssiYhteensa": 80, "LLMKasitelty": 30,
         "Mukana": 8, "Hylatty": 22, "HitlLkm": 1,
         "HitlKursseja": 1, "RiittamatonOpas": 0, "LlmVirhe": 0, "TuntematonSyy": 1},
    ]
    with patch("webui.palvelin.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("webui.palvelin.mallit.hae_kysymykset", return_value=[]), \
         patch("webui.palvelin.mallit.hae_vastaukset", return_value=[]), \
         patch("webui.palvelin.mallit.hae_tilastot_yliopistoittain", return_value=tilastot):
        vastaus = asiakas.get("/api/tutkimukset/kyber-2025/raportti/tilastot")
    assert vastaus.status_code == 200
    hitl = vastaus.json()["hitl"]
    assert hitl["llm_kasitelty"] == 70
    assert hitl["muutettu"] == 4
    assert round(hitl["muutettu_pros"], 1) == 5.7
    assert hitl["opas"] == 2 and round(hitl["opas_pros"], 1) == 50.0
    assert hitl["llm_virhe"] == 1


def test_api_raportti_tilastot_404_kun_tutkimusta_ei_loydy():
    with patch("webui.palvelin.mallit.hae_tutkimus_slugilla", return_value=None):
        vastaus = asiakas.get("/api/tutkimukset/ei-ole/raportti/tilastot")
    assert vastaus.status_code == 404


def test_api_raportti_tilanne_palauttaa_tuoreuden():
    tilanne = {"generoitu": True, "tuoreus": "vanhentunut", "hitl_jalkeen": 2,
               "kommentit_jalkeen": 1, "puuttuu": [], "tarkistettu": "2026-07-15T12:00:00",
               "generoitu_aika": "2026-07-15T10:00:00", "osiot": []}
    # Raskas tuoreuslaskenta ajetaan taustalla → stubataan trigger pois testistä
    # (ei osu kantaan / ei säikeitä); endpoint palauttaa tallennetun tilanteen.
    with patch("webui.palvelin.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("webui.palvelin._kaynnista_taustatuoreus") as mock_tausta, \
         patch("webui.palvelin.llmraportti.koosta_tilanne", return_value=tilanne):
        vastaus = asiakas.get("/api/tutkimukset/kyber-2025/raportti/tilanne")
    assert vastaus.status_code == 200
    data = vastaus.json()
    assert data["tuoreus"] == "vanhentunut"
    assert data["tarkistettu"] == "2026-07-15T12:00:00"
    assert data["hitl_jalkeen"] == 2
    mock_tausta.assert_called_once()  # generoidulle raportille laukaistaan taustapäivitys


def test_api_raportti_tilanne_404_kun_tutkimusta_ei_loydy():
    with patch("webui.palvelin.mallit.hae_tutkimus_slugilla", return_value=None):
        vastaus = asiakas.get("/api/tutkimukset/ei-ole/raportti/tilanne")
    assert vastaus.status_code == 404


def test_taustatuoreus_ohitetaan_kun_tarkistettu_tuore():
    from datetime import datetime, timedelta
    tuore = {"Signatuuri": "x", "Tarkistettu": datetime.now() - timedelta(seconds=5)}
    with patch("webui.palvelin.mallit.hae_raportti_tuoreus", return_value=tuore), \
         patch("webui.palvelin.threading.Thread") as mock_thread:
        palvelin._kaynnista_taustatuoreus({"TID": 1})
    mock_thread.assert_not_called()  # tuore → ei uudelleenlaskentaa


def test_taustatuoreus_laukaistaan_kun_vanha():
    from datetime import datetime, timedelta
    vanha = {"Signatuuri": "x", "Tarkistettu": datetime.now() - timedelta(days=1)}
    try:
        with patch("webui.palvelin.mallit.hae_raportti_tuoreus", return_value=vanha), \
             patch("webui.palvelin.threading.Thread") as mock_thread:
            palvelin._kaynnista_taustatuoreus({"TID": 4242})
        mock_thread.assert_called_once()  # vanhentunut → taustalaskenta
    finally:
        palvelin._tuoreus_kaynnissa.discard(4242)  # siivoa globaali lippu


def test_taustatuoreus_laukaistaan_kun_ei_koskaan_laskettu():
    try:
        with patch("webui.palvelin.mallit.hae_raportti_tuoreus", return_value=None), \
             patch("webui.palvelin.threading.Thread") as mock_thread:
            palvelin._kaynnista_taustatuoreus({"TID": 4243})
        mock_thread.assert_called_once()
    finally:
        palvelin._tuoreus_kaynnissa.discard(4243)


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
    with patch("webui.palvelin.mallit.hae_tutkimukset_yhteenvedolla", return_value=[]):
        vastaus = asiakas.get("/api/tutkimukset", auth=("demo", "salainen"))
    assert vastaus.status_code == 200


def test_auth_pois_paalta_kun_env_tyhja():
    # Ilman WEBUI_AUTH-muuttujia (autouse-fixture poistanut) → ei vaadita tunnuksia
    with patch("webui.palvelin.mallit.hae_tutkimukset_yhteenvedolla", return_value=[]):
        vastaus = asiakas.get("/api/tutkimukset")
    assert vastaus.status_code == 200


# --- WebSocket-todennus Basic Authin alla (eväste, koska selain ei lähetä
#     Authorization-otsikkoa WS-kättelyssä) ---

def test_auth_asettaa_evasteen_oikeilla_tunnuksilla(monkeypatch):
    _aseta_auth(monkeypatch)
    with patch("webui.palvelin.mallit.hae_tutkimukset_yhteenvedolla", return_value=[]):
        vastaus = asiakas.get("/api/tutkimukset", auth=("demo", "salainen"))
    assert vastaus.status_code == 200
    assert vastaus.cookies.get("opserver_auth") == palvelin._auth_token("demo", "salainen")


def test_ws_kelpaa_auth_evasteella(monkeypatch):
    _aseta_auth(monkeypatch)
    token = palvelin._auth_token("demo", "salainen")
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


# --- Staattisten kyselyjen TTL-välimuisti ---

def test_lukuvuodet_valimuistitetaan():
    with patch("webui.palvelin.mallit.hae_lukuvuodet", return_value=["2025-2026"]) as mock:
        v1 = asiakas.get("/api/lukuvuodet")
        v2 = asiakas.get("/api/lukuvuodet")
    assert v1.json() == v2.json() == ["2025-2026"]
    assert mock.call_count == 1  # toinen pyyntö palvellaan välimuistista


def test_tasot_valimuisti_eri_argumentit_erikseen():
    with patch("webui.palvelin.mallit.hae_tasot", return_value=["perus"]) as mock:
        asiakas.get("/api/tasot")
        asiakas.get("/api/tasot")            # sama → välimuistista
        asiakas.get("/api/tasot?kkid=2")     # eri argumentti → uusi kysely
    assert mock.call_count == 2
