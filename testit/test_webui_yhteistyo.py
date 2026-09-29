"""WebUI-testit: reaaliaikainen yhteistyö: näkymät, jaetut lomakkeet ja läsnäolo (webui/yhteistyo.py)."""
from webui import yhteistyo
from testit.webui_apu import _auth_pois  # noqa: F401 — autouse-fixture
from testit.webui_apu import asiakas


def test_suodatinnakyma_luodaan_postilla_ja_jaetaan(monkeypatch):
    # Suodatetut näkymävälilehdet ovat jaettua tilaa: luotu näkymä lähetetään
    # kaikille ja uusille yhteyksille; roskasyöte hylätään. Sama id uudelleen
    # (uudelleenlähetys kadonneen vastauksen jälkeen) on onnistuminen, ei tupla.
    monkeypatch.setattr(yhteistyo, "_nakymat", {})
    uusi = {"sivu": "/kurssit", "id": "abc", "nimi": "OULU", "suodatin": {"kkid": "3", "taso": None}}
    odotettu = {"/kurssit": [{"id": "abc", "nimi": "OULU", "suodatin": {"kkid": "3", "taso": None}}]}
    with asiakas.websocket_connect("/ws") as ws:
        assert ws.receive_json()["tyyppi"] == "oma-id"
        assert ws.receive_json() == {"tyyppi": "nakymat", "data": {}}
        assert asiakas.post("/api/nakymat", json=uusi).status_code == 200
        assert ws.receive_json() == {"tyyppi": "nakymat", "data": odotettu}
    assert asiakas.post("/api/nakymat", json=uusi).status_code == 200
    paha = {**uusi, "id": "x", "suodatin": {"kkid": {"sisakkainen": 1}}}
    assert asiakas.post("/api/nakymat", json=paha).status_code == 400
    with asiakas.websocket_connect("/ws") as ws:
        ws.receive_json()
        assert ws.receive_json()["data"] == odotettu


# --- Jaettu korjauslomake (HITL-modaalit yhteismuokattavina) ---

def _lomakeviesti(ws):
    """Seuraava lomake-sessio-viesti (ohittaa oma-id/nakymat-aloitusviestit)."""
    while True:
        viesti = ws.receive_json()
        if viesti["tyyppi"].startswith("lomake-"):
            return viesti


def test_lomakesessio_jaetaan_ja_ensimmaisen_arvot_sailyvat(monkeypatch):
    monkeypatch.setattr(yhteistyo, "_lomakkeet", {})
    with asiakas.websocket_connect("/ws") as a, asiakas.websocket_connect("/ws") as b:
        a.send_json({"tyyppi": "lomake-liity", "avain": "hitl:1:7", "arvot": {"nimi": "Aino", "perustelu": ""}})
        va = _lomakeviesti(a)
        assert va["arvot"] == {"nimi": "Aino", "perustelu": ""} and len(va["muokkaajat"]) == 1
        # 3.b: myöhemmin liittyvän omat arvot eivät korvaa ensimmäisen arvoja
        b.send_json({"tyyppi": "lomake-liity", "avain": "hitl:1:7", "arvot": {"nimi": "Bertta", "perustelu": ""}})
        vb = _lomakeviesti(b)
        assert vb["arvot"]["nimi"] == "Aino" and len(vb["muokkaajat"]) == 2
        assert len(_lomakeviesti(a)["muokkaajat"]) == 2
        # 2.c: arvon muutos ja kursori välittyvät muille; lahettaja kertoo kenen muutos
        b.send_json({"tyyppi": "lomake-arvo", "avain": "hitl:1:7", "kentta": "perustelu", "arvo": "ei kuulu", "kursori": 8})
        va = _lomakeviesti(a)
        assert _lomakeviesti(b)["lahettaja"] == va["lahettaja"]  # B:n oma kaiku (selain ohittaa)
        assert va["arvot"]["perustelu"] == "ei kuulu"
        bertta = [m for m in va["muokkaajat"] if m["id"] == va["lahettaja"]][0]
        assert bertta["kentta"] == "perustelu" and bertta["kursori"] == 8
        # roskasyöte ei muuta tilaa
        b.send_json({"tyyppi": "lomake-arvo", "avain": "hitl:1:7", "kentta": "perustelu", "arvo": {"x": 1}})
        # tallennus välittyy muille, jotta heidän modaalinsa sulkeutuu
        b.send_json({"tyyppi": "lomake-tallennettu", "avain": "hitl:1:7"})
        assert _lomakeviesti(a)["tyyppi"] == "lomake-tallennettu"
        b.send_json({"tyyppi": "lomake-poistu", "avain": "hitl:1:7"})
        va = _lomakeviesti(a)
        assert va["arvot"]["perustelu"] == "ei kuulu" and len(va["muokkaajat"]) == 1
        a.send_json({"tyyppi": "lomake-poistu", "avain": "hitl:1:7"})
        b.send_json({"tyyppi": "lomake-liity", "avain": "hitl:1:7", "arvot": {"nimi": "Bertta"}})
        # viimeisen poistuttua sessio häviää → seuraava avaaja on taas ensimmäinen (3.a)
        assert _lomakeviesti(b)["arvot"] == {"nimi": "Bertta"}


def test_lomakesessio_hyvaksyy_pitkan_raporttiosion(monkeypatch):
    # Raporttimuokkain on jaettu lomake (kenttä "teksti"): LLM:n kirjoittama osio voi
    # olla kymmeniä tuhansia merkkejä. Kohtuuton koko hylätään yhä (luottamusraja).
    monkeypatch.setattr(yhteistyo, "_lomakkeet", {})
    pitka = "x" * 60000
    with asiakas.websocket_connect("/ws") as a:
        a.send_json({"tyyppi": "lomake-liity", "avain": "raportti:1:johdanto", "arvot": {"teksti": pitka}})
        assert _lomakeviesti(a)["arvot"]["teksti"] == pitka
        a.send_json({"tyyppi": "lomake-liity", "avain": "raportti:1:liian", "arvot": {"teksti": "x" * 200001}})
        a.send_json({"tyyppi": "lomake-poistu", "avain": "raportti:1:johdanto"})
        a.send_json({"tyyppi": "uutinen", "teksti": "synkronointi"})
        while a.receive_json()["tyyppi"] != "uutinen":
            pass
    assert yhteistyo._lomakkeet == {}


# --- Läsnäolo: tilapäivitysten koonti ---

def _kayttajaviesti(ws):
    while True:
        viesti = ws.receive_json()
        if viesti["tyyppi"] == "kayttajat":
            return viesti


def test_lasnaolopaivitykset_kootaan_yhdeksi_lahetykseksi(monkeypatch):
    # Jokainen hiiren liike (80 ms) lähetti kaikkien tilan kaikille: O(käyttäjät²)
    # viestiä yhteisellä WiFillä. Koontiväli kerää peräkkäiset päivitykset yhteen
    # lähetykseen, jossa on uusin tila.
    # Yksi yhteys: TestClient ajaa jokaisen yhteyden omassa silmukassaan, eikä
    # koontitehtävän lähetys toisen silmukan yhteyteen toimi testissä (tuotannossa yksi silmukka).
    monkeypatch.setattr(yhteistyo, "_KOONTI_S", 0.2)
    monkeypatch.setattr(yhteistyo, "_koonti", None)
    with asiakas.websocket_connect("/ws") as a:
        for x in range(5):
            a.send_json({"nimimerkki": "A", "sijainti": {"x": x, "y": 0}})
        data = _kayttajaviesti(a)["data"]
        assert [k["sijainti"]["x"] for k in data] == [4]
