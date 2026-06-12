"""Testit llm-kääreelle."""
import os
from unittest.mock import patch, MagicMock
import pytest
from llm import kutsu


_ENV = {
    "LLM_PROVIDER": "https://openrouter.ai/api/v1",
    "LLM_API_KEY": "testiavain",
    "LLM_MODEL": "testimalli",
}


class TestKysy:
    @pytest.fixture(autouse=True)
    def uni(self):
        """Nollaa viivetila ja korvaa time.sleep mockilla joka testissä."""
        kutsu._viive_s = kutsu._ALKUVIIVE_S
        with patch("llm.kutsu.time.sleep") as mock_uni:
            yield mock_uni

    def _mock_vastaus(self, teksti):
        vastaus = MagicMock()
        vastaus.status_code = 200
        vastaus.json.return_value = {"choices": [{"message": {"content": teksti}}]}
        return vastaus

    def _mock_429(self):
        vastaus = MagicMock()
        vastaus.status_code = 429
        return vastaus

    def test_kysy_lahettaa_openai_muotoisen_pyynnon(self):
        with patch.dict(os.environ, _ENV), \
             patch("llm.kutsu.requests.post", return_value=self._mock_vastaus("vastausteksti")) as mock_post:
            tulos = kutsu.kysy("kysymys", jarjestelma="ohje")
        assert tulos == "vastausteksti"
        args, kwargs = mock_post.call_args
        assert args[0] == "https://openrouter.ai/api/v1/chat/completions"
        assert kwargs["headers"]["Authorization"] == "Bearer testiavain"
        assert kwargs["json"]["model"] == "testimalli"
        assert kwargs["json"]["messages"] == [
            {"role": "system", "content": "ohje"},
            {"role": "user", "content": "kysymys"},
        ]

    def test_kysy_kayttaa_oletusjarjestelmakehotetta(self):
        with patch.dict(os.environ, _ENV), \
             patch("llm.kutsu.requests.post", return_value=self._mock_vastaus("ok")) as mock_post:
            kutsu.kysy("kysymys")
        jarjestelma = mock_post.call_args.kwargs["json"]["messages"][0]
        assert jarjestelma["role"] == "system"
        assert jarjestelma["content"]  # ei tyhjä

    def test_kysy_vaatii_konfiguraation(self):
        tyhja = {avain: "" for avain in _ENV}
        with patch.dict(os.environ, tyhja), pytest.raises(EnvironmentError):
            kutsu.kysy("kysymys")

    # --- slow start -viivesäätö ---

    def test_onnistuminen_puolittaa_viiveen(self, uni):
        kutsu._viive_s = 4.0
        with patch.dict(os.environ, _ENV), \
             patch("llm.kutsu.requests.post", return_value=self._mock_vastaus("ok")):
            kutsu.kysy("kysymys")
        uni.assert_called_once_with(4.0)
        assert kutsu._viive_s == 2.0

    def test_429_tuplaa_viiveen_ja_yrittaa_uudelleen(self, uni):
        kutsu._viive_s = 1.0
        vastaukset = [self._mock_429(), self._mock_429(), self._mock_vastaus("ok")]
        with patch.dict(os.environ, _ENV), \
             patch("llm.kutsu.requests.post", side_effect=vastaukset) as mock_post:
            tulos = kutsu.kysy("kysymys")
        assert tulos == "ok"
        assert mock_post.call_count == 3
        # viive: 1.0 -> 2.0 -> 4.0 (kaksi 429:ää), onnistuminen puolittaa -> 2.0
        assert [k.args[0] for k in uni.call_args_list] == [1.0, 2.0, 4.0]
        assert kutsu._viive_s == 2.0

    def test_429_kasvattaa_viiveen_nollasta_alkuviiveeseen(self, uni):
        kutsu._viive_s = 0.0
        vastaukset = [self._mock_429(), self._mock_vastaus("ok")]
        with patch.dict(os.environ, _ENV), \
             patch("llm.kutsu.requests.post", side_effect=vastaukset):
            kutsu.kysy("kysymys")
        assert kutsu._viive_s == kutsu._ALKUVIIVE_S / 2

    def test_viive_ei_ylita_maksimia(self, uni):
        kutsu._viive_s = kutsu._MAKSIMIVIIVE_S
        vastaukset = [self._mock_429(), self._mock_vastaus("ok")]
        with patch.dict(os.environ, _ENV), \
             patch("llm.kutsu.requests.post", side_effect=vastaukset):
            kutsu.kysy("kysymys")
        assert kutsu._viive_s == kutsu._MAKSIMIVIIVE_S / 2

    def test_liian_monta_429_nostaa_virheen(self, uni):
        with patch.dict(os.environ, _ENV), \
             patch("llm.kutsu.requests.post", return_value=self._mock_429()) as mock_post:
            with pytest.raises(RuntimeError):
                kutsu.kysy("kysymys")
        assert mock_post.call_count == kutsu._MAX_YRITYKSET
