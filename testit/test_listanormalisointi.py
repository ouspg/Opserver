"""Lista-arvojen normalisointi (raportti/listanormalisointi.py): kirjainkokoryhmittely,
ketjujen ratkaisu, listan uudelleenkirjoitus ja vaiheiden orkestrointi (kanta mockattu)."""
from unittest.mock import patch

from raportti import listanormalisointi as ln
from raportti.listanormalisointi import Ehdotus

KYSYMYKSET = [
    {"KysID": 10, "Kysymys": "Mikä on kurssin vaikeustaso?", "Luokittelu": "asteikko"},
    {"KysID": 11, "Kysymys": "Mikä on merkittävin opetusmenetelmä kurssilla?", "Luokittelu": "lista"},
]


class TestValitseYleisin:
    def test_eniten_mainintoja_voittaa(self):
        assert ln.valitse_yleisin({"ai": 1, "AI": 2, "Ai": 1}) == "AI"

    def test_tasapelissa_pienin_merkkijono_koodipisteittain(self):
        # Sääntö: tasapelissä valitaan Unicode-koodipistejärjestyksessä ensimmäinen
        # → isot kirjaimet ennen pieniä ("AI" < "Ai" < "ai").
        assert ln.valitse_yleisin({"ai": 2, "AI": 2, "Ai": 2}) == "AI"
        assert ln.valitse_yleisin({"luennot": 3, "Luennot": 3}) == "Luennot"

    def test_tulos_ei_riipu_syottojarjestyksesta(self):
        a = ln.valitse_yleisin({"luennot": 3, "Luennot": 3, "LUENNOT": 1})
        b = ln.valitse_yleisin({"LUENNOT": 1, "Luennot": 3, "luennot": 3})
        assert a == b == "Luennot"


class TestKirjainkokoparit:
    def test_esimerkki_ai(self):
        # maininnat ["ai","AI","AI","Ai"] → kaikki "AI"
        parit = ln.kirjainkokoparit({"ai": 1, "AI": 2, "Ai": 1})
        assert sorted(parit) == [("Ai", "AI"), ("ai", "AI")]

    def test_yksittaiset_muodot_eivat_tuota_ehdotuksia(self):
        assert ln.kirjainkokoparit({"Luennot": 5, "Ryhmätyö": 2}) == []

    def test_useat_ryhmat(self):
        parit = ln.kirjainkokoparit({"Luennot": 5, "luennot": 2, "ryhmätyö": 3, "Ryhmätyö": 1})
        assert sorted(parit) == [("Ryhmätyö", "ryhmätyö"), ("luennot", "Luennot")]


class TestRatkaiseKetjut:
    def test_transitiivinen(self):
        assert ln.ratkaise_ketjut({"a": "b", "b": "c"}) == {"a": "c", "b": "c"}

    def test_sykli_pudotetaan(self):
        assert ln.ratkaise_ketjut({"a": "b", "b": "a", "x": "y"}) == {"x": "y"}

    def test_itseensa_osoittava_pudotetaan(self):
        assert ln.ratkaise_ketjut({"a": "a"}) == {}


class TestUusiLista:
    def test_kuvaus_ja_duplikaattien_poisto_jarjestys_sailyy(self):
        assert ln.uusi_lista(["ai", "Luennot", "AI", "Ai"], {"ai": "AI", "Ai": "AI"}) == ["AI", "Luennot"]

    def test_ei_muutosta_palauttaa_saman_sisallon(self):
        assert ln.uusi_lista(["x", "y"], {"a": "b"}) == ["x", "y"]

    def test_olemassa_olevat_duplikaatit_poistetaan_myos(self):
        assert ln.uusi_lista(["x", "x"], {}) == ["x"]

    def test_ei_merkkijonot_sailyvat(self):
        assert ln.uusi_lista(["a", 3, None], {"a": "b"}) == ["b", 3, None]

    def test_idempotentti(self):
        kuvaus = {"ai": "AI", "Ai": "AI"}
        kerran = ln.uusi_lista(["ai", "Ai", "x"], kuvaus)
        assert ln.uusi_lista(kerran, kuvaus) == kerran


class TestEhdotusRivi:
    def test_rivin_muoto(self):
        e = Ehdotus(kysid=11, kysymys_nro=1, kysymys="Mikä on merkittävin opetusmenetelmä kurssilla?",
                    lahde="ai", kohde="AI")
        assert e.rivi(40) == '[x] ai --> AI (kysymyksessä 1, "Mikä on merkittävin opetusmenetelmä kurs...")'
        e.valittu = False
        assert e.rivi().startswith("[ ] ai --> AI")

    def test_ehdotettu_oletuksena_kohde(self):
        assert Ehdotus(1, 1, "k", "a", "b").ehdotettu == "b"


class TestKuvaukset:
    def test_hyvaksytyt_tallennetuista_paatoksista_uusin_voittaa(self):
        paatokset = [
            {"KysID": 11, "Lahde": "ai", "Kohde": "Ai", "Hyvaksytty": 1},
            {"KysID": 11, "Lahde": "ai", "Kohde": "AI", "Hyvaksytty": 1},   # uudempi
            {"KysID": 11, "Lahde": "AI", "Kohde": "Tekoäly", "Hyvaksytty": 1},
            {"KysID": 11, "Lahde": "x", "Kohde": "y", "Hyvaksytty": 0},
        ]
        assert ln.tallennetut_kuvaukset(paatokset) == {11: {"ai": "Tekoäly", "AI": "Tekoäly"}}

    def test_hylatyt(self):
        paatokset = [{"KysID": 11, "Lahde": "x", "Kohde": "y", "Hyvaksytty": 0},
                     {"KysID": 11, "Lahde": "a", "Kohde": "b", "Hyvaksytty": 1}]
        assert ln.hylatyt(paatokset) == {(11, "x", "y")}


