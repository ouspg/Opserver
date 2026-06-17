"""Curses-UI testataan pääosin manuaalisesti; tässä vain savutestit."""


def test_moduulit_latautuvat():
    from cliui import valikko, korkeakoulunaytto, tutkimusnaytto, luokittelunaytto, apurit  # noqa: F401


def test_paavalikon_kohdat_ja_kasittelijat_tasmaavat():
    from cliui import valikko
    assert len(valikko.VALIKKO) == 7  # 6 vaihetta + LLM-asetukset
    assert valikko.VALIKKO[-1] == "A) LLM-asetukset"


def test_korkeakoulunaytto_ops_tyypit():
    from cliui import korkeakoulunaytto
    assert korkeakoulunaytto.OPS_TYYPIT == ["Peppi", "Sisu"]


def test_tutkimusnaytto_ei_hardkoodattuja_tasoja():
    from cliui import tutkimusnaytto
    assert not hasattr(tutkimusnaytto, "TASOT"), "TASOT ei saa olla hardkoodattu — haetaan tietokannasta"


class _FakeScr:
    """Mokattu curses-näyttö joka jäljittelee ruudun rajat (addstr ERR ulkopuolelle)."""
    def __init__(self, korkeus, leveys, nappaimet):
        self.korkeus, self.leveys = korkeus, leveys
        self._nappaimet = iter(nappaimet)
    def getmaxyx(self):
        return (self.korkeus, self.leveys)
    def clear(self):
        pass
    def addstr(self, y, x, teksti, *a):
        if not (0 <= y < self.korkeus):
            raise Exception(f"rivi ruudun ulkopuolella: {y} (korkeus {self.korkeus})")
        if x + len(teksti) > self.leveys:
            raise Exception(f"teksti yli leveyden: {x}+{len(teksti)} > {self.leveys}")
    def getch(self):
        return next(self._nappaimet)


def test_valitse_listasta_ei_kirjoita_ruudun_ulkopuolelle_pitkalla_listalla():
    import curses
    from cliui.apurit import valitse_listasta
    vaihtoehdot = [f"{i:03d} " + "x" * 120 for i in range(300)]  # pitkä JA leveä lista
    # Liiku 200 alas ja valitse — ei saa kaatua, palauttaa indeksin 200
    nappaimet = [curses.KEY_DOWN] * 200 + [10]
    scr = _FakeScr(korkeus=24, leveys=80, nappaimet=nappaimet)
    assert valitse_listasta(scr, "Otsikko", vaihtoehdot) == 200


def test_valitse_monivalinta_on_olemassa():
    from cliui.apurit import valitse_monivalinta
    import inspect
    assert callable(valitse_monivalinta)
    params = inspect.signature(valitse_monivalinta).parameters
    assert "vaihtoehdot" in params
    assert "valitut" in params
