"""Testit llm/erakutsu.py:lle — jaettu erän kutsu + uusintayritys."""
import json
from unittest.mock import patch
import pytest
from llm import erakutsu


def _jasenna(teksti):
    return json.loads(teksti)


def test_kysy_json_ok_ja_uusinta():
    with patch("llm.erakutsu.kutsu.kysy", return_value='[{"id": 1}]') as kysy:
        assert erakutsu.kysy_json("v", "j", "p", _jasenna, " OHJE") == ([{"id": 1}], "ok")
    assert kysy.call_count == 1
    # viallinen JSON tai tyhjä vastaus (kutsu nostaa ValueError) → yksi uusinta ohjeella
    for eka in ("ei jsonia", ValueError("LLM palautti tyhjän vastauksen")):
        with patch("llm.erakutsu.kutsu.kysy", side_effect=[eka, '[{"id": 2}]']) as kysy:
            assert erakutsu.kysy_json("v", "j", "p", _jasenna, " OHJE") == ([{"id": 2}], "uusinta")
        assert kysy.call_args.args[0] == "v OHJE"


def test_kysy_json_uusinnan_virhe_nousee():
    with patch("llm.erakutsu.kutsu.kysy", side_effect=["x", "y"]):
        with pytest.raises(json.JSONDecodeError):
            erakutsu.kysy_json("v", "j", "p", _jasenna, " OHJE")
