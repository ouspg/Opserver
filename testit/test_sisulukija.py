import json
import os
from unittest.mock import patch, MagicMock, call
import requests
from tiedonhaku.sisulukija import SisuLukija, _muunna_taso, _fi, _riisu_html

DIR = os.path.dirname(__file__)


def _fixture(nimi: str):
    with open(os.path.join(DIR, "fixtures", nimi), encoding="utf-8") as f:
        return json.load(f)


def _lukija() -> SisuLukija:
    return SisuLukija({
        "KKID": 2,
        "KouluNimi": "Jyväskylän yliopisto",
        "OpsOsoite": "https://sisu.jyu.fi",
    })


YLIOPISTO_CONFIG_JS = """
var universityConfig = {
    "homeOrganisations": [{"id": "jyu-university-root-id", "name": {"fi": "Jyväskylän yliopisto"}}],
    "officialLanguages": ["fi", "en"]
};
"""


# --- _muunna_taso ---

def test_muunna_taso_perus():
    assert _muunna_taso("urn:code:study-level:basic-studies") == "perus"

def test_muunna_taso_aine():
    assert _muunna_taso("urn:code:study-level:intermediate-studies") == "aine"

def test_muunna_taso_syventava():
    assert _muunna_taso("urn:code:study-level:advanced-studies") == "syventävä"

def test_muunna_taso_yleis():
    assert _muunna_taso("urn:code:study-level:other-studies") == "yleis"

def test_muunna_taso_tuntematon_on_none():
    assert _muunna_taso("urn:code:study-level:language-studies") is None

def test_muunna_taso_none_on_none():
    assert _muunna_taso(None) is None


# --- _fi ---

def test_fi_palauttaa_suomen():
    assert _fi({"fi": "Testi", "en": "Test"}) == "Testi"

def test_fi_fallback_englantiin():
    assert _fi({"en": "Test"}) == "Test"

def test_fi_none_on_tyhja():
    assert _fi(None) == ""


# --- _riisu_html ---

def test_riisu_html_poistaa_tagit():
    assert _riisu_html("<p>Teksti</p>") == "Teksti"

def test_riisu_html_none_on_tyhja():
    assert _riisu_html(None) == ""


# --- hae_saatavilla_kaudet ---

def test_hae_saatavilla_kaudet_palauttaa_laskevassa_jarjestyksessa():
    lukija = _lukija()
    lukija._yliopisto_id = "jyu-university-root-id"
    with patch.object(SisuLukija, "_hae_json", return_value=_fixture("sisu_kaudet.json")):
        kaudet = lukija.hae_saatavilla_kaudet()
    assert kaudet[0] > kaudet[-1]
    assert "2025-2026" in kaudet
    assert "2024-2025" in kaudet

def test_hae_saatavilla_kaudet_suodattaa_ei_vuosimuotoiset():
    lukija = _lukija()
    lukija._yliopisto_id = "jyu-university-root-id"
    with patch.object(SisuLukija, "_hae_json", return_value=_fixture("sisu_kaudet.json")):
        kaudet = lukija.hae_saatavilla_kaudet()
    assert "-2017" not in kaudet
    assert all(len(k) == 9 and "-" in k for k in kaudet)


def test_hae_saatavilla_kaudet_hyvaksyy_yyyy_yy_muodon():  # Helsinki
    lukija = _lukija()
    lukija._yliopisto_id = "hy-university-root-id"
    kaudet_data = [
        {"documentState": "ACTIVE", "abbreviation": {"fi": "2025-26"}, "id": "hy-lv-76"},
        {"documentState": "ACTIVE", "abbreviation": {"fi": "2024-25"}, "id": "hy-lv-75"},
        {"documentState": "ACTIVE", "abbreviation": {"fi": "-2017"}, "id": "hy-lv-x"},
    ]
    with patch.object(SisuLukija, "_hae_json", return_value=kaudet_data):
        kaudet = lukija.hae_saatavilla_kaudet()
    assert "2025-26" in kaudet and "2024-25" in kaudet
    assert "-2017" not in kaudet


# --- _jasenna_kurssi ---

def test_jasenna_kurssi_perustiedot():
    lukija = _lukija()
    org_nimet = {"jy-ORG-25": "Informaatioteknologian tiedekunta"}
    kurssi_data = _fixture("sisu_kurssi.json")[0]
    kurssi = lukija._jasenna_kurssi(kurssi_data, org_nimet)
    assert kurssi["lahde_id"] == "otm-1e84a2f0-5e70-4e01-937c-60337616cff3"
    assert kurssi["koodi"] == "TJTA237"
    assert kurssi["kurssi_nimi"] == "Informaatio- ja tietotekniikkaoikeus"
    assert kurssi["taso"] == "aine"
    assert kurssi["oppiaine"] == "Informaatioteknologian tiedekunta"
    assert kurssi["opintopisteet"] == "5"