class TestListaKysymykset:
    def test_vain_lista_tyyppi_numerointi_kaikista_kysymyksista(self):
        with patch("raportti.listanormalisointi.mallit.hae_kysymykset", return_value=KYSYMYKSET):
            tulos = ln.lista_kysymykset(1)
        assert [(k["KysID"], k["nro"]) for k in tulos] == [(11, 2)]


class TestKirjainkokoVaihe:
    def _aja(self, maarat, paatokset=()):
        with patch("raportti.listanormalisointi.mallit.hae_lista_arvomaarat", return_value=maarat), \
             patch("raportti.listanormalisointi.mallit.hae_lista_paatokset", return_value=list(paatokset)):
            return ln.kirjainkoko_ehdotukset(1, [{**KYSYMYKSET[1], "nro": 2}])

    def test_ehdotukset_kysymystietoineen(self):
        ehdotukset = self._aja({11: {"ai": 1, "AI": 2, "Ai": 1}})
        assert [(e.lahde, e.kohde, e.kysymys_nro, e.valittu) for e in ehdotukset] == [
            ("Ai", "AI", 2, True), ("ai", "AI", 2, True)]

    def test_aiemmin_hylatty_ei_tule_uudelleen(self):
        ehdotukset = self._aja({11: {"ai": 1, "AI": 2, "Ai": 1}},
                               [{"KysID": 11, "Lahde": "ai", "Kohde": "AI", "Hyvaksytty": 0}])
        assert [(e.lahde, e.kohde) for e in ehdotukset] == [("Ai", "AI")]

    def test_liian_pitkat_arvot_ohitetaan(self):
        pitka = "x" * 256
        assert self._aja({11: {pitka: 1, pitka.upper(): 2}}) == []


class TestTallennaKuittaus:
    def test_hyvaksytyt_ja_hylatyt_yhteen_kirjoitukseen(self):
        ehdotukset = [
            Ehdotus(11, 2, "k", "ai", "AI"),
            Ehdotus(11, 2, "k", "Ai", "AI", valittu=False),
            Ehdotus(11, 2, "k", "luennot", "Luennot-opetus", ehdotettu="Luennot"),  # muokattu kohde
            Ehdotus(11, 2, "k", "x", "x"),                                          # muokattu = lähde
        ]
        with patch("raportti.listanormalisointi.mallit.paivita_listat", return_value=7) as paivita:
            assert ln.tallenna_kuittaus(1, ehdotukset) == 7
        tid, kuvaukset, muunna, paatokset, kasitellyt = paivita.call_args[0]
        assert tid == 1
        assert kuvaukset == {11: {"ai": "AI", "luennot": "Luennot-opetus"}}
        assert muunna is ln.uusi_lista
        assert sorted(paatokset) == sorted([
            (11, "ai", "AI", True), (11, "Ai", "AI", False),
            (11, "luennot", "Luennot-opetus", True), (11, "x", "x", False)])
        assert kasitellyt == {}

    def test_kasitellyt_tiiviste_lasketaan_kuittauksen_jalkeisista_arvoista(self):
        ehdotukset = [Ehdotus(11, 2, "k", "Luento", "Luennot")]
        with patch("raportti.listanormalisointi.mallit.paivita_listat", return_value=0) as paivita:
            ln.tallenna_kuittaus(1, ehdotukset, lahetetyt={11: {"Luento", "Luennot", "Ryhmätyö"}},
                                 kehote="K")
        kasitellyt = paivita.call_args[0][4]
        assert kasitellyt == {11: ln.arvojoukon_tiiviste({"Luennot", "Ryhmätyö"}, "K")}


class TestSovellaTallennetut:
    def test_kirjoittaa_tallennetut_kuvaukset_ilman_uusia_paatoksia(self):
        paatokset = [{"KysID": 11, "Lahde": "ai", "Kohde": "AI", "Hyvaksytty": 1}]
        with patch("raportti.listanormalisointi.mallit.hae_lista_paatokset", return_value=paatokset), \
             patch("raportti.listanormalisointi.mallit.paivita_listat", return_value=3) as paivita:
            assert ln.sovella_tallennetut(1) == 3
        paivita.assert_called_once_with(1, {11: {"ai": "AI"}}, ln.uusi_lista, [], {})

    def test_ei_paatoksia_ei_kirjoitusta(self):
        with patch("raportti.listanormalisointi.mallit.hae_lista_paatokset", return_value=[]), \
             patch("raportti.listanormalisointi.mallit.paivita_listat") as paivita:
            assert ln.sovella_tallennetut(1) == 0
        paivita.assert_not_called()


def test_arvojoukon_tiiviste_jarjestysriippumaton_ja_kehotesidonnainen():
    assert ln.arvojoukon_tiiviste({"a", "b"}, "K") == ln.arvojoukon_tiiviste(["b", "a"], "K")
    assert ln.arvojoukon_tiiviste({"a", "b"}, "K") != ln.arvojoukon_tiiviste({"a", "b"}, "L")
    assert ln.arvojoukon_tiiviste({"a"}, "K") != ln.arvojoukon_tiiviste({"a", "b"}, "K")
