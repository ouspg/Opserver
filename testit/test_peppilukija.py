import json
import os
from unittest.mock import patch, MagicMock, call
import requests
from tiedonhaku.peppilukija import (
    PeppiLukija, paattele_taso, generoi_kaudet, lue_kaudet_bundlesta,
    _kaudet_taulukosta, _kaudet_laskettuna, _turvallinen_float,
)

DIR = os.path.dirname(__file__)


def _fixture(nimi: str):
    with open(os.path.join(DIR, "fixtures", nimi), encoding="utf-8") as f:
        return json.load(f)


def _lukija() -> PeppiLukija:
    return PeppiLukija({"KKID": 1, "KouluNimi": "Oulun Yliopisto",
                        "OpsOsoite": "https://opas.peppi.oulu.fi",
                        "ApiOsoite": "https://opasbe.peppi.oulu.fi"})


# --- hae_kurssi ---

def test_hae_kurssi_jasentaa_perustiedot():
    with patch.object(PeppiLukija, "_hae_json", return_value=_fixture("peppi_kurssi_45690.json")):
        kurssi = _lukija().hae_kurssi("45690")
    assert kurssi["kurssi_nimi"] == "Kyberturvallisuuden perusteet"
    assert kurssi["koodi"] == "IC00AU61"
    assert kurssi["opintopisteet"] == "5.0"
    assert kurssi["lahde_id"] == "45690"


def test_hae_kurssi_tallentaa_tason_raakana():
    with patch.object(PeppiLukija, "_hae_json", return_value=_fixture("peppi_kurssi_45690.json")):
        kurssi = _lukija().hae_kurssi("45690")
    assert kurssi["taso"] == "Aineopinnot"


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


# --- kausilista JS-bundlesta ---

def test_generoi_kaudet_yhden_vuoden_jakso():
    kaudet = generoi_kaudet(ensimmainen=2020, viimeinen=2026, pituus=1)
    assert kaudet == ["2020-2021","2021-2022","2022-2023","2023-2024","2024-2025","2025-2026","2026-2027"]

def test_generoi_kaudet_kahden_vuoden_jakso():
    kaudet = generoi_kaudet(ensimmainen=2022, viimeinen=2026, pituus=2)
    assert kaudet == ["2022-2024","2024-2026","2026-2028"]

def test_hae_saatavilla_kaudet_lukee_bundlen():
    fake_js = "firstSchoolYear:2020,currentPeriodStartYear:2026,curriculumPeriod:1,showTags:!1"
    with patch("tiedonhaku.peppilukija._hae_bundle_js", return_value=fake_js):
        kaudet = _lukija().hae_saatavilla_kaudet()
    assert "2025-2026" in kaudet
    assert "2020-2021" in kaudet
    assert len(kaudet) == 7


# --- kausiparsinta: eksplisiittinen taulukko ensin, muuten laskettu ---

def test_kaudet_laskettuna_kaksoispiste_syntaksi():  # Oulu
    js = "firstSchoolYear:2020,currentPeriodStartYear:2026,curriculumPeriod:1"
    assert _kaudet_laskettuna(js)[-1] == "2026-2027"

def test_kaudet_laskettuna_yhtasuuruus_ja_oletuspituus():  # Åbo (ei curriculumPeriod)
    js = "this.firstSchoolYear=2018,this.currentPeriodStartYear=2024,search"
    kaudet = _kaudet_laskettuna(js)
    assert kaudet[0] == "2018-2019" and kaudet[-1] == "2024-2025"  # askel 1

def test_kaudet_taulukosta_lukee_sekapituiset_verbatim():  # UTU-tyyli, 2v + 3v
    js = 'x=["2018-2020","2020-2022","2022-2024","2024-2027"],y'
    assert _kaudet_taulukosta(js) == ["2018-2020","2020-2022","2022-2024","2024-2027"]

def test_kaudet_taulukosta_none_kun_ei_taulukkoa():
    assert _kaudet_taulukosta("firstSchoolYear:2020,curriculumPeriod:1") is None

def test_lue_kaudet_suosii_taulukkoa_yli_lasketun():
    js = 'firstSchoolYear:2020,currentPeriodStartYear:2026,curriculumPeriod:1,p=["2024-2025","2025-2026"]'
    assert lue_kaudet_bundlesta(js) == ["2024-2025", "2025-2026"]

