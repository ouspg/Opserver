"""Testit luokittelun testierä-mittaukselle (eräkoon viritys)."""
import json
import re
from unittest.mock import patch, MagicMock
import pytest
from luokittelu import testierat


_TUTKIMUS = {
    "TID": 1,
    "Slug": "kyber",
    "LuokittelunNimi": "Kyber",
    "Luokittelukehote": "Luokittele kurssit.",
}


def _kurssit(n):
    return [
        {"KID": i, "KurssiNimi": f"Kurssi {i}", "Koodi": f"K{i}",
         "Taso": "perus", "Oppiaine": "tieto", "OpsKuvaus": "kuvaus"}
        for i in range(1, n + 1)
    ]


def _vastaus_json(idt):
    return json.dumps([{"id": i, "mukana": i % 2 == 0, "perustelu": "p"} for i in idt])


def _kaiuta_kysy(viesti, *a, **k):
    """Mock-LLM: palauttaa tuloksen jokaiselle viestissä esiintyvälle kurssi-id:lle."""
    idt = [int(x) for x in re.findall(r'"id":\s*(\d+)', viesti)]
    return _vastaus_json(idt)


@pytest.fixture
def mockit():
    """Mockaa kanta, LLM-kutsu ja kehotteet — ei verkkoa, ei tiedostoja."""
    with patch("luokittelu.testierat.mallit.hae_luokittelemattomat", return_value=_kurssit(4)), \
         patch("luokittelu.testierat.testimallit.aseta_testiluokitus") as aseta, \
         patch("luokittelu.testierat.llmluokittelu._lue_jarjestelmakehote", return_value="JARJ"), \
         patch("luokittelu.testierat.tiiviste.luokittelu", return_value="TIIV"), \
         patch("luokittelu.testierat.kutsu.hae_malli", return_value="openai/gpt-oss-120b:free"), \
         patch("luokittelu.testierat.kutsu.hae_viimeisin_kaytto",
               return_value={"prompt_tokens": 1000, "completion_tokens": 2048, "finish_reason": "stop"}), \
         patch("luokittelu.testierat.kutsu.kysy", side_effect=_kaiuta_kysy):
        yield {"aseta": aseta}


def test_kirjaa_tietueen_per_era(tmp_path, mockit):
    polku = tmp_path / "tilastot.jsonl"
    tulos = testierat.aja_testierat(_TUTKIMUS, erakoko=2, montako_era=2, tilastopolku=str(polku))
    assert tulos["eria"] == 2
    rivit = polku.read_text(encoding="utf-8").strip().splitlines()
    assert len(rivit) == 2


def test_uusi_ajo_ei_pyyhi_aiempaa_tilastoa(tmp_path, mockit):
    polku = tmp_path / "tilastot.jsonl"
    testierat.aja_testierat(_TUTKIMUS, erakoko=2, montako_era=2, tilastopolku=str(polku))
    testierat.aja_testierat(_TUTKIMUS, erakoko=4, montako_era=1, tilastopolku=str(polku))
    rivit = [json.loads(r) for r in polku.read_text(encoding="utf-8").strip().splitlines()]
    assert len(rivit) == 3  # 2 + 1 erää
    assert {r["erakoko_pyydetty"] for r in rivit} == {2, 4}


def test_tietue_sisaltaa_vertailuun_tarvittavan(tmp_path, mockit):
    polku = tmp_path / "tilastot.jsonl"
    testierat.aja_testierat(_TUTKIMUS, erakoko=2, montako_era=1, tilastopolku=str(polku))
    tietue = json.loads(polku.read_text(encoding="utf-8").strip())
    for avain in ("aikaleima", "ajo_id", "malli", "erakoko_pyydetty", "era_nro",
                  "kursseja_lahetetty", "tuloksia_saatu", "pudonneet", "jasennys",
                  "kesto_s", "syote_tokenit", "ulostulo_tokenit", "ulostulo_katto",
                  "ulostulo_tayttoaste", "finish_reason", "mukana", "hylatty", "paatokset"):
        assert avain in tietue, f"puuttuu: {avain}"
    assert tietue["ulostulo_tayttoaste"] == round(2048 / tietue["ulostulo_katto"], 3)
    assert tietue["kursseja_lahetetty"] == 2


