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


def test_kattavat_kaudet_ohittaa_virheellisen_kauden():
    """Virheellinen/puuttuva Opetusvuosi aineistossa ei saa kaataa raportin tilastoja."""
    kursori = MagicMock()
    kursori.fetchall.return_value = [("2025-2026",), ("rikki",), (None,)]
    assert tk_raportti._kattavat_kaudet(kursori, "2025-2026") == ["2025-2026"]
