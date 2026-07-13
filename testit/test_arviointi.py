"""Testit arviointi-moduulille."""
from unittest.mock import patch, MagicMock, call
import pytest
from arviointi import llmarviointi


LLM_VASTAUS = '{"tulokset": [{"id": 1, "vastaukset": ["Kyllä", "Ei"]}, {"id": 2, "vastaukset": ["Ei", "Kyllä"]}]}'

KYSYMYKSET = [
    {"KysID": 10, "TID": 1, "Kysymys": "Liittyykö kurssi kyberturvallisuuteen?",
     "Luokittelu": "vapaa_teksti", "LuokitteluMaarittely": None},
    {"KysID": 11, "TID": 1, "Kysymys": "Soveltuuko kurssi ESR-hankkeeseen?",
     "Luokittelu": "vapaa_teksti", "LuokitteluMaarittely": None},
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
    """aja() perustuu nyt hae_valitut_kurssit + hae_vastaus_tiivisteet -tietoihin.
    olemassa={} → mikään kurssi ei ole vielä arvioitu → kaikki kysymykset kysytään.
    """

    def test_aja_kirjoittaa_vastaukset(self):
        with patch("arviointi.llmarviointi.mallit.hae_kysymykset", return_value=KYSYMYKSET), \
             patch("arviointi.llmarviointi.mallit.hae_valitut_kurssit", return_value=KURSSIT), \
             patch("arviointi.llmarviointi.mallit.hae_vastaus_tiivisteet", return_value={}), \
             patch("arviointi.llmarviointi.kutsu.kysy", return_value=LLM_VASTAUS), \
             patch("arviointi.llmarviointi.kutsu.hae_malli", return_value="testimalli"), \
             patch("arviointi.llmarviointi.mallit.aseta_vastaus") as mock_aseta, \
             patch("arviointi.llmarviointi._lue_jarjestelma_kehote", return_value="system"):
            arvioitu = llmarviointi.aja(TUTKIMUS)

        assert arvioitu == 2
        # 2 kurssit × 2 kysymystä = 4 aseta_vastaus-kutsua, kukin tiivisteellä
        assert mock_aseta.call_count == 4
        for c in mock_aseta.call_args_list:
            assert c.kwargs["tiiviste"] and len(c.kwargs["tiiviste"]) == 64

    def test_aja_ohittaa_jo_arvioidut_samalla_tiivisteella(self):
        jarj = "system"
        t10 = llmarviointi.tiiviste.kysymys(TUTKIMUS["Arviointikehote"], jarj, KYSYMYKSET[0])
        t11 = llmarviointi.tiiviste.kysymys(TUTKIMUS["Arviointikehote"], jarj, KYSYMYKSET[1])
        olemassa = {
            (1, 10): {"tiiviste": t10, "vastattu": True},
            (1, 11): {"tiiviste": t11, "vastattu": True},
            (2, 10): {"tiiviste": t10, "vastattu": True},
            (2, 11): {"tiiviste": t11, "vastattu": True},
        }
        with patch("arviointi.llmarviointi.mallit.hae_kysymykset", return_value=KYSYMYKSET), \
             patch("arviointi.llmarviointi.mallit.hae_valitut_kurssit", return_value=KURSSIT), \
             patch("arviointi.llmarviointi.mallit.hae_vastaus_tiivisteet", return_value=olemassa), \
             patch("arviointi.llmarviointi.kutsu.kysy") as mock_kysy, \
             patch("arviointi.llmarviointi.mallit.aseta_vastaus") as mock_aseta, \
             patch("arviointi.llmarviointi._lue_jarjestelma_kehote", return_value=jarj):
            arvioitu = llmarviointi.aja(TUTKIMUS)
        assert arvioitu == 0
        mock_kysy.assert_not_called()
        mock_aseta.assert_not_called()

    def test_aja_kysyy_vain_muuttuneen_kysymyksen(self):
        jarj = "system"
        t10 = llmarviointi.tiiviste.kysymys(TUTKIMUS["Arviointikehote"], jarj, KYSYMYKSET[0])
        olemassa = {
            (1, 10): {"tiiviste": t10, "vastattu": True},
            (1, 11): {"tiiviste": "vanha", "vastattu": True},
            (2, 10): {"tiiviste": t10, "vastattu": True},
            (2, 11): {"tiiviste": "vanha", "vastattu": True},
        }
        vastaus = '{"tulokset": [{"id": 1, "vastaukset": ["Uusi"]}, {"id": 2, "vastaukset": ["Uusi2"]}]}'
        with patch("arviointi.llmarviointi.mallit.hae_kysymykset", return_value=KYSYMYKSET), \
             patch("arviointi.llmarviointi.mallit.hae_valitut_kurssit", return_value=KURSSIT), \
             patch("arviointi.llmarviointi.mallit.hae_vastaus_tiivisteet", return_value=olemassa), \
             patch("arviointi.llmarviointi.kutsu.kysy", return_value=vastaus) as mock_kysy, \
             patch("arviointi.llmarviointi.kutsu.hae_malli", return_value="m"), \
             patch("arviointi.llmarviointi.mallit.aseta_vastaus") as mock_aseta, \
             patch("arviointi.llmarviointi._lue_jarjestelma_kehote", return_value=jarj):
            llmarviointi.aja(TUTKIMUS)
        viesti = mock_kysy.call_args.args[0]
        assert "Soveltuuko" in viesti          # kysymys 11 mukana
        assert "Liittyykö" not in viesti        # kysymys 10 ohitettu
        assert mock_aseta.call_count == 2       # vain KysID 11, 2 kurssille
        assert all(c.args[0] == 11 for c in mock_aseta.call_args_list)

    def test_aja_ilman_kysymyksia_palauttaa_nollan(self):
        with patch("arviointi.llmarviointi.mallit.hae_kysymykset", return_value=[]), \
             patch("arviointi.llmarviointi.kutsu.kysy") as mock_kysy:
            arvioitu = llmarviointi.aja(TUTKIMUS)
        assert arvioitu == 0
        mock_kysy.assert_not_called()

    def test_aja_ilman_valittuja_kursseja_palauttaa_nollan(self):
        with patch("arviointi.llmarviointi.mallit.hae_kysymykset", return_value=KYSYMYKSET), \
             patch("arviointi.llmarviointi.mallit.hae_valitut_kurssit", return_value=[]), \
             patch("arviointi.llmarviointi.mallit.hae_vastaus_tiivisteet", return_value={}), \
             patch("arviointi.llmarviointi._lue_jarjestelma_kehote", return_value="system"), \
             patch("arviointi.llmarviointi.kutsu.kysy") as mock_kysy:
            arvioitu = llmarviointi.aja(TUTKIMUS)
        assert arvioitu == 0
        mock_kysy.assert_not_called()

    def test_aja_kutsuu_kysy_json_muodolla(self):
        with patch("arviointi.llmarviointi.mallit.hae_kysymykset", return_value=KYSYMYKSET), \
             patch("arviointi.llmarviointi.mallit.hae_valitut_kurssit", return_value=KURSSIT[:1]), \
             patch("arviointi.llmarviointi.mallit.hae_vastaus_tiivisteet", return_value={}), \
             patch("arviointi.llmarviointi.kutsu.kysy", return_value=LLM_VASTAUS) as mock_kysy, \
             patch("arviointi.llmarviointi.kutsu.hae_malli", return_value="m"), \
             patch("arviointi.llmarviointi.mallit.aseta_vastaus"), \
             patch("arviointi.llmarviointi._lue_jarjestelma_kehote", return_value="system"):
            llmarviointi.aja(TUTKIMUS)
        _, kwargs = mock_kysy.call_args
        assert kwargs.get("json_muoto") is True

    def test_aja_kutsuu_edistyminen_cb(self):
        tapahtumat = []
        def edistyminen(n, yht, erä, erat):
            tapahtumat.append((n, yht, erä, erat))

        with patch("arviointi.llmarviointi.mallit.hae_kysymykset", return_value=KYSYMYKSET), \
             patch("arviointi.llmarviointi.mallit.hae_valitut_kurssit", return_value=KURSSIT), \
             patch("arviointi.llmarviointi.mallit.hae_vastaus_tiivisteet", return_value={}), \
             patch("arviointi.llmarviointi.kutsu.kysy", return_value=LLM_VASTAUS), \
             patch("arviointi.llmarviointi.kutsu.hae_malli", return_value="m"), \
             patch("arviointi.llmarviointi.mallit.aseta_vastaus"), \
             patch("arviointi.llmarviointi._lue_jarjestelma_kehote", return_value="system"):
            llmarviointi.aja(TUTKIMUS, edistyminen)

        # Pre-batch (0 käsitelty) ja post-batch (2 käsitelty) — yhteensä 2 tapahtumaa
        assert len(tapahtumat) == 2
        assert tapahtumat[0] == (0, 2, 1, 1)
        assert tapahtumat[1] == (2, 2, 1, 1)

    def test_aja_max_erat_rajaa_yhteen_pyyntoon(self):
        # 7 kurssia, sama kysymysjoukko → ERÄKOKO 5 → 2 erää. max_erat=1 → 1 LLM-pyyntö.
        kurssit = [{"KID": i, "KurssiNimi": f"K{i}", "Koodi": f"C{i}", "Taso": "aine",
                    "Oppiaine": "TT", "Opintopisteet": "5", "Opetusvuosi": "2025", "OpsKuvaus": None}
                   for i in range(1, 8)]
        vastaus = '{"tulokset": [{"id": 1, "vastaukset": ["a", "b"]}]}'
        tapahtumat = []
        with patch("arviointi.llmarviointi.mallit.hae_kysymykset", return_value=KYSYMYKSET), \
             patch("arviointi.llmarviointi.mallit.hae_valitut_kurssit", return_value=kurssit), \
             patch("arviointi.llmarviointi.mallit.hae_vastaus_tiivisteet", return_value={}), \
             patch("arviointi.llmarviointi.kutsu.kysy", return_value=vastaus) as mock_kysy, \
             patch("arviointi.llmarviointi.kutsu.hae_malli", return_value="m"), \
             patch("arviointi.llmarviointi.mallit.aseta_vastaus"), \
             patch("arviointi.llmarviointi._lue_jarjestelma_kehote", return_value="system"):
            llmarviointi.aja(TUTKIMUS, lambda n, y, e, et: tapahtumat.append(et), max_erat=1)
        assert mock_kysy.call_count == 1
        assert all(et == 1 for et in tapahtumat)  # eräkokonaismäärä näkyy rajattuna

    def test_aja_ilman_max_erat_ajaa_kaikki_erat(self):
        kurssit = [{"KID": i, "KurssiNimi": f"K{i}", "Koodi": f"C{i}", "Taso": "aine",
                    "Oppiaine": "TT", "Opintopisteet": "5", "Opetusvuosi": "2025", "OpsKuvaus": None}
                   for i in range(1, 8)]
        vastaus = '{"tulokset": [{"id": 1, "vastaukset": ["a", "b"]}]}'
        with patch("arviointi.llmarviointi.mallit.hae_kysymykset", return_value=KYSYMYKSET), \
             patch("arviointi.llmarviointi.mallit.hae_valitut_kurssit", return_value=kurssit), \
             patch("arviointi.llmarviointi.mallit.hae_vastaus_tiivisteet", return_value={}), \
             patch("arviointi.llmarviointi.kutsu.kysy", return_value=vastaus) as mock_kysy, \
             patch("arviointi.llmarviointi.kutsu.hae_malli", return_value="m"), \
             patch("arviointi.llmarviointi.mallit.aseta_vastaus"), \
             patch("arviointi.llmarviointi._lue_jarjestelma_kehote", return_value="system"):
            llmarviointi.aja(TUTKIMUS)
        assert mock_kysy.call_count == 2

    def test_laske_tyomaara_erottaa_uudet_ja_vanhentuneet(self):
        jarj = "system"
        t10 = llmarviointi.tiiviste.kysymys(TUTKIMUS["Arviointikehote"], jarj, KYSYMYKSET[0])
        # Kurssi 1: arvioitu mutta kysymys 11 vanha → vanhentunut. Kurssi 2: ei vastauksia → uusi.
        olemassa = {
            (1, 10): {"tiiviste": t10, "vastattu": True},
            (1, 11): {"tiiviste": "vanha", "vastattu": True},
        }
        with patch("arviointi.llmarviointi.mallit.hae_kysymykset", return_value=KYSYMYKSET), \
             patch("arviointi.llmarviointi.mallit.hae_valitut_kurssit", return_value=KURSSIT), \
             patch("arviointi.llmarviointi.mallit.hae_vastaus_tiivisteet", return_value=olemassa), \
             patch("arviointi.llmarviointi._lue_jarjestelma_kehote", return_value=jarj):
            uudet, vanhentuneet = llmarviointi.laske_tyomaara(TUTKIMUS)
        assert uudet == 1
        assert vanhentuneet == 1

    def test_kysymystiivisteet_ei_hae_kursseja_eika_vastauksia(self):
        """Kevyt tiivistehaku käyttää vain hae_kysymykset — ei kurssien/vastausten
        latausta (jota täysi _selvita_tyo tekisi turhaan tiivisteitä varten)."""
        with patch("arviointi.llmarviointi.mallit.hae_kysymykset", return_value=KYSYMYKSET), \
             patch("arviointi.llmarviointi.mallit.hae_valitut_kurssit") as mock_kurssit, \
             patch("arviointi.llmarviointi.mallit.hae_vastaus_tiivisteet") as mock_vast, \
             patch("arviointi.llmarviointi._lue_jarjestelma_kehote", return_value="system"):
            tiivisteet = llmarviointi._kysymystiivisteet(TUTKIMUS)
        assert set(tiivisteet) == {10, 11}                       # KysID:t
        assert all(len(t) == 64 for t in tiivisteet.values())
        mock_kurssit.assert_not_called()
        mock_vast.assert_not_called()

    def test_laske_tyomaara_esilasketulla_tiedolla_ei_hae_uudelleen(self):
        """Annettu tieto → ei uutta _selvita_tyo-hakua (ei kurssien/vastausten latausta)."""
        tieto = {"kysymykset": KYSYMYKSET,
                 "olemassa": {(1, 10): {"tiiviste": "x", "vastattu": True}},
                 "tyo": {1: [KYSYMYKSET[1]], 2: list(KYSYMYKSET)}}
        with patch("arviointi.llmarviointi._selvita_tyo") as mock_selvita:
            uudet, vanhentuneet = llmarviointi.laske_tyomaara(TUTKIMUS, tieto=tieto)
        mock_selvita.assert_not_called()
        assert (uudet, vanhentuneet) == (1, 1)   # kurssi 1: oli vastauksia; kurssi 2: uusi

    def test_aja_esilasketulla_tiedolla_ei_hae_kursseja(self):
        """aja(tieto=...) ei kutsu _selvita_tyo:tä → ei hae_valitut_kurssit-latausta."""
        jarj = "system"
        kys_tiiviste = {k["KysID"]: llmarviointi.tiiviste.kysymys(
            TUTKIMUS["Arviointikehote"], jarj, k) for k in KYSYMYKSET}
        tieto = {"kysymykset": KYSYMYKSET, "jarjestelma": jarj, "kys_tiiviste": kys_tiiviste,
                 "arviointikehote": TUTKIMUS["Arviointikehote"],
                 "kurssi_kartta": {k["KID"]: k for k in KURSSIT},
                 "olemassa": {}, "tyo": {1: list(KYSYMYKSET), 2: list(KYSYMYKSET)}}
        with patch("arviointi.llmarviointi.mallit.hae_kysymykset") as mk, \
             patch("arviointi.llmarviointi.mallit.hae_valitut_kurssit") as mvk, \
             patch("arviointi.llmarviointi.mallit.hae_vastaus_tiivisteet") as mvt, \
             patch("arviointi.llmarviointi.kutsu.kysy", return_value=LLM_VASTAUS), \
             patch("arviointi.llmarviointi.kutsu.hae_malli", return_value="m"), \
             patch("arviointi.llmarviointi.mallit.aseta_vastaus") as mock_aseta, \
             patch("arviointi.llmarviointi._lue_jarjestelma_kehote", return_value=jarj):
            arvioitu = llmarviointi.aja(TUTKIMUS, tieto=tieto)
        assert arvioitu == 2
        assert mock_aseta.call_count == 4          # 2 kurssia × 2 kysymystä
        mk.assert_not_called(); mvk.assert_not_called(); mvt.assert_not_called()


KYSYMYKSET_MONITYYPPI = [
    {"KysID": 10, "TID": 1, "Kysymys": "Kuvaile kurssia.",
     "Luokittelu": "vapaa_teksti", "LuokitteluMaarittely": None},
    {"KysID": 11, "TID": 1, "Kysymys": "Millä tasolla kyber on mukana?",
     "Luokittelu": "luokittelu",
     "LuokitteluMaarittely": {"luokat": [
         {"nimi": "korkea", "kuvaus": "Pääaiheena"},
         {"nimi": "matala", "kuvaus": "Sivuaa"},
     ]}},
    {"KysID": 12, "TID": 1, "Kysymys": "Kuinka hyödyllinen kurssi on (1–3)?",
     "Luokittelu": "asteikko",
     "LuokitteluMaarittely": {"minimi": 1, "maksimi": 3,
                               "pisteet": [{"arvo": 1, "kuvaus": "Ei lainkaan"},
                                           {"arvo": 3, "kuvaus": "Täydellisesti"}]}},
    {"KysID": 13, "TID": 1, "Kysymys": "Mitkä ovat kurssin esitiedot?",
     "Luokittelu": "lista", "LuokitteluMaarittely": {"max_kohdat": 5}},
]


class TestRakennaKysymysteksti:
    def test_vapaa_teksti_on_vain_kysymys(self):
        teksti = llmarviointi._rakenna_kysymysteksti(KYSYMYKSET[:1])
        assert "Kuvaile" not in teksti  # eri kysymys, tarkistetaan muoto
        ks = [{"KysID": 1, "Kysymys": "Kuvaile kurssia.", "Luokittelu": "vapaa_teksti", "LuokitteluMaarittely": None}]
        teksti = llmarviointi._rakenna_kysymysteksti(ks)
        assert "1. Kuvaile kurssia." in teksti
        assert "luokka" not in teksti.lower()
        assert "pisteet" not in teksti.lower()

    def test_luokittelu_sisaltaa_luokat(self):
        teksti = llmarviointi._rakenna_kysymysteksti([KYSYMYKSET_MONITYYPPI[1]])
        assert "korkea" in teksti
        assert "matala" in teksti
        assert "luokka" in teksti.lower()

    def test_asteikko_sisaltaa_asteikon(self):
        teksti = llmarviointi._rakenna_kysymysteksti([KYSYMYKSET_MONITYYPPI[2]])
        assert "1" in teksti
        assert "3" in teksti
        assert "pisteet" in teksti.lower()
        assert "Ei lainkaan" in teksti

    def test_lista_pyytaa_taulukon(self):
        teksti = llmarviointi._rakenna_kysymysteksti([KYSYMYKSET_MONITYYPPI[3]])
        assert "kohdat" in teksti
        assert "esitiedot" in teksti.lower()
        assert "5" in teksti  # max_kohdat-raja näkyy

    def test_numerot_oikein_sekakysymyksissa(self):
        teksti = llmarviointi._rakenna_kysymysteksti(KYSYMYKSET_MONITYYPPI)
        assert "1." in teksti
        assert "2." in teksti
        assert "3." in teksti
        assert "4." in teksti


class TestTallennaTulokset:
    def test_vapaa_teksti_tallennetaan_sellaisenaan(self):
        with patch("arviointi.llmarviointi.mallit.aseta_vastaus") as mock_aseta:
            ks = [{"KysID": 10, "Luokittelu": "vapaa_teksti", "LuokitteluMaarittely": None}]
            tulokset = [{"id": 1, "vastaukset": ["Hyvä kurssi"]}]
            llmarviointi._tallenna_tulokset(tulokset, ks, "testimalli")
        mock_aseta.assert_called_once_with(10, 1, "Hyvä kurssi", "testimalli", pisteet=None, luokka=None, lista=None, tiiviste=None)

    def test_luokittelu_purkaa_luokan_ja_perustelun(self):
        with patch("arviointi.llmarviointi.mallit.aseta_vastaus") as mock_aseta:
            ks = [{"KysID": 11, "Luokittelu": "luokittelu", "LuokitteluMaarittely": {}}]
            tulokset = [{"id": 1, "vastaukset": [{"luokka": "korkea", "perustelu": "Koska..."}]}]
            llmarviointi._tallenna_tulokset(tulokset, ks, "malli")
        mock_aseta.assert_called_once_with(11, 1, "Koska...", "malli", pisteet=None, luokka="korkea", lista=None, tiiviste=None)

    def test_asteikko_purkaa_pisteet_ja_perustelun(self):
        with patch("arviointi.llmarviointi.mallit.aseta_vastaus") as mock_aseta:
            ks = [{"KysID": 12, "Luokittelu": "asteikko", "LuokitteluMaarittely": {}}]
            tulokset = [{"id": 1, "vastaukset": [{"pisteet": 4, "perustelu": "Erittäin hyvä"}]}]
            llmarviointi._tallenna_tulokset(tulokset, ks, "malli")
        mock_aseta.assert_called_once_with(12, 1, "Erittäin hyvä", "malli", pisteet=4.0, luokka=None, lista=None, tiiviste=None)

    def test_fallback_merkkijono_strukturoidulle(self):
        """LLM palauttaa merkkijonon vaikka odotettiin objektia — tallennetaan sellaisenaan."""
        with patch("arviointi.llmarviointi.mallit.aseta_vastaus") as mock_aseta:
            ks = [{"KysID": 11, "Luokittelu": "luokittelu", "LuokitteluMaarittely": {}}]
            tulokset = [{"id": 1, "vastaukset": ["korkea"]}]
            llmarviointi._tallenna_tulokset(tulokset, ks, "malli")
        mock_aseta.assert_called_once_with(11, 1, "korkea", "malli", pisteet=None, luokka=None, lista=None, tiiviste=None)

    def test_lista_purkaa_kohdat_ja_perustelun(self):
        with patch("arviointi.llmarviointi.mallit.aseta_vastaus") as mock_aseta:
            ks = [{"KysID": 13, "Luokittelu": "lista", "LuokitteluMaarittely": {}}]
            tulokset = [{"id": 1, "vastaukset": [
                {"kohdat": ["Matematiikka", "Ohjelmointi"], "perustelu": "Opetussuunnitelman mukaan"}]}]
            llmarviointi._tallenna_tulokset(tulokset, ks, "malli")
        mock_aseta.assert_called_once_with(13, 1, "Opetussuunnitelman mukaan", "malli",
                                           pisteet=None, luokka=None,
                                           lista=["Matematiikka", "Ohjelmointi"], tiiviste=None)

    def test_lista_ei_kohtia_tallentaa_tyhjan_listan(self):
        with patch("arviointi.llmarviointi.mallit.aseta_vastaus") as mock_aseta:
            ks = [{"KysID": 13, "Luokittelu": "lista", "LuokitteluMaarittely": {}}]
            tulokset = [{"id": 1, "vastaukset": [{"kohdat": [], "perustelu": "Ei esitietoja"}]}]
            llmarviointi._tallenna_tulokset(tulokset, ks, "malli")
        mock_aseta.assert_called_once_with(13, 1, "Ei esitietoja", "malli",
                                           pisteet=None, luokka=None, lista=[], tiiviste=None)

    def test_useita_kursseja_ja_kysymyksia(self):
        with patch("arviointi.llmarviointi.mallit.aseta_vastaus") as mock_aseta:
            ks = [
                {"KysID": 10, "Luokittelu": "vapaa_teksti", "LuokitteluMaarittely": None},
                {"KysID": 11, "Luokittelu": "asteikko", "LuokitteluMaarittely": {}},
            ]
            tulokset = [
                {"id": 1, "vastaukset": ["Teksti", {"pisteet": 3, "perustelu": "OK"}]},
                {"id": 2, "vastaukset": ["Toinen", {"pisteet": 5, "perustelu": "Erinomainen"}]},
            ]
            llmarviointi._tallenna_tulokset(tulokset, ks, "m")
        assert mock_aseta.call_count == 4


class TestSiivoaTulokset:
    """Kohta 6: torju hallusinoidut/väärät id:t, säilytä vain erän kurssit."""

    def test_suodattaa_vieraan_idn(self):
        raaka = [{"id": 1, "vastaukset": []}, {"id": 999, "vastaukset": []}]
        assert llmarviointi._siivoa_tulokset(raaka, {1, 2}) == [{"id": 1, "vastaukset": []}]

    def test_normalisoi_merkkijono_idn(self):
        tulos = llmarviointi._siivoa_tulokset([{"id": "2", "vastaukset": []}], {1, 2})
        assert tulos == [{"id": 2, "vastaukset": []}]

    def test_ohittaa_puuttuvan_tai_kelvottoman_idn(self):
        raaka = [{"vastaukset": []}, {"id": None, "vastaukset": []}, {"id": "abc"}]
        assert llmarviointi._siivoa_tulokset(raaka, {1, 2}) == []
