"""Testit arvioinnin testierä-mittaukselle (eräkoon viritys)."""
import json
from unittest.mock import patch
import pytest
from arviointi import testierat


_TUTKIMUS = {"TID": 1, "Slug": "kyber", "LuokittelunNimi": "Kyber"}

_KYSYMYKSET = [{"KysID": 10, "Kysymys": "Onko relevantti?", "Luokittelu": "vapaa_teksti"}]


def _kurssi(kid):
    return {"KID": kid, "KurssiNimi": f"Kurssi {kid}", "Koodi": f"K{kid}",
            "Taso": "perus", "Oppiaine": "tieto", "OpsKuvaus": "kuvaus"}


def _tieto(n_kurssia):
    kurssit = {i: _kurssi(i) for i in range(1, n_kurssia + 1)}
    return {
        "kysymykset": _KYSYMYKSET,
        "jarjestelma": "JARJ",
        "kys_tiiviste": {10: "TIIV"},
        "arviointikehote": "Arvioi.",
        "kurssi_kartta": kurssit,
        "olemassa": {},
        "tyo": {i: _KYSYMYKSET for i in kurssit},
    }


def _vastaus_obj(idt):
    return json.dumps({"tulokset": [{"id": i, "vastaukset": ["vapaa vastaus"]} for i in idt]})


def _kaiuta(viesti, *a, **k):
    import re
    idt = [int(x) for x in re.findall(r'"id":\s*(\d+)', viesti)]
    return _vastaus_obj(idt)


@pytest.fixture
def mockit():
    with patch("arviointi.testierat.llmarviointi._selvita_tyo", return_value=_tieto(4)), \
         patch("arviointi.testierat.testimallit.aseta_testivastaus") as aseta, \
         patch("arviointi.testierat.kutsu.hae_malli", return_value="openai/gpt-oss-120b:free"), \
         patch("arviointi.testierat.kutsu.hae_viimeisin_kaytto",
               return_value={"prompt_tokens": 1000, "completion_tokens": 1024, "finish_reason": "stop"}), \
         patch("arviointi.testierat.kutsu.kysy", side_effect=_kaiuta):
        yield {"aseta": aseta}


def test_kirjaa_tietueen_per_era(tmp_path, mockit):
    polku = tmp_path / "t.jsonl"
    tulos = testierat.aja_testierat(_TUTKIMUS, erakoko=2, montako_era=2, tilastopolku=str(polku))
    assert tulos["eria"] == 2
    assert len(polku.read_text(encoding="utf-8").strip().splitlines()) == 2


def test_uusi_ajo_ei_pyyhi_aiempaa(tmp_path, mockit):
    polku = tmp_path / "t.jsonl"
    testierat.aja_testierat(_TUTKIMUS, erakoko=2, montako_era=2, tilastopolku=str(polku))
    testierat.aja_testierat(_TUTKIMUS, erakoko=4, montako_era=1, tilastopolku=str(polku))
    rivit = [json.loads(r) for r in polku.read_text(encoding="utf-8").strip().splitlines()]
    assert len(rivit) == 3
    assert {r["erakoko_pyydetty"] for r in rivit} == {2, 4}


def test_tietue_sisaltaa_vertailutiedot(tmp_path, mockit):
    polku = tmp_path / "t.jsonl"
    testierat.aja_testierat(_TUTKIMUS, erakoko=2, montako_era=1, tilastopolku=str(polku))
    tietue = json.loads(polku.read_text(encoding="utf-8").strip().splitlines()[0])
    for avain in ("ajo_id", "erakoko_pyydetty", "kursseja_lahetetty", "kysymyksia",
                  "tuloksia_saatu", "pudonneet", "jasennys", "ulostulo_tayttoaste",
                  "finish_reason", "ulostulo_katto"):
        assert avain in tietue, f"puuttuu: {avain}"
    assert tietue["ulostulo_tayttoaste"] == round(1024 / tietue["ulostulo_katto"], 3)


def test_kirjaa_vastaukset_testitauluun_ajotunnuksella(tmp_path, mockit):
    polku = tmp_path / "t.jsonl"
    tulos = testierat.aja_testierat(_TUTKIMUS, erakoko=2, montako_era=2, tilastopolku=str(polku))
    # 4 kurssia × 1 kysymys = 4 vastauskirjausta saman ajon tunnuksella
    assert mockit["aseta"].call_count == 4
    assert {c.kwargs["ajo"] for c in mockit["aseta"].call_args_list} == {tulos["ajo_id"]}


def test_ei_tyota_palauttaa_tyhjan(tmp_path):
    tieto = _tieto(0)
    with patch("arviointi.testierat.llmarviointi._selvita_tyo", return_value=tieto):
        tulos = testierat.aja_testierat(_TUTKIMUS, erakoko=2, montako_era=1,
                                        tilastopolku=str(tmp_path / "t.jsonl"))
    assert tulos["eria"] == 0


def test_jasennys_epaonnistuu_merkitaan(tmp_path):
    with patch("arviointi.testierat.llmarviointi._selvita_tyo", return_value=_tieto(2)), \
         patch("arviointi.testierat.testimallit.aseta_testivastaus"), \
         patch("arviointi.testierat.kutsu.hae_malli", return_value="m"), \
         patch("arviointi.testierat.kutsu.hae_viimeisin_kaytto", return_value={"finish_reason": "length"}), \
         patch("arviointi.testierat.kutsu.kysy", side_effect=lambda *a, **k: "ei json"):
        testierat.aja_testierat(_TUTKIMUS, erakoko=2, montako_era=1,
                                tilastopolku=str(tmp_path / "t.jsonl"))
    tietue = json.loads((tmp_path / "t.jsonl").read_text(encoding="utf-8").strip())
    assert tietue["jasennys"] == "epaonnistui"
    assert tietue["tuloksia_saatu"] == 0
