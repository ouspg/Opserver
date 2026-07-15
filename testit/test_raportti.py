"""Testit raportti-moduulille."""
from unittest.mock import patch, call, ANY
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
        "HitlKursseja": 3, "RiittamatonOpas": 2, "LlmVirhe": 1, "TuntematonSyy": 0,
    },
    {
        "KKID": 2, "KouluNimi": "Aalto-yliopisto",
        "KurssiYhteensa": 80, "LLMKasitelty": 30,
        "Mukana": 8, "Hylatty": 22, "HitlLkm": 1,
        "HitlKursseja": 1, "RiittamatonOpas": 0, "LlmVirhe": 0, "TuntematonSyy": 1,
    },
]
# Yhteensä: LLM-luokiteltu 70, käsin muutettu 4 (5,7 %); juurisyyt
# riittämätön opas 2 (50 %), LLM:n virhe 1 (25 %), tuntematon 1 (25 %).

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
        assert "4" in viesti  # 3 + 1 käsin muutettua kurssia

    def test_sisaltaa_kasin_muutos_osuuden(self):
        viesti = llmraportti._rakenna_kurssit_viesti(TUTKIMUS, TILASTOT)
        assert "5.7" in viesti  # 4 / 70 LLM-luokiteltua kurssia

    def test_sisaltaa_juurisyyjakauman(self):
        viesti = llmraportti._rakenna_kurssit_viesti(TUTKIMUS, TILASTOT)
        assert "Riittämätön opinto-opas" in viesti
        assert "50.0" in viesti  # 2 / 4 korjauksista riittämätön opas
        assert "LLM:n väärinymmärrys" in viesti
        assert "25.0" in viesti  # 1 / 4 korjauksista LLM:n virhe


class TestHitlMittarit:
    def test_laskee_osuudet(self):
        m = llmraportti.hitl_mittarit(TILASTOT)
        assert m["llm_kasitelty"] == 70
        assert m["muutettu"] == 4
        assert round(m["muutettu_pros"], 1) == 5.7
        assert m["opas"] == 2 and round(m["opas_pros"], 1) == 50.0
        assert m["llm_virhe"] == 1 and round(m["llm_virhe_pros"], 1) == 25.0
        assert m["tuntematon"] == 1

    def test_nolla_muutosta_ei_jaa_nollalla(self):
        tyhjat = [{"LLMKasitelty": 0, "HitlKursseja": 0, "RiittamatonOpas": 0,
                   "LlmVirhe": 0, "TuntematonSyy": 0}]
        m = llmraportti.hitl_mittarit(tyhjat)
        assert m["muutettu_pros"] == 0.0
        assert m["opas_pros"] == 0.0


