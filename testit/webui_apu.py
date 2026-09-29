"""WebUI-testien yhteinen testiasiakas, autouse-fixture ja testidata (testit/test_webui_*.py)."""
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


TUTKIMUS = {
    "TID": 1, "LuokittelunNimi": "Kyber 2025", "Slug": "kyber-2025",
    "Luokittelukehote": "valintakehote", "Tasorajaus": "aine",
    "Oppiainerajaus": None, "Arviointikehote": "arviointikehote",
}


KURSSI_MUKANA = {
    "KID": 1, "KKID": 1, "LahdeId": "45690", "Koodi": "IC00AU61",
    "KurssiNimi": "Kyberturvallisuuden perusteet", "Taso": "aine",
    "Oppiaine": "Tietotekniikka", "Opintopisteet": "5",
    "Opetusvuosi": "2025-2026", "OpsKuvaus": None,
}

KYSYMYS = {"KysID": 10, "TID": 1, "Kysymys": "Liittyykö kurssi kyberturvallisuuteen?",
           "Luokittelu": "vapaa_teksti", "LuokitteluMaarittely": None}


# --- Arviointien HITL-korjaus (tyyppikohtainen) ---

KYSYMYS_LUOKITTELU = {
    "KysID": 30, "TID": 1, "Kysymys": "Joustavuus?", "Luokittelu": "luokittelu",
    "LuokitteluMaarittely": {"luokat": [{"nimi": "Täysin", "kuvaus": "a"},
                                        {"nimi": "osittain", "kuvaus": "b"}]},
}
KYSYMYS_ASTEIKKO = {
    "KysID": 31, "TID": 1, "Kysymys": "Työelämälähtöisyys?", "Luokittelu": "asteikko",
    "LuokitteluMaarittely": {"minimi": 1, "maksimi": 5},
}
