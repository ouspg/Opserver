"""Testit cliui/apurit.py:n puhtaille tekstiapureille (rivitys + sananavigointi)."""
from cliui import apurit


class TestRivita:
    def test_lyhyt_teksti_yhdella_rivilla(self):
        assert apurit._rivita(list("lyhyt"), 12, 80) == [0]

    def test_tyhja(self):
        assert apurit._rivita([], 0, 80) == [0]

    def test_kova_rivitys_ilman_valilyonteja(self):
        assert apurit._rivita(list("a" * 25), 0, 10) == [0, 10, 20]

    def test_rivitys_sanarajalla(self):
        # 'aaaa bbbb cccc dddd' (leveys 10) katkeaa välilyöntien kohdalta
        alut = apurit._rivita(list("aaaa bbbb cccc dddd"), 0, 10)
        assert alut[0] == 0
        assert len(alut) >= 2
        # jokaisen rivin pituus mahtuu leveyteen
        for i in range(len(alut) - 1):
            assert alut[i + 1] - alut[i] <= 10

    def test_etuliite_kaventaa_ensimmaista_rivia(self):
        # etuliite vie tilaa ensimmäiseltä riviltä → katkeaa aiemmin kuin leveys
        ilman = apurit._rivita(list("a" * 30), 0, 20)
        kanssa = apurit._rivita(list("a" * 30), 10, 20)
        assert kanssa[1] < ilman[1]


class TestSananavigointi:
    def test_sana_eteen(self):
        assert apurit._sana_eteen(list("hei maailma"), 0) == 3
        assert apurit._sana_eteen(list("hei maailma"), 3) == 11

    def test_sana_eteen_lopussa(self):
        assert apurit._sana_eteen(list("hei"), 3) == 3

    def test_sana_taakse(self):
        assert apurit._sana_taakse(list("hei maailma"), 11) == 4
        assert apurit._sana_taakse(list("hei maailma"), 4) == 0

    def test_sana_taakse_alussa(self):
        assert apurit._sana_taakse(list("hei"), 0) == 0


class TestOptionSuunta:
    def test_meta_kirjaimet(self):
        assert apurit._option_suunta("f") == 1
        assert apurit._option_suunta("b") == -1
        assert apurit._option_suunta("F") == 1
        assert apurit._option_suunta("B") == -1

    def test_csi_sekvenssit(self):
        assert apurit._option_suunta("[1;3C") == 1   # Option+oikea
        assert apurit._option_suunta("[1;3D") == -1  # Option+vasen
        assert apurit._option_suunta("[1;9C") == 1   # iTerm Esc+
        assert apurit._option_suunta("OC") == 1      # SS3-muoto

    def test_tuntematon_ja_tyhja(self):
        assert apurit._option_suunta("") == 0
        assert apurit._option_suunta("[5~") == 0