# --- taso-kartta ---

def test_taso_kartta_kattaa_kaikki_tasot():
    assert paattele_taso("Yleisopinnot") == "yleis"
    assert paattele_taso("Perusopinnot") == "perus"
    assert paattele_taso("Aineopinnot") == "aine"
    assert paattele_taso("Syventävät opinnot") == "syventävä"
    assert paattele_taso("") is None


def test_paattele_taso_palauttaa_none_tuntemattomalle():
    assert paattele_taso("Muut opinnot") is None
    assert paattele_taso(None) is None


def test_turvallinen_float():
    assert _turvallinen_float(5) == 5.0
    assert _turvallinen_float("3.5") == 3.5
    assert _turvallinen_float(None) is None
    assert _turvallinen_float("5-10") is None
    assert _turvallinen_float("") is None


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
         patch("tiedonhaku.peppilukija.mallit.tallenna_kurssi", return_value=1) as mock_tallenna, \
         patch("tiedonhaku.peppilukija.mallit.hae_tallennetut_lahde_idt", return_value=set()):
        tallennettu, ohitettu = _lukija().hae_kurssit("2025-2026")

    assert tallennettu >= 1
    assert ohitettu == 0
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
         patch("tiedonhaku.peppilukija.mallit.tallenna_kurssi", return_value=1) as mock_tallenna, \
         patch("tiedonhaku.peppilukija.mallit.hae_tallennetut_lahde_idt", return_value=set()):
        _lukija().hae_kurssit("2025-2026")

    # Kurssi 45690 esiintyy molemmissa ohjelmissa mutta tallennetaan vain kerran
    kurssi_idt = [k.kwargs["lahde_id"] for k in mock_tallenna.call_args_list]
    assert kurssi_idt.count("45690") == 1


def test_hae_kurssit_ohittaa_verkkovirheet():
    """Mikä tahansa verkkovirhe yksittäisessä kurssissa ei kaada koko hakua."""
    nav = _fixture("peppi_navigaatio.json")[:1]
    edu = [{"id": "11738", "type": "EDUCATION", "name": {"valueFi": "Testi", "valueEn": "", "valueSv": ""},
            "children": [{"id": "1", "type": "PROGRAMME"}]}]
    plan = _fixture("peppi_accomplishment_plan_mini.json")  # sisältää id 45690

    def fake_hae_json(url, viive=True):
        if "/navigation" in url and "/navigation/" not in url:
            return nav
        if "/education-type" in url:
            return edu
        if "/accomplishment-plan/" in url:
            return plan
        if "/course/" in url:
            raise requests.exceptions.ConnectionError("yhteys katkesi")
        return []

    with patch.object(PeppiLukija, "_hae_json", side_effect=fake_hae_json), \
         patch("tiedonhaku.peppilukija.mallit.tallenna_kurssi", return_value=1) as mock_tallenna, \
         patch("tiedonhaku.peppilukija.mallit.hae_tallennetut_lahde_idt", return_value=set()):
        tallennettu, ohitettu = _lukija().hae_kurssit("2025-2026")

    assert tallennettu == 0
    assert ohitettu >= 1
    mock_tallenna.assert_not_called()


def test_hae_kurssit_ohittaa_jo_kannassa_olevat():
    """Kurssit, joiden LahdeId on jo tietokannassa, haetaan uudelleen."""
    nav = _fixture("peppi_navigaatio.json")[:1]
    edu = [{"id": "11738", "type": "EDUCATION", "name": {"valueFi": "Testi", "valueEn": "", "valueSv": ""},
            "children": [{"id": "1", "type": "PROGRAMME"}]}]
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
         patch("tiedonhaku.peppilukija.mallit.tallenna_kurssi", return_value=1) as mock_tallenna, \
         patch("tiedonhaku.peppilukija.mallit.hae_tallennetut_lahde_idt", return_value={"45690"}):
        tallennettu, ohitettu = _lukija().hae_kurssit("2025-2026")

    assert tallennettu == 0
    assert ohitettu == 0
    mock_tallenna.assert_not_called()
