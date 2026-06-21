"""Testit llm/asetukset.py:lle (.env-muutokset)."""
import os
from unittest.mock import patch
from llm import asetukset


def test_paivita_env_korvaa_olemassa_olevan_rivin(tmp_path):
    polku = tmp_path / ".env"
    polku.write_text("LLM_PROVIDER=https://x\nLLM_MODEL=vanha/malli\nMUU=arvo\n", encoding="utf-8")
    asetukset.paivita_env("LLM_MODEL", "uusi/malli", str(polku))
    sisalto = polku.read_text(encoding="utf-8")
    assert "LLM_MODEL=uusi/malli\n" in sisalto
    assert "vanha/malli" not in sisalto
    assert "LLM_PROVIDER=https://x" in sisalto  # muut rivit säilyvät
    assert "MUU=arvo" in sisalto


def test_paivita_env_lisaa_puuttuvan_avaimen(tmp_path):
    polku = tmp_path / ".env"
    polku.write_text("LLM_PROVIDER=https://x\n", encoding="utf-8")
    asetukset.paivita_env("LLM_MODEL", "uusi/malli", str(polku))
    sisalto = polku.read_text(encoding="utf-8")
    assert "LLM_MODEL=uusi/malli\n" in sisalto
    assert "LLM_PROVIDER=https://x" in sisalto


def test_paivita_env_lisaa_rivinvaihdon_jos_puuttuu(tmp_path):
    polku = tmp_path / ".env"
    polku.write_text("LLM_PROVIDER=https://x", encoding="utf-8")  # ei loppurivinvaihtoa
    asetukset.paivita_env("LLM_MODEL", "m", str(polku))
    assert polku.read_text(encoding="utf-8") == "LLM_PROVIDER=https://x\nLLM_MODEL=m\n"


def test_aseta_malli_paivittaa_ymparayston_ja_tiedoston(tmp_path):
    polku = tmp_path / ".env"
    polku.write_text("LLM_MODEL=vanha\n", encoding="utf-8")
    with patch("llm.asetukset._ENV_POLKU", str(polku)), patch.dict(os.environ, {}, clear=False):
        asetukset.aseta_malli("uusi/malli")
        assert os.environ["LLM_MODEL"] == "uusi/malli"
    assert "LLM_MODEL=uusi/malli\n" in polku.read_text(encoding="utf-8")


# --- konfiguraatiolukijat ---

def test_lue_int_lukee_ymparistosta():
    with patch.dict(os.environ, {"TESTI_LUKU": "42"}):
        assert asetukset.lue_int("TESTI_LUKU", 7) == 42


def test_lue_int_palauttaa_oletuksen_puuttuvalle_ja_kelvottomalle():
    with patch.dict(os.environ, {"TESTI_LUKU": "xyz"}):
        assert asetukset.lue_int("TESTI_LUKU", 7) == 7
    with patch.dict(os.environ, {}, clear=True):
        assert asetukset.lue_int("TESTI_LUKU", 7) == 7


def test_lue_float_lukee_ja_oletus():
    with patch.dict(os.environ, {"TESTI_F": "3.5"}):
        assert asetukset.lue_float("TESTI_F", 1.0) == 3.5
    with patch.dict(os.environ, {"TESTI_F": ""}):
        assert asetukset.lue_float("TESTI_F", 1.0) == 1.0


def test_aseta_arvo_paivittaa_env_ja_ymparayston(tmp_path):
    polku = tmp_path / ".env"
    polku.write_text("X=1\n", encoding="utf-8")
    with patch("llm.asetukset._ENV_POLKU", str(polku)), patch.dict(os.environ, {}, clear=False):
        asetukset.aseta_arvo("LUOKITTELU_ERAKOKO", "30")
        assert os.environ["LUOKITTELU_ERAKOKO"] == "30"
    assert "LUOKITTELU_ERAKOKO=30\n" in polku.read_text(encoding="utf-8")
