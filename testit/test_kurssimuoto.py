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

    def test_jasentaa_sisu_kori_rakenteen(self):
        """Sisu (KORI) course-unit: tekstikentät monikielisinä, HTML riisuttuna."""
        ops = json.dumps({
            "code": "TIES001",
            "outcomes": {"fi": "<p>Opiskelija osaa kryptografian perusteet.</p>"},
            "content": {"fi": "Symmetrinen ja epäsymmetrinen salaus."},
            "prerequisites": {"fi": ""},
            "tweetText": {"fi": "Johdatus salaukseen"},
        })
        teksti = kurssimuoto.kuvaus_tekstina(ops)
        assert "Osaamistavoitteet: Opiskelija osaa kryptografian perusteet." in teksti
        assert "Sisältö: Symmetrinen ja epäsymmetrinen salaus." in teksti
        assert "Tiivistelmä: Johdatus salaukseen" in teksti
        assert "<p>" not in teksti          # HTML riisuttu
        assert "Esitiedot" not in teksti    # tyhjä kenttä jätetään pois

    def test_sisu_kayttaa_englantia_jos_suomi_puuttuu(self):
        ops = json.dumps({"content": {"en": "Basics of cryptography."}})
        assert "Sisältö: Basics of cryptography." in kurssimuoto.kuvaus_tekstina(ops)

    def test_sisu_ilman_tekstikenttia_palauttaa_tyhjan(self):
        # Aidosti kuvaukseton Sisu-kurssi (riittämätön opinto-opas) → tyhjä, ei raaka JSON
        ops = json.dumps({"code": "X", "credits": {"min": 5}, "outcomes": None})
        assert kurssimuoto.kuvaus_tekstina(ops) == ""

    def test_sisu_lisaa_suoritustavat(self):
        """completionMethods (jo tallennettu KORI-data) → 'Suoritustavat'-osio."""
        ops = json.dumps({
            "content": {"fi": "Salausoppi."},
            "completionMethods": [{
                "studyType": "DEGREE_STUDIES",
                "description": {"fi": "<p>Luento-opetus ja lopputentti.</p>"},
                "evaluationCriteria": {"fi": "Hyväksytty edellyttää 50 % pisteistä."},
            }],
        })
        teksti = kurssimuoto.kuvaus_tekstina(ops)
        assert "Suoritustavat:" in teksti
        assert "Luento-opetus ja lopputentti." in teksti
        assert "Arviointi: Hyväksytty edellyttää 50 % pisteistä." in teksti
        assert "<p>" not in teksti  # HTML riisuttu

    def test_sisu_merkitsee_avoimen_yliopiston_suoritustavan(self):
        """studyType=OPEN_UNIVERSITY_STUDIES → eksplisiittinen avoimen yo:n merkintä (ESR-signaali)."""
        ops = json.dumps({
            "completionMethods": [{
                "studyType": "OPEN_UNIVERSITY_STUDIES",
                "description": {"fi": "Verkkokurssi, jatkuva ilmoittautuminen."},
            }],
        })
        teksti = kurssimuoto.kuvaus_tekstina(ops)
        assert "Avoimen yliopiston suoritustapa: kyllä" in teksti
        assert "avoin yliopisto" in teksti

    def test_sisu_tutkintokurssi_ei_merkitse_avointa_yliopistoa(self):
        ops = json.dumps({
            "completionMethods": [{
                "studyType": "DEGREE_STUDIES",
                "description": {"fi": "Luento-opetus."},
            }],
        })
        teksti = kurssimuoto.kuvaus_tekstina(ops)
        assert "Avoimen yliopiston suoritustapa" not in teksti

    def test_sisu_sivuuttaa_tekstittomat_suoritustavat(self):
        """Suoritustapa ilman kuvausta/kriteereitä ei tuota tyhjää 'Suoritustavat'-osiota..."""
        ops = json.dumps({
            "content": {"fi": "Salausoppi."},
            "completionMethods": [{"studyType": "DEGREE_STUDIES", "description": {"fi": ""}}],
        })
        teksti = kurssimuoto.kuvaus_tekstina(ops)
        assert "Suoritustavat:" not in teksti

    def test_sisu_avoin_yliopisto_merkitaan_vaikka_kuvaus_puuttuu(self):
        """...mutta avoimen yo:n signaali säilyy, vaikka kuvausteksti puuttuisi."""
        ops = json.dumps({
            "content": {"fi": "Salausoppi."},
            "completionMethods": [{"studyType": "OPEN_UNIVERSITY_STUDIES", "description": {"fi": ""}}],
        })
        teksti = kurssimuoto.kuvaus_tekstina(ops)
        assert "Avoimen yliopiston suoritustapa: kyllä" in teksti


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