def test_jasenna_kurssi_kokoaa_kuvauksen():
    lukija = _lukija()
    kurssi_data = _fixture("sisu_kurssi.json")[0]
    kurssi = lukija._jasenna_kurssi(kurssi_data, {})
    assert "peruskysymyksiä" in kurssi["ops_kuvaus_teksti"]
    assert "lainsäädännön" in kurssi["ops_kuvaus_teksti"]


# --- hae_kurssit ---

def _mock_hae_json(url):
    if "curriculum-periods" in url:
        return _fixture("sisu_kaudet.json")
    if "organisations" in url:
        return _fixture("sisu_organisaatiot.json")
    if "course-unit-search" in url:
        return _fixture("sisu_haku_tulokset.json")
    if "by-group-id" in url:
        return _fixture("sisu_kurssi.json")
    raise ValueError(f"Tuntematon URL: {url}")


def test_hae_kurssit_tallentaa_uudet_kurssit():
    lukija = _lukija()
    lukija._yliopisto_id = "jyu-university-root-id"
    with patch.object(SisuLukija, "_hae_json", side_effect=_mock_hae_json), \
         patch("tiedonhaku.sisulukija.mallit.hae_tallennetut_lahde_idt", return_value=set()), \
         patch("tiedonhaku.sisulukija.mallit.tallenna_kurssi") as mock_tallenna:
        tallennettu, ohitettu = lukija.hae_kurssit("2025-2026")
    assert tallennettu == 1
    assert ohitettu == 0
    mock_tallenna.assert_called_once()
    kutsu_kwargs = mock_tallenna.call_args.kwargs
    assert kutsu_kwargs["lahde_id"] == "otm-1e84a2f0-5e70-4e01-937c-60337616cff3"
    assert kutsu_kwargs["koodi"] == "TJTA237"
    assert kutsu_kwargs["taso"] == "aine"
    assert kutsu_kwargs["opetusvuosi"] == "2025-2026"


def test_hae_kurssit_ohittaa_jo_kannassa_olevat():
    lukija = _lukija()
    lukija._yliopisto_id = "jyu-university-root-id"
    with patch.object(SisuLukija, "_hae_json", side_effect=_mock_hae_json), \
         patch("tiedonhaku.sisulukija.mallit.hae_tallennetut_lahde_idt",
               return_value={"otm-1e84a2f0-5e70-4e01-937c-60337616cff3"}), \
         patch("tiedonhaku.sisulukija.mallit.tallenna_kurssi") as mock_tallenna:
        tallennettu, ohitettu = lukija.hae_kurssit("2025-2026")
    mock_tallenna.assert_not_called()
    assert tallennettu == 0


def test_hae_kurssit_ohittaa_verkkovirheet():
    lukija = _lukija()
    lukija._yliopisto_id = "jyu-university-root-id"

    def hae_json_virhe(url):
        if "by-group-id" in url:
            raise requests.exceptions.ConnectionError("timeout")
        return _mock_hae_json(url)

    with patch.object(SisuLukija, "_hae_json", side_effect=hae_json_virhe), \
         patch("tiedonhaku.sisulukija.mallit.hae_tallennetut_lahde_idt", return_value=set()), \
         patch("tiedonhaku.sisulukija.mallit.tallenna_kurssi") as mock_tallenna:
        tallennettu, ohitettu = lukija.hae_kurssit("2025-2026")
    mock_tallenna.assert_not_called()
    assert ohitettu > 0
    assert tallennettu == 0


def test_hae_kurssit_kutsuu_edistyminen_cb():
    lukija = _lukija()
    lukija._yliopisto_id = "jyu-university-root-id"
    kutsut = []
    with patch.object(SisuLukija, "_hae_json", side_effect=_mock_hae_json), \
         patch("tiedonhaku.sisulukija.mallit.hae_tallennetut_lahde_idt", return_value=set()), \
         patch("tiedonhaku.sisulukija.mallit.tallenna_kurssi"):
        lukija.hae_kurssit("2025-2026", edistyminen_cb=lambda n, yht, nimi: kutsut.append(n))
    assert len(kutsut) == 1
    assert kutsut[0] == 1
