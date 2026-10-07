"""Tietokantamallien testit: raporttiosiot, tuoreus, tilastot (tietokanta/raportti.py)."""
from unittest.mock import MagicMock
from tietokanta import mallit
from tietokanta import raportti as tk_raportti


class TestRaporttiTuoreus:
    """Raportin tuoreussignatuuri tallennetaan/luetaan halvalla — raskas
    tiivistelaskenta tehdään erikseen taustalla."""

    def test_hae_palauttaa_none_kun_ei_riviä(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.description = None
        assert mallit.hae_raportti_tuoreus(1) is None

    def test_hae_palauttaa_signatuurin_ja_ajan(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.description = [("Signatuuri",), ("Tarkistettu",)]
        kursori.fetchone.return_value = ("abc123", "2026-07-15 10:00:00")
        tulos = mallit.hae_raportti_tuoreus(1)
        assert tulos == {"Signatuuri": "abc123", "Tarkistettu": "2026-07-15 10:00:00"}
        sql, params = kursori.execute.call_args[0]
        assert "RaporttiTuoreus" in sql and list(params) == [1]

    def test_tallenna_upsertoi_signatuurin(self, mock_yhteys):
        yht, kursori = mock_yhteys
        mallit.tallenna_raportti_tuoreus(3, "sig")
        sql, params = kursori.execute.call_args[0]
        assert "INSERT" in sql.upper() and "ON DUPLICATE KEY UPDATE" in sql.upper()
        assert "RaporttiTuoreus" in sql
        assert list(params) == [3, "sig"]


class TestRaporttiTila:
    def test_aseta_raportti_osio_kirjoittaa_tiivisteen(self, mock_yhteys):
        yht, kursori = mock_yhteys
        mallit.aseta_raportti_osio(1, "johdanto", "teksti", laskentatiiviste="abc123")
        sql, params = kursori.execute.call_args[0]
        assert "Laskentatiiviste" in sql
        assert params == (1, "johdanto", "teksti", "abc123")

    def test_aseta_raportti_osio_sailyttaa_tiivisteen_kun_none(self, mock_yhteys):
        """WebUI-tekstimuokkaus (ilman tiivistettä) ei saa nollata Laskentatiivistettä."""
        yht, kursori = mock_yhteys
        mallit.aseta_raportti_osio(1, "johdanto", "muokattu")
        sql, params = kursori.execute.call_args[0]
        assert "COALESCE(VALUES(Laskentatiiviste), Laskentatiiviste)" in sql
        assert params == (1, "johdanto", "muokattu", None)

    def test_hae_raportti_tila_palauttaa_aikaleimat_ja_tiivisteen(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.fetchall.return_value = [
            ("johdanto", "2026-07-15 10:00:00", "abc"),
            ("kurssit", "2026-07-15 10:00:05", "abc"),
        ]
        kursori.description = [("OsioAvain",), ("Aikaleima",), ("Laskentatiiviste",)]
        rivit = mallit.hae_raportti_tila(1)
        assert rivit[0]["OsioAvain"] == "johdanto"
        assert rivit[0]["Laskentatiiviste"] == "abc"
        sql = kursori.execute.call_args[0][0]
        assert "Aikaleima" in sql and "Laskentatiiviste" in sql

    def test_laske_hitl_korjaukset_jalkeen_kayttaa_countia(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.fetchone.return_value = (3,)
        n = mallit.laske_hitl_korjaukset_jalkeen(1, "2026-07-15 10:00:00")
        sql, params = kursori.execute.call_args[0]
        assert "COUNT(*)" in sql and "HitlKorjaus" in sql and "Aikaleima >" in sql
        assert n == 3
        assert list(params) == [1, "2026-07-15 10:00:00"]

    def test_laske_hitl_vastaukset_kayttaa_countia(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.fetchone.return_value = (2,)
        n = mallit.laske_hitl_vastaukset(1, jalkeen="2026-07-15 10:00:00")
        sql, params = kursori.execute.call_args[0]
        assert "COUNT(*)" in sql and "Malli IS NULL" in sql and "Aikaleima >" in sql
        assert n == 2
        assert list(params) == [1, "2026-07-15 10:00:00"]
        mallit.laske_hitl_vastaukset(1)
        sql, params = kursori.execute.call_args[0]
        assert "Aikaleima" not in sql and list(params) == [1]
        # Vain nyt mukana olevien kurssien vastaukset (#114), kuten hae_vastaukset(vain_mukana=True)
        assert "kl.Mukana = 1" in sql


def test_kattavat_kaudet_ohittaa_virheellisen_kauden():
    """Virheellinen/puuttuva Opetusvuosi aineistossa ei saa kaataa raportin tilastoja."""
    kursori = MagicMock()
    kursori.fetchall.return_value = [("2025-2026",), ("rikki",), (None,)]
    assert tk_raportti._kattavat_kaudet(kursori, "2025-2026") == ["2025-2026"]


class TestTilastotYliopistoittain:
    """Per-yliopisto-suppilo: meta-hylätyt erotetaan LLM:lle menneistä samalla
    jaetulla SQL-aggregaatilla kuin hae_tutkimuksen_tilanne (DRY)."""
    SARAKKEET = ("KKID", "KouluNimi", "KurssiYhteensa", "Mukana", "OdottaaLLM",
                 "MetaHylatty", "LLMHylatty", "Luokiteltu", "MetaHylkaama", "MukanaTarkistettu")

    def _aja(self, kursori, paarivi, hitl=(), hitl_ryhmat=()):
        from unittest.mock import patch
        kursori.description = [(n,) for n in self.SARAKKEET]
        kursori.fetchall.side_effect = [[paarivi], list(hitl), list(hitl_ryhmat)]
        with patch.object(tk_raportti, "_rajaus", return_value=("2026-2027", [1])), \
             patch.object(tk_raportti, "_kattavat_kaudet", return_value=["2026-2027"]):
            return mallit.hae_tilastot_yliopistoittain(1)

    def test_suppilo_per_yliopisto(self, mock_yhteys):
        yht, kursori = mock_yhteys
        # 100 kurssia: 5 odottaa metaa, 45 meta-hylkäämää (5 niistä ihminen lisäsi),
        # 50 LLM:lle: 5 odottaa, 28 LLM-hylättyä, 17 LLM-mukana (+5 meta-lisättyä = 22).
        r = self._aja(kursori, (1, "OY", 100, 22, 5, 40, 28, 95, 45, 10))[0]
        assert r["OdottaaMeta"] == 5
        assert r["MetaHylkaama"] == 45
        assert r["LLMlle"] == 50
        assert r["OdottaaLLM"] == 5
        assert r["LLMKasitelty"] == 45        # LLM:lle − odottaa: ei meta-hylkäämiä
        assert r["LLMHylatty"] == 28
        assert r["Mukana"] == 22 and r["Hylatty"] == 68
        assert r["MukanaTarkistettu"] == 10

    def test_kayttaa_jaettua_suppiloaggregaattia(self, mock_yhteys):
        from tietokanta._yhteiset import luokitus_suppilo_sql
        yht, kursori = mock_yhteys
        self._aja(kursori, (1, "OY", 0, 0, 0, 0, 0, 0, 0, 0))
        sql, params = kursori.execute.call_args_list[0][0]
        assert luokitus_suppilo_sql() in sql
        assert "kl.KID = k.KID AND kl.TID = %s" in sql   # muiden tutkimusten luokitukset eivät mukana
        assert list(params) == ["2026-2027", 1, 1, 1]
        # HITL-kattavuus: mukana-kurssi on tarkistettu, jos hyväksytty tai korjattu
        assert "kl.KayttajaNimi IS NOT NULL OR hk.KID IS NOT NULL" in sql
        assert "SELECT DISTINCT KID FROM HitlKorjaus WHERE TID = %s" in sql

    def test_hitl_suunta_vaihe_ja_juurisyy(self, mock_yhteys):
        """Kunkin kurssin viimeisin korjaus ryhmiteltynä (KKID, UusiTila, Meta,
        Juurisyy, Muutos, lkm): Muutos = 0 → palautettu alkutilaan."""
        yht, kursori = mock_yhteys
        ryhmat = [(1, 1, 0, "riittamaton_opas", 1, 0, 4), (1, 1, 1, None, 1, 0, 2),
                  (1, 0, 0, "llm_virhe", 1, 0, 3), (1, 1, 0, "llm_virhe", 0, 0, 5), (2, 0, 0, None, 1, 0, 9)]
        r = self._aja(kursori, (1, "OY", 100, 22, 5, 40, 28, 95, 45, 10), hitl=[(1, 20)], hitl_ryhmat=ryhmat)[0]
        assert (r["LisattyLLM"], r["LisattyMeta"], r["PoistettuLLM"], r["PoistettuMeta"]) == (4, 2, 3, 0)
        assert (r["LisattyOpas"], r["LisattyLlmVirhe"], r["LisattyTuntematon"]) == (4, 0, 2)
        assert (r["PoistettuOpas"], r["PoistettuLlmVirhe"], r["PoistettuTuntematon"]) == (0, 3, 0)
        assert r["Palautettu"] == 5 and r["HitlKursseja"] == 14 and r["HitlLkm"] == 20
        # Juurisyyt yhteensä vain nettomuutoksista (palautettu ei ole virhe)
        assert (r["RiittamatonOpas"], r["LlmVirhe"], r["TuntematonSyy"]) == (4, 3, 2)

    def test_odottaneen_suora_paatos_ei_ole_llm_paatos(self, mock_yhteys):
        """LLM:ää odottanut kurssi (META_ODOTTAA), jonka ihminen päätti suoraan:
        ei LLMKasitelty:ssä eikä LLM:n kumoamissa (#114)."""
        yht, kursori = mock_yhteys
        ryhmat = [(1, 1, 0, None, 1, 1, 2), (1, 0, 0, None, 1, 1, 1), (1, 0, 0, None, 1, 0, 3)]
        r = self._aja(kursori, (1, "OY", 100, 22, 5, 40, 28, 95, 45, 10), hitl_ryhmat=ryhmat)[0]
        assert r["Suoraan"] == 3 and r["SuoraanMukana"] == 2
        assert r["LLMKasitelty"] == 42       # 50 LLM:lle − 5 odottaa − 3 ihmisen suoraan päättämää
        assert (r["LisattyLLM"], r["PoistettuLLM"]) == (0, 3)
        assert r["HitlKursseja"] == 6

    def test_hitl_kysely_vertaa_ensimmaiseen_korjaukseen(self, mock_yhteys):
        """Alkuperäinen päätös: meta-hylkäys = 0, muuten ensimmäisen korjauksen vastakohta."""
        from tietokanta._yhteiset import meta_hylkays_sql
        yht, kursori = mock_yhteys
        self._aja(kursori, (1, "OY", 0, 0, 0, 0, 0, 0, 0, 0))
        sql, params = kursori.execute.call_args_list[-1][0]
        assert "MIN(HID)" in sql and "MAX(HID)" in sql
        assert meta_hylkays_sql() in sql
        assert f"kl.Luokitteluperuste = '{tk_raportti.META_ODOTTAA}'" in sql
        assert list(params) == [1, 1]


class TestKaytetytMallit:
    def test_ryhmittelee_vaiheittain_aggregaattina(self, mock_yhteys):
        """Mallit tallennetuista riveistä (GROUP BY, ei rivinoutoa); tyhjä/NULL malli ohitetaan."""
        yht, kursori = mock_yhteys
        kursori.fetchall.return_value = [("seulonta", "m1", 30), ("arviointi", "m2", 5), ("seulonta", "m3", 40)]
        tulos = mallit.hae_kaytetyt_mallit(1)
        assert tulos == {"seulonta": [("m3", 40), ("m1", 30)], "arviointi": [("m2", 5)]}
        sql, params = kursori.execute.call_args[0]
        assert "GROUP BY Malli" in sql and "Kurssiluokitus" in sql and "Vastaukset" in sql
        assert "Malli <> ''" in sql
        assert list(params) == [1, 1]
