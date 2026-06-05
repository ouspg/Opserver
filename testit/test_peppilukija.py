import json
import os
from unittest.mock import patch, MagicMock, call
from tiedonhaku.peppilukija import PeppiLukija, paattele_taso

DIR = os.path.dirname(__file__)


def _fixture(nimi: str):
    with open(os.path.join(DIR, "fixtures", nimi), encoding="utf-8") as f:
        return json.load(f)


def _lukija() -> PeppiLukija:
    return PeppiLukija({"KKID": 1, "KouluNimi": "Oulun Yliopisto", "OpsOsoite": "https://opas.peppi.oulu.fi"})


# --- hae_kurssi ---

def test_hae_kurssi_jasentaa_perustiedot():
    with patch.object(PeppiLukija, "_hae_json", return_value=_fixture("peppi_kurssi_45690.json")):
        kurssi = _lukija().hae_kurssi("45690")
    assert kurssi["kurssi_nimi"] == "Kyberturvallisuuden perusteet"
    assert kurssi["koodi"] == "IC00AU61"
    assert kurssi["opintopisteet"] == 5.0
    assert kurssi["lahde_id"] == "45690"


def test_hae_kurssi_paattelee_tason_kuvauksesta():
    with patch.object(PeppiLukija, "_hae_json", return_value=_fixture("peppi_kurssi_45690.json")):
        kurssi = _lukija().hae_kurssi("45690")
    assert kurssi["taso"] == "aine"


def test_hae_kurssi_lukee_oppiaineen():
    with patch.object(PeppiLukija, "_hae_json", return_value=_fixture("peppi_kurssi_45690.json")):
        kurssi = _lukija().hae_kurssi("45690")
    assert kurssi["oppiaine"] == "Tietotekniikka"


def test_hae_kurssi_rakentaa_oikean_urlin():
    with patch.object(PeppiLukija, "_hae_json", return_value=_fixture("peppi_kurssi_45690.json")) as mock:
        _lukija().hae_kurssi("45690", kausi="2025-2026")
    url = mock.call_args[0][0]
    assert "opasbe.peppi.oulu.fi/api/course/45690" in url
    assert "period=2025-2026" in url


# --- taso-kartta ---

def test_taso_kartta_kattaa_kaikki_tasot():
    assert paattele_taso("Yleisopinnot") == "yleis"
    assert paattele_taso("Perusopinnot") == "perus"
    assert paattele_taso("Aineopinnot") == "aine"
    assert paattele_taso("Syventävät opinnot") == "syventävä"
    assert paattele_taso("") is None


# --- hae_kurssit ---

def test_hae_kurssit_kayttaa_oikeita_endpointteja():
    nav = _fixture("peppi_navigaatio.json")[:2]
    edu = _fixture("peppi_education_type_mini.json")
    plan = _fixture("peppi_accomplishment_plan_mini.json")
    kurssi = _fixture("peppi_kurssi_45690.json")

    # Ohjelma-id:t mini-fixturessa
    ohjelma_idt = [str(c["id"]) for e in edu for c in (e.get("children") or [])]

    def fake_hae_json(url, viive=True):
        if "/navigation" in url and "/navigation/" not in url:
            return nav
        if "/education-type" in url:
            return edu
        if "/accomplishment-plan/" in url:
            return plan
        if "/course/" in url:
            return kurssi
        return []

    with patch.object(PeppiLukija, "_hae_json", side_effect=fake_hae_json), \
         patch("tiedonhaku.peppilukija.mallit.tallenna_kurssi", return_value=1) as mock_tallenna:
        maara = _lukija().hae_kurssit("2025-2026")

    assert maara >= 1
    mock_tallenna.assert_called()
    kutsu = mock_tallenna.call_args
    assert kutsu.kwargs["opetusvuosi"] == "2025-2026"
    assert kutsu.kwargs["kkid"] == 1


def test_hae_kurssit_deduplikoi_kurssit():
    """Sama kurssi-id kahdessa ohjelmassa tallennetaan vain kerran."""
    nav = _fixture("peppi_navigaatio.json")[:1]
    edu = [{"id": "11738", "type": "EDUCATION", "name": {"valueFi": "Testi", "valueEn": "", "valueSv": ""},
            "children": [{"id": "1", "type": "PROGRAMME"}, {"id": "2", "type": "PROGRAMME"}]}]
    plan = _fixture("peppi_accomplishment_plan_mini.json")  # sisältää id 45690

    def fake_hae_json(url, viive=True):
        if "/navigation" in url and "/navigation/" not in url:
            return nav
        if "/education-type" in url:
            return edu
        if "/accomplishment-plan/" in url:
            return plan
        if "/course/" in url:
            return _fixture("peppi_kurssi_45690.json")
        return []

    with patch.object(PeppiLukija, "_hae_json", side_effect=fake_hae_json), \
         patch("tiedonhaku.peppilukija.mallit.tallenna_kurssi", return_value=1) as mock_tallenna:
        _lukija().hae_kurssit("2025-2026")

    # Kurssi 45690 esiintyy molemmissa ohjelmissa mutta tallennetaan vain kerran
    kurssi_idt = [k.kwargs["lahde_id"] for k in mock_tallenna.call_args_list]
    assert kurssi_idt.count("45690") == 1
