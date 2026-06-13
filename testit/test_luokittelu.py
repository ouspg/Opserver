"""Testit luokittelu-moduulille."""
from unittest.mock import patch, MagicMock
import pytest
from luokittelu import metasuodatus, llmluokittelu


# --- metasuodatus ---

class TestMetasuodatus:
    KURSSIT = [
        {"KID": 1, "KurssiNimi": "Ohjelmointi 1", "Taso": "perus", "Oppiaine": "Tietotekniikka"},
        {"KID": 2, "KurssiNimi": "Kvanttimekaniikka", "Taso": "aine", "Oppiaine": "Fysiikka"},
        {"KID": 3, "KurssiNimi": "Tietoverkot", "Taso": "aine", "Oppiaine": "Tietotekniikka"},
    ]
    TUTKIMUS = {"TID": 1, "LuokittelunNimi": "Testi", "Tasorajaus": "aine", "Oppiainerajaus": "Tietotekniikka"}

    def test_taso_suodatus(self):
        assert metasuodatus._taso_ok({"Taso": "aine"}, "perus,aine") is True
        assert metasuodatus._taso_ok({"Taso": "yleis"}, "perus,aine") is False
        assert metasuodatus._taso_ok({"Taso": "aine"}, None) is True

    def test_oppiaine_suodatus(self):
        assert metasuodatus._oppiaine_ok({"Oppiaine": "Tietotekniikka"}, "Tieto") is True
        assert metasuodatus._oppiaine_ok({"Oppiaine": "Fysiikka"}, "Tieto") is False
        assert metasuodatus._oppiaine_ok({"Oppiaine": "Fysiikka"}, None) is True
        assert metasuodatus._oppiaine_ok({"Oppiaine": "Fysiikka"}, "Tieto,Fysi") is True
        assert metasuodatus._oppiaine_ok({"Oppiaine": "Matematiikka"}, "Tieto,Fysi") is False

    def test_aja_kirjoittaa_hyvaksytyt_ja_hylatyt(self):
        with patch("luokittelu.metasuodatus.mallit.hae_kurssit", return_value=self.KURSSIT), \
             patch("luokittelu.metasuodatus.mallit.aseta_luokitus") as mock_aseta:
            lapaisseet, yht = metasuodatus.aja(self.TUTKIMUS)
        assert yht == 3
        assert lapaisseet == 1  # vain Tietoverkot läpäisee molemmat
        assert mock_aseta.call_count == 3  # kaikki 3 kurssia kirjataan (1 mukana + 2 hylätty)
        # Tietoverkot (KID=3) kirjataan hyväksyttynä
        mock_aseta.assert_any_call(1, 3, True, "meta: läpäissyt")

    def test_aja_ilman_rajausta_kaikki_hyvaksytaan(self):
        tutkimus = {"TID": 1, "Tasorajaus": None, "Oppiainerajaus": None}
        with patch("luokittelu.metasuodatus.mallit.hae_kurssit", return_value=self.KURSSIT), \
             patch("luokittelu.metasuodatus.mallit.aseta_luokitus") as mock_aseta:
            lapaisseet, yht = metasuodatus.aja(tutkimus)
        assert lapaisseet == yht == 3
        assert mock_aseta.call_count == 3  # kaikki kirjataan Mukana=True
        for call in mock_aseta.call_args_list:
            assert call.args[2] is True


# --- llmluokittelu ---

class TestLlmluokittelu:
    LLM_VASTAUS = '[{"id": 1, "mukana": true, "perustelu": "Relevantti"}, {"id": 2, "mukana": false, "perustelu": "Ei sovellu"}]'

    def test_erittele_json_puhdas(self):
        tulos = llmluokittelu._erittele_json(self.LLM_VASTAUS)
        assert len(tulos) == 2
        assert tulos[0]["mukana"] is True

    def test_erittele_json_ylimaaraisella_tekstilla(self):
        vastaus = f"Tässä on arviointini:\n```json\n{self.LLM_VASTAUS}\n```"
        tulos = llmluokittelu._erittele_json(vastaus)
        assert len(tulos) == 2

    def test_aja_kirjoittaa_luokitukset(self):
        kandidaatit = [
            {"KID": 1, "KurssiNimi": "A", "Koodi": "X1", "Taso": "aine",
             "Oppiaine": "IT", "Opintopisteet": 5, "Opetusvuosi": "2025-2026", "OpsKuvaus": None},
            {"KID": 2, "KurssiNimi": "B", "Koodi": "X2", "Taso": "perus",
             "Oppiaine": "FY", "Opintopisteet": 3, "Opetusvuosi": "2025-2026", "OpsKuvaus": None},
        ]
        tutkimus = {"TID": 1, "Luokittelukehote": "Arvioi kyberturvallisuusrelevanssi."}
        with patch("luokittelu.llmluokittelu.mallit.hae_luokittelemattomat", return_value=kandidaatit), \
             patch("luokittelu.llmluokittelu.kutsu.kysy", return_value=self.LLM_VASTAUS), \
             patch("luokittelu.llmluokittelu.mallit.aseta_luokitus") as mock_aseta, \
             patch("luokittelu.llmluokittelu._lue_jarjestelma_kehote", return_value="system"):
            mukana, hylätty = llmluokittelu.aja(tutkimus)
        assert mukana == 1
        assert hylätty == 1
        assert mock_aseta.call_count == 2
