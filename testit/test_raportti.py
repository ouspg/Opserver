"""Testit raportti-moduulille."""
from unittest.mock import patch, call
import pytest
from raportti import llmraportti

TUTKIMUS = {
    "TID": 1,
    "LuokittelunNimi": "Kyber 2025",
    "Luokittelukehote": "Valitse kyberturvallisuuskurssit.",
    "Arviointikehote": "Arvioi kurssin soveltuvuus.",
    "Raportointikehote": "Raportti ESR-hakua varten.",
    "Tasorajaus": "aine",
    "Oppiainerajaus": "Tietotekniikka",
}

TILASTOT = [
    {
        "KKID": 1, "KouluNimi": "Tampereen yliopisto",
        "KurssiYhteensa": 100, "LLMKasitelty": 40,
        "Mukana": 12, "Hylatty": 28, "HitlLkm": 3,
    },
    {
        "KKID": 2, "KouluNimi": "Aalto-yliopisto",
        "KurssiYhteensa": 80, "LLMKasitelty": 30,
        "Mukana": 8, "Hylatty": 22, "HitlLkm": 1,
    },
]

KYSYMYKSET = [
    {"KysID": 10, "TID": 1, "Kysymys": "Liittyykö kurssi kyberturvallisuuteen?"},
    {"KysID": 11, "TID": 1, "Kysymys": "Soveltuuko kurssi ESR-hankkeeseen?"},
]


class TestTilastoTaulukko:
    def test_sisaltaa_yliopiston_nimen(self):
        tulos = llmraportti._tilasto_taulukko(TILASTOT)
        assert "Tampereen yliopisto" in tulos
        assert "Aalto-yliopisto" in tulos

    def test_sisaltaa_lukuarvot(self):
        tulos = llmraportti._tilasto_taulukko(TILASTOT)
        assert "100" in tulos
        assert "12" in tulos
        assert "3" in tulos


class TestRakennaViestiJohdanto:
    def test_sisaltaa_tutkimuksen_nimen(self):
        viesti = llmraportti._rakenna_johdanto_viesti(TUTKIMUS, TILASTOT)
        assert "Kyber 2025" in viesti

    def test_sisaltaa_raportointikehot(self):
        viesti = llmraportti._rakenna_johdanto_viesti(TUTKIMUS, TILASTOT)
        assert "ESR-hakua varten" in viesti

    def test_sisaltaa_yliopistojen_maaran(self):
        viesti = llmraportti._rakenna_johdanto_viesti(TUTKIMUS, TILASTOT)
        assert "2" in viesti  # 2 yliopistoa

    def test_sisaltaa_kurssien_kokonaisluvun(self):
        viesti = llmraportti._rakenna_johdanto_viesti(TUTKIMUS, TILASTOT)
        assert "180" in viesti  # 100 + 80

    def test_sisaltaa_mukana_luvun(self):
        viesti = llmraportti._rakenna_johdanto_viesti(TUTKIMUS, TILASTOT)
        assert "20" in viesti  # 12 + 8


class TestRakennaViestiKurssit:
    def test_sisaltaa_valintakehotteen(self):
        viesti = llmraportti._rakenna_kurssit_viesti(TUTKIMUS, TILASTOT)
        assert "Valitse kyberturvallisuuskurssit" in viesti

    def test_sisaltaa_tasorajauksen(self):
        viesti = llmraportti._rakenna_kurssit_viesti(TUTKIMUS, TILASTOT)
        assert "aine" in viesti

    def test_sisaltaa_tilastotaulukon(self):
        viesti = llmraportti._rakenna_kurssit_viesti(TUTKIMUS, TILASTOT)
        assert "Tampereen yliopisto" in viesti

    def test_sisaltaa_hitl_summan(self):
        viesti = llmraportti._rakenna_kurssit_viesti(TUTKIMUS, TILASTOT)
        assert "4" in viesti  # 3 + 1 HITL-korjausta


class TestRakennaViestiArvioinnit:
    def test_sisaltaa_arviointikehot(self):
        with patch("raportti.llmraportti.mallit.hae_arviokommentit_kaikki", return_value=[]):
            viesti = llmraportti._rakenna_arvioinnit_viesti(TUTKIMUS, KYSYMYKSET, TILASTOT)
        assert "Arvioi kurssin soveltuvuus" in viesti

    def test_sisaltaa_kysymykset(self):
        with patch("raportti.llmraportti.mallit.hae_arviokommentit_kaikki", return_value=[]):
            viesti = llmraportti._rakenna_arvioinnit_viesti(TUTKIMUS, KYSYMYKSET, TILASTOT)
        assert "Liittyykö kurssi kyberturvallisuuteen" in viesti
        assert "Soveltuuko kurssi ESR-hankkeeseen" in viesti

    def test_sisaltaa_kommenttien_maaran(self):
        kommentit = [{"KID": 1, "KysID": 10, "Kommentti": "OK"}, {"KID": 2, "KysID": 11, "Kommentti": "Ei"}]
        with patch("raportti.llmraportti.mallit.hae_arviokommentit_kaikki", return_value=kommentit):
            viesti = llmraportti._rakenna_arvioinnit_viesti(TUTKIMUS, KYSYMYKSET, TILASTOT)
        assert "2" in viesti


