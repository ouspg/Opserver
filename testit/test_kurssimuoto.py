"""Testit llm/kurssimuoto.py:lle — kurssin kuvauksen muotoilu promptiin.

Keskeinen vaatimus (laadunvarmistus): kuvausta EI saa katkaista — mallin täytyy
saada käyttöönsä kaikki opinto-oppaassa näkyvä tieto.
"""
import json
from llm import kurssimuoto


class TestKuvausTekstina:
    def test_tyhja_kuvaus_palauttaa_tyhjan(self):
        assert kurssimuoto.kuvaus_tekstina(None) == ""
        assert kurssimuoto.kuvaus_tekstina("") == ""

    def test_jasentaa_contentlistin_otsikko_ja_sisalto(self):
        ops = json.dumps({"contentList": [
            {"title": {"valueFi": "Sisältö"}, "content": {"valueFi": "Kryptografian perusteet."}},
            {"title": {"valueFi": "Osaamistavoitteet"}, "content": {"valueFi": "Opiskelija osaa X."}},
        ]})
        teksti = kurssimuoto.kuvaus_tekstina(ops)
        assert "Sisältö: Kryptografian perusteet." in teksti
        assert "Osaamistavoitteet: Opiskelija osaa X." in teksti

    def test_sivuuttaa_tyhjat_osiot(self):
        ops = json.dumps({"contentList": [
            {"title": {"valueFi": "Sisältö"}, "content": {"valueFi": "Jotain."}},
            {"title": {"valueFi": "Tyhjä"}, "content": {"valueFi": "   "}},
        ]})
        teksti = kurssimuoto.kuvaus_tekstina(ops)
        assert "Tyhjä" not in teksti

    def test_ei_katkaise_pitkaa_kuvausta(self):
        """Kriittinen: koko kuvauksen täytyy päästä mallille (ei 800-merkin rajaa)."""
        pitka = "A" * 5000
        ops = json.dumps({"contentList": [
            {"title": {"valueFi": "Sisältö"}, "content": {"valueFi": pitka}},
        ]})
        teksti = kurssimuoto.kuvaus_tekstina(ops)
        assert pitka in teksti
        assert len(teksti) >= 5000

    def test_ei_json_palauttaa_raa_an_tekstin_kokonaan(self):
        raaka = "Ei JSON-muodossa. " + "B" * 2000
        assert kurssimuoto.kuvaus_tekstina(raaka) == raaka


class TestKurssiJsonPromptiin:
    def test_rakentaa_kentat_ja_taydellisen_kuvauksen(self):
        pitka = "C" * 3000
        ops = json.dumps({"contentList": [
            {"title": {"valueFi": "Sisältö"}, "content": {"valueFi": pitka}},
        ]})
        kurssi = {"KID": 42, "KurssiNimi": "Kyberturvallisuus", "Koodi": "TIE101",
                  "Taso": "perus", "Oppiaine": "Tietotekniikka", "OpsKuvaus": ops}
        tulos = kurssimuoto.kurssi_json_promptiin(kurssi)
        assert tulos["id"] == 42
        assert tulos["nimi"] == "Kyberturvallisuus"
        assert tulos["koodi"] == "TIE101"
        assert tulos["taso"] == "perus"
        assert tulos["oppiaine"] == "Tietotekniikka"
        assert pitka in tulos["kuvaus"]

    def test_puuttuvat_kentat_tyhjiksi(self):
        kurssi = {"KID": 1, "KurssiNimi": "X", "OpsKuvaus": None}
        tulos = kurssimuoto.kurssi_json_promptiin(kurssi)
        assert tulos["koodi"] == ""
        assert tulos["taso"] == ""
        assert tulos["oppiaine"] == ""
        assert tulos["kuvaus"] == ""
