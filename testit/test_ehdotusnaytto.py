"""Ehdotusten kuittausnäkymä (cliui/ehdotusnaytto.py) ja sen kytkentä raportin
generointiin (cliui/raporttinaytto._generoi). Logiikka ja LLM mockattu."""
import curses
from unittest.mock import patch

from cliui import ehdotusnaytto, raporttinaytto
from raportti.listanormalisointi import Ehdotus

ALAS, YLOS, ENTER, VALI, ESC = curses.KEY_DOWN, curses.KEY_UP, 10, ord(" "), 27


class FakeScr:
    def __init__(self, nappaimet, korkeus=20, leveys=100):
        self._n = iter(nappaimet)
        self.korkeus, self.leveys = korkeus, leveys
        self.kirjoitetut = []

    def getmaxyx(self):
        return (self.korkeus, self.leveys)

    def getch(self):
        return next(self._n)

    def addstr(self, y, x, teksti, *a):
        assert 0 <= y < self.korkeus and x + len(teksti) < self.leveys, (y, teksti)
        self.kirjoitetut.append((y, teksti))

    def clear(self): self.kirjoitetut = []
    def clrtoeol(self): pass
    def move(self, *a): pass
    def refresh(self): pass


def _ehdotukset(n=2):
    return [Ehdotus(11, 1, "Mikä on merkittävin menetelmä?", f"l{i}", f"K{i}") for i in range(n)]


def _aja(nappaimet, ehdotukset, muokkaus=None, korkeus=20):
    scr = FakeScr(nappaimet, korkeus=korkeus)
    with patch("cliui.ehdotusnaytto.lue_teksti", side_effect=muokkaus or (lambda *a: "")):
        return ehdotusnaytto.kuittaa_ehdotukset(scr, "Otsikko", ehdotukset), scr


class TestKuittaaEhdotukset:
    def test_hyvaksy_napista_palauttaa_kaikki_valittuina(self):
        tulos, _ = _aja([ALAS, ALAS, ENTER], _ehdotukset())
        assert [(e.lahde, e.valittu) for e in tulos] == [("l0", True), ("l1", True)]

    def test_valilyonti_poistaa_ja_palauttaa_ruksin(self):
        tulos, _ = _aja([VALI, ALAS, VALI, VALI, ALAS, ENTER], _ehdotukset())
        assert [e.valittu for e in tulos] == [False, True]

    def test_enter_muokkaa_kohdetta(self):
        tulos, _ = _aja([ALAS, ENTER, ALAS, ENTER], _ehdotukset(), muokkaus=lambda *a: " Uusi ")
        assert [(e.kohde, e.ehdotettu, e.valittu) for e in tulos] == [("K0", "K0", True), ("Uusi", "K1", True)]

    def test_tyhja_muokkaus_ei_muuta(self):
        tulos, _ = _aja([ENTER, ALAS, ALAS, ENTER], _ehdotukset(), muokkaus=lambda *a: "  ")
        assert tulos[0].kohde == "K0"

    def test_muokkaus_lahteeksi_poistaa_ruksin(self):
        tulos, _ = _aja([ENTER, ALAS, ALAS, ENTER], _ehdotukset(), muokkaus=lambda *a: "l0")
        assert (tulos[0].kohde, tulos[0].valittu) == ("l0", False)

    def test_a_vaihtaa_kaikki(self):
        tulos, _ = _aja([ord("a"), YLOS, ENTER], _ehdotukset())
        assert [e.valittu for e in tulos] == [False, False]

    def test_esc_ja_q_peruuttavat(self):
        assert _aja([ESC], _ehdotukset())[0] is None
        assert _aja([ord("q")], _ehdotukset())[0] is None

    def test_rivit_vihjeet_ja_nappi_nakyvat(self):
        _, scr = _aja([ESC], _ehdotukset())
        tekstit = [t for _, t in scr.kirjoitetut]
        assert any(t.startswith('[x] l0 --> K0 (kysymyksessä 1, "Mikä on merkittävin') for t in tekstit)
        assert any("Hyväksy" in t for t in tekstit)
        assert any("Space" in t and "Enter" in t and "Esc" in t for t in tekstit)

    def test_pitka_lista_vierittyy_ruudun_sisalla(self):
        # FakeScr.addstr kaatuu, jos rivi menee ruudun ulkopuolelle
        tulos, scr = _aja([curses.KEY_NPAGE] * 20 + [ENTER], _ehdotukset(100), korkeus=12)
        assert tulos is not None and len(tulos) == 100


class TestGeneroi:
    TUTKIMUS = {"TID": 1, "LuokittelunNimi": "T"}

    def _aja(self, kysymykset, kuittaukset, a_ehd=(), b_ehd=()):
        scr = FakeScr([ord("x")] * 5)
        kuittaus = iter(kuittaukset)
        with patch("raportti.listanormalisointi.lista_kysymykset", return_value=kysymykset), \
             patch("raportti.listanormalisointi.sovella_tallennetut", return_value=0) as sovella, \
             patch("raportti.listanormalisointi.kirjainkoko_ehdotukset", return_value=list(a_ehd)), \
             patch("raportti.listanormalisointi.tallenna_kuittaus", return_value=1) as tallenna, \
             patch("raportti.listasynonyymit.synonyymiehdotukset",
                   return_value=(list(b_ehd), {11: {"a"}}, [])) as synonyymit, \
             patch("raportti.listasynonyymit.lue_kehote", return_value="KEH"), \
             patch("cliui.raporttinaytto.kuittaa_ehdotukset", side_effect=lambda *a: next(kuittaus)) as kuittaa, \
             patch("raportti.llmraportti.aja", return_value=3) as aja:
            raporttinaytto._generoi(scr, self.TUTKIMUS)
        return {"sovella": sovella, "tallenna": tallenna, "synonyymit": synonyymit,
                "kuittaa": kuittaa, "aja": aja}

    def test_ei_lista_kysymyksia_suoraan_raporttiin(self):
        m = self._aja([], [])
        m["sovella"].assert_not_called()
        m["aja"].assert_called_once()

    def test_molemmat_vaiheet_ja_sitten_raportti(self):
        a, b = _ehdotukset(1), _ehdotukset(1)
        m = self._aja([{"KysID": 11}], [a, b], a_ehd=a, b_ehd=b)
        assert m["kuittaa"].call_count == 2
        assert m["tallenna"].call_args_list[0].args == (1, a)
        assert m["tallenna"].call_args_list[1].args == (1, b, {11: {"a"}}, "KEH")
        m["aja"].assert_called_once()

    def test_peruutus_a_vaiheessa_ei_muutoksia_eika_raporttia(self):
        m = self._aja([{"KysID": 11}], [None], a_ehd=_ehdotukset(1))
        m["tallenna"].assert_not_called()
        m["synonyymit"].assert_not_called()
        m["aja"].assert_not_called()

    def test_peruutus_b_vaiheessa_ei_raporttia(self):
        a = _ehdotukset(1)
        m = self._aja([{"KysID": 11}], [a, None], a_ehd=a, b_ehd=_ehdotukset(1))
        assert m["tallenna"].call_count == 1          # vain a)-vaiheen kuittaus
        m["aja"].assert_not_called()

    def test_ilman_ehdotuksia_kasitellyt_tallennetaan_silti(self):
        m = self._aja([{"KysID": 11}], [])
        m["kuittaa"].assert_not_called()
        m["tallenna"].assert_called_once_with(1, [], {11: {"a"}}, "KEH")
        m["aja"].assert_called_once()
