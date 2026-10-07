"""Tietokantamallien testit: arviointien vastaukset ja ihmisten korjaukset (tietokanta/vastaukset.py)."""
from unittest.mock import patch
from tietokanta import mallit


class TestHaeArvioimattomat:
    """LLM-arvioinnin ehdokasjoukon täytyy noudattaa tutkimuksen rajausta —
    muuten vanhojen ajojen rajauksen ulkopuoliset hyväksynnät menisivät
    arviointiin (sama bugiluokka kuin hae_luokittelemattomat)."""

    def test_soveltaa_tutkimuksen_rajausta(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.fetchone.return_value = (0,)
        with patch("tietokanta.vastaukset._tutkimus_kurssi_scope",
                   return_value=("k.KKID IN (%s) AND vuosirajaus", [4, 2024, 2025])):
            mallit.laske_arvioimattomat(1)
        sql, params = kursori.execute.call_args[0]
        assert "k.KKID IN" in sql and "vuosirajaus" in sql
        # GROUP BY -aggregaatti, ei per-rivi korreloitua alikyselyä
        assert "GROUP BY" in sql
        # kaksi tid:tä (Kurssiluokitus- ja Kysymykset-JOIN), sitten rajausparametrit
        assert list(params) == [1, 1, 4, 2024, 2025]

    def test_laske_arvioimattomat_laskee_ei_hae_riveja(self, mock_yhteys):
        """Tilannesivu tarvitsee vain lukumäärän → COUNT(*), ei SELECT k.* (ei vedä
        OpsKuvaus-tekstejä verkon yli). Sama WHERE-ehto kuin rivihaussa."""
        yht, kursori = mock_yhteys
        kursori.fetchone.return_value = (7,)
        with patch("tietokanta.vastaukset._tutkimus_kurssi_scope",
                   return_value=("k.KKID IN (%s) AND vuosirajaus", [4, 2024, 2025])):
            tulos = mallit.laske_arvioimattomat(1)
        assert tulos == 7
        sql, params = kursori.execute.call_args[0]
        assert "SELECT COUNT(*)" in sql and "SELECT k.*" not in sql
        assert "GROUP BY" in sql
        assert list(params) == [1, 1, 4, 2024, 2025]


class TestHitlVastaukset:
    """Ihmisen korjaus menee samaan Vastaukset-tauluun kuin LLM:n vastaus
    (migraatio_022). Malli IS NULL erottaa rivit toisistaan."""

    def test_tallenna_hitl_vastaus_jattaa_mallin_nulliksi(self, mock_yhteys):
        yht, kursori = mock_yhteys
        mallit.tallenna_hitl_vastaus(1, 7, 30, "Perustelu", "Testi", "t@e.fi",
                                     luokka="Täysin", juurisyy="llm_virhe")
        sql, params = kursori.execute.call_args[0]
        assert "INSERT INTO Vastaukset" in sql
        assert "NULL, NULL" in sql          # Malli ja Kehotetiiviste
        assert "Aikaleima = CURRENT_TIMESTAMP" in sql
        assert params[:3] == (1, 30, 7)     # TID, KysID, KID
        assert "Testi" in params and "llm_virhe" in params

    def test_hae_hitl_vastaukset_rajaa_ihmisen_riveihin(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.fetchall.return_value = []
        kursori.description = []
        mallit.hae_hitl_vastaukset(1)
        sql = kursori.execute.call_args[0][0]
        assert "Malli IS NULL" in sql

    def test_vastaus_tiivisteet_hitl_voittaa_llm_rivin(self, mock_yhteys):
        """Samalla (KID, KysID) -parilla HITL-tila jää voimaan."""
        yht, kursori = mock_yhteys
        kursori.description = [("KID",), ("KysID",), ("Kehotetiiviste",), ("Hitl",), ("Vastattu",)]
        kursori.fetchall.return_value = [
            (5, 30, "tiiv", 0, 1),   # LLM-rivi ensin (ORDER BY)
            (5, 30, None, 1, 1),     # ihmisen korjaus kirjoittaa yli
        ]
        tulos = mallit.hae_vastaus_tiivisteet(1)
        assert tulos[(5, 30)]["hitl"] is True


class TestHitlRivitEivatSotkeLaskentaa:
    """LLM- ja HITL-rivi ovat samalla (KID, KysID) -parilla (migraatio_022);
    laskennat eivät saa laskea paria kahdesti eikä HITL-riviä LLM-riviksi."""

    def test_arvioimattomat_laskee_erilliset_kysymykset(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.fetchone.return_value = (0,)
        mallit.laske_arvioimattomat(1)
        sql, _ = kursori.execute.call_args[0]
        assert "COUNT(DISTINCT v.KysID) < COUNT(DISTINCT ky.KysID)" in sql

    def test_raakana_tallennetut_ohittaa_ihmisen_rivit(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.fetchall.return_value = []
        kursori.description = []
        mallit.hae_raakana_tallennetut_vastaukset(1)
        sql, _ = kursori.execute.call_args[0]
        assert "v.Malli IS NOT NULL" in sql

    def test_testiajon_siirto_asettaa_tidin(self, mock_yhteys):
        from tietokanta import testimallit
        yht, kursori = mock_yhteys
        kursori.fetchone.return_value = (3,)
        testimallit.siirra_testiajo_arviointi("ajo1")
        sql, _ = kursori.execute.call_args[0]
        assert "INSERT INTO Vastaukset\n                       (TID, KysID" in sql or "(TID, KysID" in sql
        assert "SELECT TID, KysID" in sql

    def test_testiajon_siirto_nollaa_hyvaksynnan(self, mock_yhteys):
        """Siirretty LLM-tulos ei saa periä vanhan tuloksen hyväksyntää (kuten aseta_*)."""
        from tietokanta import testimallit
        yht, kursori = mock_yhteys
        kursori.fetchone.return_value = (3,)
        testimallit.siirra_testiajo_arviointi("ajo1")
        assert "HyvaksyjaNimi = NULL" in kursori.execute.call_args[0][0]
        testimallit.siirra_testiajo_luokittelu("ajo1")
        assert "KayttajaNimi = NULL" in kursori.execute.call_args[0][0]

    def test_hae_vastaukset_oletuksena_kaikki_kurssit(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.fetchall.return_value = []
        kursori.description = []
        mallit.hae_vastaukset(1)
        sql, params = kursori.execute.call_args[0]
        assert "Kurssiluokitus" not in sql and list(params) == [1]

    def test_hae_vastaukset_vain_mukana_rajaa_sql_joinilla(self, mock_yhteys):
        """HITL:ssä pois käännetyn kurssin vanhat vastaukset eivät kuulu raportin
        tilastoihin — rajaus kannassa (JOIN), ei Pythonissa."""
        yht, kursori = mock_yhteys
        kursori.fetchall.return_value = []
        kursori.description = []
        mallit.hae_vastaukset(1, vain_mukana=True)
        sql, params = kursori.execute.call_args[0]
        assert "JOIN Kurssiluokitus kl" in sql
        assert "kl.TID = v.TID" in sql and "kl.Mukana = 1" in sql
        assert list(params) == [1]


class TestEpakanonisetLuokat:
    def test_hakee_vain_sallituista_poikkeavat_tavu_tarkasti(self, mock_yhteys):
        """Kannan oletuskollaatio (ai_ci) pitäisi 'ei lainkaan' = 'Ei lainkaan' → vertailu binäärinä."""
        yht, kursori = mock_yhteys
        kursori.fetchall.return_value = []
        kursori.description = []
        mallit.hae_epakanoniset_luokat(1, {10: ["Täysin", "Ei lainkaan"], 11: ["A"]})
        sql, params = kursori.execute.call_args[0]
        assert "COLLATE utf8mb4_bin NOT IN" in sql
        assert "Luokka IS NOT NULL" in sql and "Luokka <> ''" in sql
        assert list(params) == [1, 10, "Täysin", "Ei lainkaan", 11, "A"]

    def test_ei_kyselya_ilman_luokittelukysymyksia(self, mock_yhteys):
        yht, kursori = mock_yhteys
        assert mallit.hae_epakanoniset_luokat(1, {}) == []
        kursori.execute.assert_not_called()

    def test_paivita_luokat_vasid_lla(self, mock_yhteys):
        yht, kursori = mock_yhteys
        mallit.paivita_luokat([("Ei lainkaan", 7), ("Täysin", 8)])
        sql, rivit = kursori.executemany.call_args[0]
        assert sql.startswith("UPDATE Vastaukset SET Luokka = %s WHERE VasID = %s")
        assert rivit == [("Ei lainkaan", 7), ("Täysin", 8)]