class TestAja:
    def test_aja_generoi_kaikki_osiot(self):
        with patch("raportti.llmraportti.mallit.hae_tilastot_yliopistoittain", return_value=TILASTOT), \
             patch("raportti.llmraportti.mallit.hae_kysymykset", return_value=KYSYMYKSET), \
             patch("raportti.llmraportti.mallit.hae_arviokommentit_kaikki", return_value=[]), \
             patch("raportti.llmraportti.mallit.aseta_raportti_osio") as mock_aseta, \
             patch("raportti.llmraportti.kutsu.kysy", return_value="LLM-teksti") as mock_kysy, \
             patch("raportti.llmraportti._lue_jarjestelmakehote", return_value="jarj"):
            lkm = llmraportti.aja(TUTKIMUS)

        assert lkm == 3
        assert mock_kysy.call_count == 3
        assert mock_aseta.call_count == 3
        # Tarkista että kaikki osioavaimet tallennettiin
        avaimet = [c.args[1] for c in mock_aseta.call_args_list]
        assert avaimet == ["johdanto", "kurssit", "arvioinnit"]

    def test_aja_tallentaa_llm_tekstin(self):
        with patch("raportti.llmraportti.mallit.hae_tilastot_yliopistoittain", return_value=TILASTOT), \
             patch("raportti.llmraportti.mallit.hae_kysymykset", return_value=KYSYMYKSET), \
             patch("raportti.llmraportti.mallit.hae_arviokommentit_kaikki", return_value=[]), \
             patch("raportti.llmraportti.mallit.aseta_raportti_osio") as mock_aseta, \
             patch("raportti.llmraportti.kutsu.kysy", return_value="Generoitu teksti"), \
             patch("raportti.llmraportti._lue_jarjestelmakehote", return_value="jarj"):
            llmraportti.aja(TUTKIMUS)

        mock_aseta.assert_any_call(1, "johdanto", "Generoitu teksti")

    def test_aja_kutsuu_edistyminen_cb(self):
        tapahtumat = []
        def edistyminen(n, yht, avain):
            tapahtumat.append((n, yht, avain))

        with patch("raportti.llmraportti.mallit.hae_tilastot_yliopistoittain", return_value=TILASTOT), \
             patch("raportti.llmraportti.mallit.hae_kysymykset", return_value=KYSYMYKSET), \
             patch("raportti.llmraportti.mallit.hae_arviokommentit_kaikki", return_value=[]), \
             patch("raportti.llmraportti.mallit.aseta_raportti_osio"), \
             patch("raportti.llmraportti.kutsu.kysy", return_value="teksti"), \
             patch("raportti.llmraportti._lue_jarjestelmakehote", return_value="jarj"):
            llmraportti.aja(TUTKIMUS, edistyminen)

        # 3 osio-callbackia + 1 "valmis"
        assert len(tapahtumat) == 4
        assert tapahtumat[0] == (0, 3, "johdanto")
        assert tapahtumat[3] == (3, 3, "valmis")

    def test_aja_on_idempotentti(self):
        """Toinen ajo ylikirjoittaa olemassa olevat osiot."""
        with patch("raportti.llmraportti.mallit.hae_tilastot_yliopistoittain", return_value=TILASTOT), \
             patch("raportti.llmraportti.mallit.hae_kysymykset", return_value=KYSYMYKSET), \
             patch("raportti.llmraportti.mallit.hae_arviokommentit_kaikki", return_value=[]), \
             patch("raportti.llmraportti.mallit.aseta_raportti_osio") as mock_aseta, \
             patch("raportti.llmraportti.kutsu.kysy", return_value="teksti"), \
             patch("raportti.llmraportti._lue_jarjestelmakehote", return_value="jarj"):
            llmraportti.aja(TUTKIMUS)
            llmraportti.aja(TUTKIMUS)

        # Kumpikin ajo tallentaa 3 osiota — ei estä uudelleenajoa
        assert mock_aseta.call_count == 6
