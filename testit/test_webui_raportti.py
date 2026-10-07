"""WebUI-testit: raportti, tilastot ja tuoreus (webui/reitit_raportti.py)."""
from unittest.mock import patch
from webui import reitit_raportti
from testit.webui_apu import _auth_pois  # noqa: F401 — autouse-fixture
from testit.webui_apu import asiakas, TUTKIMUS


def test_api_raportti_palauttaa_tyhjat_osiot_kun_ei_generoitu():
    with patch("tietokanta.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("tietokanta.mallit.hae_raportti_osiot", return_value={}):
        vastaus = asiakas.get("/api/tutkimukset/kyber-2025/raportti")
    assert vastaus.status_code == 200
    data = vastaus.json()
    assert data["tid"] == 1
    assert data["osiot"] == {}


def test_api_raportti_palauttaa_osiot():
    osiot = {"johdanto": "Tämä on johdanto.", "kurssit": "Kurssit.", "arvioinnit": "Arvioinnit."}
    with patch("tietokanta.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("tietokanta.mallit.hae_raportti_osiot", return_value=osiot):
        vastaus = asiakas.get("/api/tutkimukset/kyber-2025/raportti")
    assert vastaus.status_code == 200
    data = vastaus.json()
    assert data["osiot"]["johdanto"] == "Tämä on johdanto."
    assert len(data["osiot"]) == 3


def test_api_raportti_404_kun_tutkimusta_ei_loydy():
    with patch("tietokanta.mallit.hae_tutkimus_slugilla", return_value=None):
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
    with patch("tietokanta.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("tietokanta.mallit.hae_kysymykset", return_value=ks), \
         patch("tietokanta.mallit.hae_vastaukset", return_value=vs), \
         patch("tietokanta.mallit.hae_tilastot_yliopistoittain", return_value=[]):
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
    with patch("tietokanta.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("tietokanta.mallit.hae_kysymykset", return_value=ks), \
         patch("tietokanta.mallit.hae_vastaukset", return_value=vs), \
         patch("tietokanta.mallit.hae_tilastot_yliopistoittain", return_value=[]):
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
    with patch("tietokanta.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("tietokanta.mallit.hae_kysymykset", return_value=[]), \
         patch("tietokanta.mallit.hae_vastaukset", return_value=[]), \
         patch("tietokanta.mallit.hae_tilastot_yliopistoittain", return_value=tilastot):
        vastaus = asiakas.get("/api/tutkimukset/kyber-2025/raportti/tilastot")
    assert vastaus.status_code == 200
    hitl = vastaus.json()["hitl"]
    assert hitl["llm_kasitelty"] == 70
    assert hitl["muutettu"] == 4
    assert round(hitl["muutettu_pros"], 1) == 5.7
    assert hitl["opas"] == 2 and round(hitl["opas_pros"], 1) == 50.0
    assert hitl["llm_virhe"] == 1


def test_api_raportti_tilastot_404_kun_tutkimusta_ei_loydy():
    with patch("tietokanta.mallit.hae_tutkimus_slugilla", return_value=None):
        vastaus = asiakas.get("/api/tutkimukset/ei-ole/raportti/tilastot")
    assert vastaus.status_code == 404


def test_api_raportti_tilanne_palauttaa_tuoreuden():
    tilanne = {"generoitu": True, "tuoreus": "vanhentunut", "hitl_jalkeen": 2,
               "arviokorjaukset_jalkeen": 1, "puuttuu": [], "tarkistettu": "2026-07-15T12:00:00",
               "generoitu_aika": "2026-07-15T10:00:00", "osiot": []}
    # Raskas tuoreuslaskenta ajetaan taustalla → stubataan trigger pois testistä
    # (ei osu kantaan / ei säikeitä); endpoint palauttaa tallennetun tilanteen.
    with patch("tietokanta.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("webui.reitit_raportti._kaynnista_taustatuoreus") as mock_tausta, \
         patch("raportti.llmraportti.koosta_tilanne", return_value=tilanne):
        vastaus = asiakas.get("/api/tutkimukset/kyber-2025/raportti/tilanne")
    assert vastaus.status_code == 200
    data = vastaus.json()
    assert data["tuoreus"] == "vanhentunut"
    assert data["tarkistettu"] == "2026-07-15T12:00:00"
    assert data["hitl_jalkeen"] == 2
    mock_tausta.assert_called_once()  # generoidulle raportille laukaistaan taustapäivitys


def test_api_raportti_tilanne_404_kun_tutkimusta_ei_loydy():
    with patch("tietokanta.mallit.hae_tutkimus_slugilla", return_value=None):
        vastaus = asiakas.get("/api/tutkimukset/ei-ole/raportti/tilanne")
    assert vastaus.status_code == 404


def test_taustatuoreus_ohitetaan_kun_tarkistettu_tuore():
    from datetime import datetime, timedelta
    tuore = {"Signatuuri": "x", "Tarkistettu": datetime.now() - timedelta(seconds=5)}
    with patch("tietokanta.mallit.hae_raportti_tuoreus", return_value=tuore), \
         patch("webui.reitit_raportti.threading.Thread") as mock_thread:
        reitit_raportti._kaynnista_taustatuoreus({"TID": 1})
    mock_thread.assert_not_called()  # tuore → ei uudelleenlaskentaa


def test_taustatuoreus_laukaistaan_kun_vanha():
    from datetime import datetime, timedelta
    vanha = {"Signatuuri": "x", "Tarkistettu": datetime.now() - timedelta(days=1)}
    try:
        with patch("tietokanta.mallit.hae_raportti_tuoreus", return_value=vanha), \
             patch("webui.reitit_raportti.threading.Thread") as mock_thread:
            reitit_raportti._kaynnista_taustatuoreus({"TID": 4242})
        mock_thread.assert_called_once()  # vanhentunut → taustalaskenta
    finally:
        reitit_raportti._tuoreus_kaynnissa.discard(4242)  # siivoa globaali lippu


def test_taustatuoreus_laukaistaan_kun_ei_koskaan_laskettu():
    try:
        with patch("tietokanta.mallit.hae_raportti_tuoreus", return_value=None), \
             patch("webui.reitit_raportti.threading.Thread") as mock_thread:
            reitit_raportti._kaynnista_taustatuoreus({"TID": 4243})
        mock_thread.assert_called_once()
    finally:
        reitit_raportti._tuoreus_kaynnissa.discard(4243)


def test_raporttiosio_tallennetaan_postilla():
    with patch("tietokanta.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("tietokanta.mallit.aseta_raportti_osio") as aseta:
        vastaus = asiakas.post("/api/tutkimukset/kyber-2025/raportti/johdanto", json={"teksti": "Uusi"})
    assert vastaus.status_code == 200
    aseta.assert_called_once_with(TUTKIMUS["TID"], "johdanto", "Uusi")


def test_api_raportti_tilastot_ihmisen_korjaus_voittaa_eika_tuplaa():
    """hae_vastaukset palauttaa saman (KID, KysID) -parin HITL-rivin ensin ja
    LLM-rivin sen jälkeen — tilastoon vain ensimmäinen."""
    ks = [{"KysID": 10, "TID": 1, "Kysymys": "Taso?",
            "Luokittelu": "luokittelu", "LuokitteluMaarittely": None}]
    vs = [
        {"KysID": 10, "KID": 1, "Vastaus": "korjattu", "Pisteet": None, "Luokka": "matala", "Malli": None},
        {"KysID": 10, "KID": 1, "Vastaus": "perustelu", "Pisteet": None, "Luokka": "korkea", "Malli": "m"},
        {"KysID": 10, "KID": 2, "Vastaus": "perustelu", "Pisteet": None, "Luokka": "korkea", "Malli": "m"},
    ]
    with patch("tietokanta.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("tietokanta.mallit.hae_kysymykset", return_value=ks), \
         patch("tietokanta.mallit.hae_vastaukset", return_value=vs), \
         patch("tietokanta.mallit.hae_tilastot_yliopistoittain", return_value=[]):
        data = asiakas.get("/api/tutkimukset/kyber-2025/raportti/tilastot").json()
    k = data["kysymykset"][0]
    assert k["jakauma"] == {"matala": 1, "korkea": 1}
    assert k["yhteensa"] == 2


def test_api_raportti_tilastot_vain_nykyiset_mukana_kurssit():
    """Tilastot lasketaan vain kursseista, jotka ovat nyt mukana (Mukana = 1):
    HITL:ssä pois käännetyn kurssin vanhat arviot eivät saa paisuttaa lukuja."""
    with patch("tietokanta.mallit.hae_tutkimus_slugilla", return_value=TUTKIMUS), \
         patch("tietokanta.mallit.hae_kysymykset", return_value=[]), \
         patch("tietokanta.mallit.hae_vastaukset", return_value=[]) as hae, \
         patch("tietokanta.mallit.hae_tilastot_yliopistoittain", return_value=[]):
        asiakas.get("/api/tutkimukset/kyber-2025/raportti/tilastot")
    hae.assert_called_once_with(TUTKIMUS["TID"], vain_mukana=True)
