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
