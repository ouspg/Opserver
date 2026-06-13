"""Testit arviointi-moduulille."""
from unittest.mock import patch, MagicMock, call
import pytest
from arviointi import llmarviointi


LLM_VASTAUS = '{"tulokset": [{"id": 1, "vastaukset": ["Kyllä", "Ei"]}, {"id": 2, "vastaukset": ["Ei", "Kyllä"]}]}'

KYSYMYKSET = [
    {"KysID": 10, "TID": 1, "Kysymys": "Liittyykö kurssi kyberturvallisuuteen?"},
    {"KysID": 11, "TID": 1, "Kysymys": "Soveltuuko kurssi ESR-hankkeeseen?"},
]

KURSSIT = [
    {"KID": 1, "KurssiNimi": "Tietoturva", "Koodi": "CS100", "Taso": "aine",
     "Oppiaine": "Tietotekniikka", "Opintopisteet": "5", "Opetusvuosi": "2025-2026", "OpsKuvaus": None},
    {"KID": 2, "KurssiNimi": "Verkot", "Koodi": "CS200", "Taso": "aine",
     "Oppiaine": "Tietotekniikka", "Opintopisteet": "5", "Opetusvuosi": "2025-2026", "OpsKuvaus": None},
]

TUTKIMUS = {"TID": 1, "LuokittelunNimi": "Testi", "Arviointikehote": "Arvioi kyberturvallisuusrelevanssi."}


class TestErittelleJson:
    def test_erittele_json_puhdas(self):
        tulos = llmarviointi._erittele_json(LLM_VASTAUS)
        assert len(tulos) == 2
        assert tulos[0]["id"] == 1
        assert tulos[0]["vastaukset"] == ["Kyllä", "Ei"]

    def test_erittele_json_ylimaaraisella_tekstilla(self):
        vastaus = f"Tässä on arviointini:\n```json\n{LLM_VASTAUS}\n```"
        tulos = llmarviointi._erittele_json(vastaus)
        assert len(tulos) == 2

    def test_erittele_json_erilaisella_avaimella(self):
        vastaus = '{"items": [{"id": 42, "vastaukset": ["Kyllä"]}]}'
        tulos = llmarviointi._erittele_json(vastaus)
        assert tulos[0]["id"] == 42

    def test_erittele_json_virheellinen_nostaa_poikkeuksen(self):
        with pytest.raises((ValueError, KeyError)):
            llmarviointi._erittele_json('{"ei_listaa": "tekstiä"}')


class TestAja:
    def test_aja_kirjoittaa_vastaukset(self):
        with patch("arviointi.llmarviointi.mallit.hae_arvioimattomat", return_value=KURSSIT), \
             patch("arviointi.llmarviointi.mallit.hae_kysymykset", return_value=KYSYMYKSET), \
             patch("arviointi.llmarviointi.kutsu.kysy", return_value=LLM_VASTAUS), \
             patch("arviointi.llmarviointi.kutsu.hae_malli", return_value="testimalli"), \
             patch("arviointi.llmarviointi.mallit.aseta_vastaus") as mock_aseta, \
             patch("arviointi.llmarviointi._lue_jarjestelma_kehote", return_value="system"):
            arvioitu = llmarviointi.aja(TUTKIMUS)

        assert arvioitu == 2
        # 2 kurssit × 2 kysymystä = 4 aseta_vastaus-kutsua
        assert mock_aseta.call_count == 4
        # Tarkista kutsut kurssi 1:lle (sisältää nyt mallinimi neljäntenä argumenttina)
        mock_aseta.assert_any_call(10, 1, "Kyllä", "testimalli")
        mock_aseta.assert_any_call(11, 1, "Ei", "testimalli")
        mock_aseta.assert_any_call(10, 2, "Ei", "testimalli")
        mock_aseta.assert_any_call(11, 2, "Kyllä", "testimalli")

    def test_aja_ilman_kysymyksia_palauttaa_nollan(self):
        with patch("arviointi.llmarviointi.mallit.hae_kysymykset", return_value=[]), \
             patch("arviointi.llmarviointi.mallit.hae_arvioimattomat", return_value=KURSSIT), \
             patch("arviointi.llmarviointi.kutsu.kysy") as mock_kysy:
            arvioitu = llmarviointi.aja(TUTKIMUS)
        assert arvioitu == 0
        mock_kysy.assert_not_called()

    def test_aja_ilman_arvioimattomia_palauttaa_nollan(self):
        with patch("arviointi.llmarviointi.mallit.hae_kysymykset", return_value=KYSYMYKSET), \
             patch("arviointi.llmarviointi.mallit.hae_arvioimattomat", return_value=[]), \
             patch("arviointi.llmarviointi.kutsu.kysy") as mock_kysy:
            arvioitu = llmarviointi.aja(TUTKIMUS)
        assert arvioitu == 0
        mock_kysy.assert_not_called()

    def test_aja_kutsuu_kysy_json_muodolla(self):
        with patch("arviointi.llmarviointi.mallit.hae_arvioimattomat", return_value=KURSSIT[:1]), \
             patch("arviointi.llmarviointi.mallit.hae_kysymykset", return_value=KYSYMYKSET), \
             patch("arviointi.llmarviointi.kutsu.kysy", return_value=LLM_VASTAUS) as mock_kysy, \
             patch("arviointi.llmarviointi.mallit.aseta_vastaus"), \
             patch("arviointi.llmarviointi._lue_jarjestelma_kehote", return_value="system"):
            llmarviointi.aja(TUTKIMUS)
        _, kwargs = mock_kysy.call_args
        assert kwargs.get("json_muoto") is True

    def test_aja_kutsuu_edistyminen_cb(self):
        tapahtumat = []
        def edistyminen(n, yht, erä, erat):
            tapahtumat.append((n, yht, erä, erat))

        with patch("arviointi.llmarviointi.mallit.hae_arvioimattomat", return_value=KURSSIT), \
             patch("arviointi.llmarviointi.mallit.hae_kysymykset", return_value=KYSYMYKSET), \
             patch("arviointi.llmarviointi.kutsu.kysy", return_value=LLM_VASTAUS), \
             patch("arviointi.llmarviointi.mallit.aseta_vastaus"), \
             patch("arviointi.llmarviointi._lue_jarjestelma_kehote", return_value="system"):
            llmarviointi.aja(TUTKIMUS, edistyminen)

        assert len(tapahtumat) == 1
        assert tapahtumat[0] == (2, 2, 1, 1)
