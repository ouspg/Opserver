"""Testit llm/mallitiedot.py:lle."""
import os
from unittest.mock import patch, MagicMock
import pytest
from llm import mallitiedot


_ENV = {"LLM_PROVIDER": "https://openrouter.ai/api/v1", "LLM_API_KEY": "avain", "LLM_MODEL": "openai/gpt-oss-120b:free"}

_DATA = [
    {"id": "openai/gpt-oss-120b:free", "context_length": 131072, "pricing": {"prompt": "0", "completion": "0"}},
    {"id": "anthropic/claude-fable-5", "context_length": 200000,
     "pricing": {"prompt": "0.000003", "completion": "0.000015", "input_cache_read": "0.0000003"}},
]


@pytest.fixture(autouse=True)
def nollaa_kakku():
    mallitiedot._mallit_kakku = None
    yield
    mallitiedot._mallit_kakku = None


def _mock_get(data):
    vastaus = MagicMock()
    vastaus.status_code = 200
    vastaus.json.return_value = {"data": data}
    return vastaus


class TestHaeMallit:
    def test_hakee_ja_palauttaa_data_listan(self):
        with patch.dict(os.environ, _ENV), \
             patch("llm.mallitiedot.requests.get", return_value=_mock_get(_DATA)) as mock_get:
            tulos = mallitiedot.hae_mallit()
        assert tulos == _DATA
        assert mock_get.call_args[0][0] == "https://openrouter.ai/api/v1/models"

    def test_kakuttaa_tuloksen(self):
        with patch.dict(os.environ, _ENV), \
             patch("llm.mallitiedot.requests.get", return_value=_mock_get(_DATA)) as mock_get:
            mallitiedot.hae_mallit()
            mallitiedot.hae_mallit()
        assert mock_get.call_count == 1

    def test_paivita_hakee_uudelleen(self):
        with patch.dict(os.environ, _ENV), \
             patch("llm.mallitiedot.requests.get", return_value=_mock_get(_DATA)) as mock_get:
            mallitiedot.hae_mallit()
            mallitiedot.hae_mallit(paivita=True)
        assert mock_get.call_count == 2

    def test_ilman_provideria_nostaa_virheen(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": ""}), pytest.raises(EnvironmentError):
            mallitiedot.hae_mallit()


class TestSaatavuus:
    def test_on_saatavilla_tunnistaa_loytyvan(self):
        with patch.dict(os.environ, _ENV), patch("llm.mallitiedot.requests.get", return_value=_mock_get(_DATA)):
            assert mallitiedot.on_saatavilla("openai/gpt-oss-120b:free") is True
            assert mallitiedot.on_saatavilla("ei/olemassa") is False

    def test_tarkista_saatavuus_lapaisee_kun_loytyy(self):
        with patch.dict(os.environ, _ENV), patch("llm.mallitiedot.requests.get", return_value=_mock_get(_DATA)):
            mallitiedot.tarkista_saatavuus()  # ei nosta virhettä

    def test_tarkista_saatavuus_nostaa_kun_ei_loydy(self):
        env = {**_ENV, "LLM_MODEL": "ei/olemassa"}
        with patch.dict(os.environ, env), patch("llm.mallitiedot.requests.get", return_value=_mock_get(_DATA)):
            with pytest.raises(RuntimeError):
                mallitiedot.tarkista_saatavuus()

    def test_tarkista_saatavuus_nostaa_kun_malli_puuttuu(self):
        env = {**_ENV, "LLM_MODEL": ""}
        with patch.dict(os.environ, env):
            with pytest.raises(EnvironmentError):
                mallitiedot.tarkista_saatavuus()
