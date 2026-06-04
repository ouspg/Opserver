import json
import os
from unittest.mock import patch
from tiedonhaku.peppilukija import PeppiLukija

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "peppi_kurssi_45690.json")


def _lataa_fixture() -> dict:
    with open(FIXTURE, encoding="utf-8") as f:
        return json.load(f)


def _lukija() -> PeppiLukija:
    return PeppiLukija({"KKID": 1, "KouluNimi": "Oulun Yliopisto", "OpsOsoite": "https://opas.peppi.oulu.fi"})


def test_hae_kurssi_jasentaa_perustiedot():
    with patch.object(PeppiLukija, "_hae_json", return_value=_lataa_fixture()):
        kurssi = _lukija().hae_kurssi("45690")
    assert kurssi["kurssi_nimi"] == "Kyberturvallisuuden perusteet"
    assert kurssi["koodi"] == "IC00AU61"
    assert kurssi["opintopisteet"] == 5.0
    assert kurssi["lahde_id"] == "45690"


def test_hae_kurssi_paattelee_tason_kuvauksesta():
    with patch.object(PeppiLukija, "_hae_json", return_value=_lataa_fixture()):
        kurssi = _lukija().hae_kurssi("45690")
    assert kurssi["taso"] == "aine"


def test_hae_kurssi_lukee_oppiaineen():
    with patch.object(PeppiLukija, "_hae_json", return_value=_lataa_fixture()):
        kurssi = _lukija().hae_kurssi("45690")
    assert kurssi["oppiaine"] == "Tietotekniikka"


def test_hae_kurssi_kokoaa_kuvauksen():
    with patch.object(PeppiLukija, "_hae_json", return_value=_lataa_fixture()):
        kurssi = _lukija().hae_kurssi("45690")
    assert "Osaamistavoitteet" in kurssi["ops_kuvaus"]
    assert "kyber" in kurssi["ops_kuvaus"].lower()


def test_hae_kurssi_rakentaa_oikean_urlin():
    with patch.object(PeppiLukija, "_hae_json", return_value=_lataa_fixture()) as mock:
        _lukija().hae_kurssi("45690")
    url = mock.call_args[0][0]
    assert "opasbe.peppi.oulu.fi/api/course/45690" in url
    assert "period=2025-2026" in url


def test_taso_kartta_kattaa_kaikki_tasot():
    from tiedonhaku.peppilukija import paattele_taso
    assert paattele_taso("Yleisopinnot") == "yleis"
    assert paattele_taso("Perusopinnot") == "perus"
    assert paattele_taso("Aineopinnot") == "aine"
    assert paattele_taso("Syventävät opinnot") == "syventävä"
    assert paattele_taso("") is None