def test_kirjaa_tulokset_testitauluun_ajotunnuksella(tmp_path, mockit):
    """Tulokset talletetaan kantaan (ei haaskata tokeneita), ajotunnuksella merkittyinä."""
    polku = tmp_path / "tilastot.jsonl"
    tulos = testierat.aja_testierat(_TUTKIMUS, erakoko=2, montako_era=2, tilastopolku=str(polku))
    # 4 kurssia → 4 testiluokitus-kirjausta, kaikki saman ajon tunnuksella
    assert mockit["aseta"].call_count == 4
    ajot = {kutsu.kwargs["ajo"] for kutsu in mockit["aseta"].call_args_list}
    assert ajot == {tulos["ajo_id"]}


def test_sama_kurssi_ei_osu_kahteen_eraan(tmp_path):
    """Satunnaisotos ilman takaisinpanoa: kukin kurssi enintään yhdessä erässä."""
    with patch("luokittelu.testierat.mallit.hae_luokittelemattomat", return_value=_kurssit(20)), \
         patch("luokittelu.testierat.testimallit.aseta_testiluokitus") as aseta, \
         patch("luokittelu.testierat.llmluokittelu._lue_jarjestelmakehote", return_value="JARJ"), \
         patch("luokittelu.testierat.tiiviste.luokittelu", return_value="TIIV"), \
         patch("luokittelu.testierat.kutsu.hae_malli", return_value="m"), \
         patch("luokittelu.testierat.kutsu.hae_viimeisin_kaytto", return_value={"finish_reason": "stop"}), \
         patch("luokittelu.testierat.kutsu.kysy", side_effect=_kaiuta_kysy):
        testierat.aja_testierat(_TUTKIMUS, erakoko=3, montako_era=3, tilastopolku=str(tmp_path / "t.jsonl"))
    kidt = [c.kwargs["kid"] for c in aseta.call_args_list]
    assert len(kidt) == 9              # 3 × 3 eri kurssia
    assert len(set(kidt)) == len(kidt)  # ei duplikaatteja


def test_pudonneet_kurssit_lasketaan(tmp_path):
    polku = tmp_path / "tilastot.jsonl"
    with patch("luokittelu.testierat.mallit.hae_luokittelemattomat", return_value=_kurssit(2)), \
         patch("luokittelu.testierat.testimallit.aseta_testiluokitus"), \
         patch("luokittelu.testierat.llmluokittelu._lue_jarjestelmakehote", return_value="JARJ"), \
         patch("luokittelu.testierat.tiiviste.luokittelu", return_value="TIIV"), \
         patch("luokittelu.testierat.kutsu.hae_malli", return_value="m"), \
         patch("luokittelu.testierat.kutsu.hae_viimeisin_kaytto", return_value={"finish_reason": "stop"}), \
         patch("luokittelu.testierat.kutsu.kysy", side_effect=lambda *a, **k: _vastaus_json([1])):
        testierat.aja_testierat(_TUTKIMUS, erakoko=2, montako_era=1, tilastopolku=str(polku))
    tietue = json.loads(polku.read_text(encoding="utf-8").strip())
    assert tietue["kursseja_lahetetty"] == 2
    assert tietue["tuloksia_saatu"] == 1
    assert tietue["pudonneet"] == 1


def test_jasennys_epaonnistuu_merkitaan(tmp_path):
    polku = tmp_path / "tilastot.jsonl"
    with patch("luokittelu.testierat.mallit.hae_luokittelemattomat", return_value=_kurssit(2)), \
         patch("luokittelu.testierat.testimallit.aseta_testiluokitus"), \
         patch("luokittelu.testierat.llmluokittelu._lue_jarjestelmakehote", return_value="JARJ"), \
         patch("luokittelu.testierat.tiiviste.luokittelu", return_value="TIIV"), \
         patch("luokittelu.testierat.kutsu.hae_malli", return_value="m"), \
         patch("luokittelu.testierat.kutsu.hae_viimeisin_kaytto", return_value={"finish_reason": "length"}), \
         patch("luokittelu.testierat.kutsu.kysy", side_effect=lambda *a, **k: "ei json"):
        testierat.aja_testierat(_TUTKIMUS, erakoko=2, montako_era=1, tilastopolku=str(polku))
    tietue = json.loads(polku.read_text(encoding="utf-8").strip())
    assert tietue["jasennys"] == "epaonnistui"
    assert tietue["tuloksia_saatu"] == 0
