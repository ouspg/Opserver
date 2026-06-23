"""Testit luokittelu-moduulille."""
from unittest.mock import patch, MagicMock
import pytest
from luokittelu import metasuodatus, llmluokittelu


# --- metasuodatus ---

class TestMetasuodatus:
    KURSSIT = [
        {"KID": 1, "KKID": 1, "KurssiNimi": "Ohjelmointi 1", "Taso": "perus", "Oppiaine": "Tietotekniikka", "Opetusvuosi": "2025-2026"},
        {"KID": 2, "KKID": 1, "KurssiNimi": "Kvanttimekaniikka", "Taso": "aine", "Oppiaine": "Fysiikka", "Opetusvuosi": "2025-2026"},
        {"KID": 3, "KKID": 1, "KurssiNimi": "Tietoverkot", "Taso": "aine", "Oppiaine": "Tietotekniikka", "Opetusvuosi": "2025-2026"},
    ]
    TUTKIMUS = {"TID": 1, "LuokittelunNimi": "Testi", "Lukuvuosi": "2025-2026",
                "Tasorajaus": "aine", "Oppiainerajaus": "Tietotekniikka"}

    def _aja(self, tutkimus, kurssit, jo_luokitellut, korkeakoulut=(1,), kohde="uudet"):
        with patch("luokittelu.metasuodatus.mallit.hae_kurssit", return_value=kurssit), \
             patch("luokittelu.metasuodatus.mallit.hae_luokitukset", return_value=jo_luokitellut), \
             patch("luokittelu.metasuodatus.mallit.hae_tutkimuksen_korkeakoulut", return_value=list(korkeakoulut)), \
             patch("luokittelu.metasuodatus.mallit.aseta_luokitus") as mock_aseta:
            tulos = metasuodatus.aja(tutkimus, kohde=kohde)
        return tulos, mock_aseta

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

    def test_aja_kirjoittaa_kaikki_kurssit(self):
        (lapaisseet, yht), mock_aseta = self._aja(self.TUTKIMUS, self.KURSSIT, [])
        assert yht == 3
        assert lapaisseet == 1  # vain Tietoverkot läpäisee taso+oppiaine
        assert mock_aseta.call_count == 3  # kaikki 3 kirjataan
        # Tietoverkot (KID=3) → Odottaa (NULL), muut → Hylätty (False)
        mock_aseta.assert_any_call(1, 3, None, "meta: odottaa LLM-seulontaa")
        mock_aseta.assert_any_call(1, 1, False, mock_aseta.call_args_list[0].args[3])
        mock_aseta.assert_any_call(1, 2, False, mock_aseta.call_args_list[1].args[3])

    def test_aja_ilman_taso_oppiainerajausta_kaikki_odottavat(self):
        tutkimus = {"TID": 1, "Lukuvuosi": "2025-2026", "Tasorajaus": None, "Oppiainerajaus": None}
        (lapaisseet, yht), mock_aseta = self._aja(tutkimus, self.KURSSIT, [])
        assert lapaisseet == yht == 3
        assert mock_aseta.call_count == 3  # kaikki kirjataan Mukana=NULL (Odottaa)
        for call in mock_aseta.call_args_list:
            assert call.args[2] is None

    def test_aja_ohittaa_jo_luokitellut(self):
        jo_luokitellut = [{"KID": 1}, {"KID": 2}]
        (lapaisseet, yht), mock_aseta = self._aja(self.TUTKIMUS, self.KURSSIT, jo_luokitellut)
        assert yht == 1  # vain KID=3 käsitellään
        assert lapaisseet == 1
        mock_aseta.assert_called_once_with(1, 3, None, "meta: odottaa LLM-seulontaa")

    def test_aja_kohde_kaikki_ylikirjoittaa(self):
        jo_luokitellut = [{"KID": 1}, {"KID": 2}]
        (lapaisseet, yht), mock_aseta = self._aja(self.TUTKIMUS, self.KURSSIT, jo_luokitellut, kohde="kaikki")
        assert yht == 3  # kaikki 3 käsitellään olemassaolosta huolimatta
        assert mock_aseta.call_count == 3

    def test_aja_kohde_hylatyt_vain_metahylatyt(self):
        jo_luokitellut = [
            {"KID": 1, "Mukana": 0, "Luokitteluperuste": "meta: oppiaine ei täsmää"},  # meta-hylätty
            {"KID": 2, "Mukana": None, "Luokitteluperuste": "meta: odottaa LLM-seulontaa"},  # meta-läpäissyt
            {"KID": 3, "Mukana": 0, "Luokitteluperuste": "LLM: ei liity"},  # LLM-hylätty (ei kohde)
        ]
        (lapaisseet, yht), mock_aseta = self._aja(self.TUTKIMUS, self.KURSSIT, jo_luokitellut, kohde="hylatyt")
        assert yht == 1  # vain KID=1 (meta-hylätty) käsitellään uudelleen
        assert mock_aseta.call_args_list[0].args[1] == 1

    def test_aja_kohde_hyvaksytyt_vain_metalapaiseet(self):
        jo_luokitellut = [
            {"KID": 1, "Mukana": 0, "Luokitteluperuste": "meta: oppiaine ei täsmää"},
            {"KID": 2, "Mukana": None, "Luokitteluperuste": "meta: odottaa LLM-seulontaa"},
            {"KID": 3, "Mukana": 1, "Luokitteluperuste": "LLM: relevantti"},  # hyväksytty LLM (ei kohde)
        ]
        (lapaisseet, yht), mock_aseta = self._aja(self.TUTKIMUS, self.KURSSIT, jo_luokitellut, kohde="hyvaksytyt")
        assert yht == 1  # vain KID=2 (meta-läpäissyt) käsitellään uudelleen
        assert mock_aseta.call_args_list[0].args[1] == 2

    def test_aja_rajaa_valittuihin_korkeakouluihin(self):
        kurssit = self.KURSSIT + [
            {"KID": 4, "KKID": 2, "KurssiNimi": "Toinen koulu", "Taso": "aine",
             "Oppiaine": "Tietotekniikka", "Opetusvuosi": "2025-2026"},
        ]
        (lapaisseet, yht), mock_aseta = self._aja(self.TUTKIMUS, kurssit, [], korkeakoulut=(1,))
        assert yht == 3  # KKID=2 jää kokonaan käsittelyn ulkopuolelle
        for call in mock_aseta.call_args_list:
            assert call.args[1] != 4

    def test_aja_ohittaa_lukuvuoden_ulkopuoliset_kokonaan(self):
        # Lukuvuosi on kova rajaus: väärän vuoden kurssia ei luokitella lainkaan
        # (ei edes Hylätty), koska vuosi ei voi olla "väärin" kuten taso/oppiaine.
        kurssit = [
            {"KID": 1, "KKID": 1, "KurssiNimi": "Vanha", "Taso": "aine",
             "Oppiaine": "Tietotekniikka", "Opetusvuosi": "2023-2024"},
            {"KID": 2, "KKID": 1, "KurssiNimi": "Nykyinen", "Taso": "aine",
             "Oppiaine": "Tietotekniikka", "Opetusvuosi": "2025-2026"},
        ]
        (lapaisseet, yht), mock_aseta = self._aja(self.TUTKIMUS, kurssit, [])
        assert yht == 1  # vain 2025-2026 on ehdokas; 2023-2024 jää kokonaan pois
        assert lapaisseet == 1
        mock_aseta.assert_called_once_with(1, 2, None, "meta: odottaa LLM-seulontaa")
        # KID=1 (väärä vuosi) ei saa luokitusta lainkaan
        assert all(c.args[1] != 1 for c in mock_aseta.call_args_list)

    def test_aja_vaatii_lukuvuoden_ja_korkeakoulut(self):
        with pytest.raises(ValueError):
            self._aja({"TID": 1, "Lukuvuosi": None}, self.KURSSIT, [], korkeakoulut=(1,))
        with pytest.raises(ValueError):
            self._aja(self.TUTKIMUS, self.KURSSIT, [], korkeakoulut=())


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
        with patch("luokittelu.llmluokittelu.mallit.hae_luokittelemattomat", return_value=kandidaatit) as mock_hae, \
             patch("luokittelu.llmluokittelu.kutsu.kysy", return_value=self.LLM_VASTAUS), \
             patch("luokittelu.llmluokittelu.mallit.aseta_luokitus") as mock_aseta, \
             patch("luokittelu.llmluokittelu._lue_jarjestelma_kehote", return_value="system"):
            mukana, hylätty, virheet = llmluokittelu.aja(tutkimus)
        assert mukana == 1
        assert hylätty == 1
        assert virheet == 0
        assert mock_aseta.call_count == 2
        # Kandidaatit haetaan tiivisteellä, jotta vanhentunut kehote ajetaan uudelleen
        tiiv = mock_hae.call_args.args[1]
        assert tiiv and len(tiiv) == 64
        # Tulokset tallennetaan samalla tiivisteellä
        for c in mock_aseta.call_args_list:
            assert c.kwargs["tiiviste"] == tiiv

    def test_aja_tyhja_kehote_hyvaksyy_meta_ilman_llm(self):
        """Tyhjä valintakehote → kaikki meta-läpäisseet mukaan ilman LLM-kutsuja."""
        kandidaatit = [
            {"KID": 1, "KurssiNimi": "A", "OpsKuvaus": None},
            {"KID": 2, "KurssiNimi": "B", "OpsKuvaus": None},
        ]
        tutkimus = {"TID": 1, "Luokittelukehote": "   "}  # tyhjä/whitespace
        with patch("luokittelu.llmluokittelu.mallit.hae_luokittelemattomat", return_value=kandidaatit), \
             patch("luokittelu.llmluokittelu.kutsu.kysy") as mock_kysy, \
             patch("luokittelu.llmluokittelu.mallit.aseta_luokitus") as mock_aseta, \
             patch("luokittelu.llmluokittelu._lue_jarjestelma_kehote", return_value="system"):
            mukana, hylätty, virheet = llmluokittelu.aja(tutkimus)
        assert (mukana, hylätty, virheet) == (2, 0, 0)
        assert mock_kysy.call_count == 0                  # ei LLM-kutsuja
        assert mock_aseta.call_count == 2
        assert all(c.args[2] is True for c in mock_aseta.call_args_list)  # kaikki mukaan

    def test_aja_viallinen_era_ei_kaada_ajoa(self):
        """Katkennut/viallinen LLM-JSON ohitetaan: virhe lasketaan, ajo jatkuu."""
        kandidaatit = [
            {"KID": 1, "KurssiNimi": "A", "Koodi": "X1", "Taso": "aine",
             "Oppiaine": "IT", "Opetusvuosi": "2025-2026", "OpsKuvaus": None},
        ]
        tutkimus = {"TID": 1, "Luokittelukehote": "Arvioi."}
        with patch("luokittelu.llmluokittelu.mallit.hae_luokittelemattomat", return_value=kandidaatit), \
             patch("luokittelu.llmluokittelu.kutsu.kysy", return_value="ei kelvollista jsonia"), \
             patch("luokittelu.llmluokittelu.mallit.aseta_luokitus") as mock_aseta, \
             patch("luokittelu.llmluokittelu._lue_jarjestelma_kehote", return_value="system"):
            mukana, hylätty, virheet = llmluokittelu.aja(tutkimus)
        assert (mukana, hylätty) == (0, 0)
        assert virheet == 1
        assert mock_aseta.call_count == 0

    def test_aja_tiiviste_muuttuu_kehotteesta(self):
        from llm import tiiviste
        t1 = llmluokittelu.tiiviste.luokittelu("kehote A", "system")
        t2 = llmluokittelu.tiiviste.luokittelu("kehote B", "system")
        assert t1 != t2 == tiiviste.luokittelu("kehote B", "system")