class TestRaporttiTiiviste:
    """raporttitiiviste() hashaa lähdeaineiston, josta raportti koottiin."""

    def _tiiviste(self, tutkimus=TUTKIMUS, tilastot=TILASTOT, kysymykset=KYSYMYKSET,
                  vastaus_tila=None, kommentit=None):
        with patch("raportti.llmraportti.mallit.hae_vastaus_tiivisteet",
                   return_value=vastaus_tila or {}), \
             patch("raportti.llmraportti.mallit.hae_arviokommentit_kaikki",
                   return_value=kommentit or []):
            return llmraportti.raporttitiiviste(tutkimus, tilastot, kysymykset)

    def test_palauttaa_64_merkkia_hexia(self):
        t = self._tiiviste()
        assert len(t) == 64 and all(c in "0123456789abcdef" for c in t)

    def test_deterministinen(self):
        assert self._tiiviste() == self._tiiviste()

    def test_muuttuu_kun_tilastot_muuttuu(self):
        muutettu = [{**TILASTOT[0], "Mukana": 999}, TILASTOT[1]]
        assert self._tiiviste() != self._tiiviste(tilastot=muutettu)

    def test_muuttuu_kun_juurisyy_muuttuu(self):
        muutettu = [{**TILASTOT[0], "RiittamatonOpas": 3, "TuntematonSyy": 0}, TILASTOT[1]]
        assert self._tiiviste() != self._tiiviste(tilastot=muutettu)

    def test_muuttuu_kun_raportointikehote_muuttuu(self):
        toinen = {**TUTKIMUS, "Raportointikehote": "Aivan eri ohje."}
        assert self._tiiviste() != self._tiiviste(tutkimus=toinen)

    def test_muuttuu_kun_arviointien_tila_muuttuu(self):
        a = self._tiiviste(vastaus_tila={})
        b = self._tiiviste(vastaus_tila={(1, 10): {"tiiviste": "x", "vastattu": True}})
        assert a != b

    def test_muuttuu_kun_kommentti_lisataan(self):
        a = self._tiiviste(kommentit=[])
        b = self._tiiviste(kommentit=[{"KID": 1, "KysID": 10, "Kommentti": "Uusi"}])
        assert a != b


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
             patch("raportti.llmraportti.mallit.hae_vastaus_tiivisteet", return_value={}), \
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
             patch("raportti.llmraportti.mallit.hae_vastaus_tiivisteet", return_value={}), \
             patch("raportti.llmraportti.mallit.aseta_raportti_osio") as mock_aseta, \
             patch("raportti.llmraportti.kutsu.kysy", return_value="Generoitu teksti"), \
             patch("raportti.llmraportti._lue_jarjestelmakehote", return_value="jarj"):
            llmraportti.aja(TUTKIMUS)

        mock_aseta.assert_any_call(1, "johdanto", "Generoitu teksti", laskentatiiviste=ANY)

    def test_aja_kirjoittaa_laskentatiivisteen_jokaiseen_osioon(self):
        with patch("raportti.llmraportti.mallit.hae_tilastot_yliopistoittain", return_value=TILASTOT), \
             patch("raportti.llmraportti.mallit.hae_kysymykset", return_value=KYSYMYKSET), \
             patch("raportti.llmraportti.mallit.hae_arviokommentit_kaikki", return_value=[]), \
             patch("raportti.llmraportti.mallit.hae_vastaus_tiivisteet", return_value={}), \
             patch("raportti.llmraportti.mallit.aseta_raportti_osio") as mock_aseta, \
             patch("raportti.llmraportti.kutsu.kysy", return_value="teksti"), \
             patch("raportti.llmraportti._lue_jarjestelmakehote", return_value="jarj"):
            llmraportti.aja(TUTKIMUS)

        tiivisteet = [c.kwargs["laskentatiiviste"] for c in mock_aseta.call_args_list]
        assert len(tiivisteet) == 3
        assert all(len(t) == 64 for t in tiivisteet)
        assert len(set(tiivisteet)) == 1  # sama tiiviste jokaiseen osioon

    def test_aja_kutsuu_edistyminen_cb(self):
        tapahtumat = []
        def edistyminen(n, yht, avain):
            tapahtumat.append((n, yht, avain))

        with patch("raportti.llmraportti.mallit.hae_tilastot_yliopistoittain", return_value=TILASTOT), \
             patch("raportti.llmraportti.mallit.hae_kysymykset", return_value=KYSYMYKSET), \
             patch("raportti.llmraportti.mallit.hae_arviokommentit_kaikki", return_value=[]), \
             patch("raportti.llmraportti.mallit.hae_vastaus_tiivisteet", return_value={}), \
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
             patch("raportti.llmraportti.mallit.hae_vastaus_tiivisteet", return_value={}), \
             patch("raportti.llmraportti.mallit.aseta_raportti_osio") as mock_aseta, \
             patch("raportti.llmraportti.kutsu.kysy", return_value="teksti"), \
             patch("raportti.llmraportti._lue_jarjestelmakehote", return_value="jarj"):
            llmraportti.aja(TUTKIMUS)
            llmraportti.aja(TUTKIMUS)

        # Kumpikin ajo tallentaa 3 osiota — ei estä uudelleenajoa
        assert mock_aseta.call_count == 6
