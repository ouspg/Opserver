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
        self.piirretyt = []  # (y, teksti) viimeisimmästä ruudunpäivityksestä
    def getmaxyx(self):
        return (self.korkeus, self.leveys)
    def clear(self):
        self.piirretyt = []
    def addstr(self, y, x, teksti, *a):
        if not (0 <= y < self.korkeus):
            raise Exception(f"rivi ruudun ulkopuolella: {y} (korkeus {self.korkeus})")
        if x + len(teksti) > self.leveys:
            raise Exception(f"teksti yli leveyden: {x}+{len(teksti)} > {self.leveys}")
        self.piirretyt.append((y, teksti))
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


def test_valitse_listasta_kiintea_otsikko_pysyy_nakyvissa_vieritettaessa():
    import curses
    from cliui.apurit import valitse_listasta
    otsikkorivit = ["Sarake A  |  Sarake B", "---------------------"]
    vaihtoehdot = [f"rivi {i:03d}" for i in range(300)]
    # Vieritä 200 alas ja valitse; sarakeotsikon pitää näkyä riveillä 3 ja 4.
    nappaimet = [curses.KEY_DOWN] * 200 + [10]
    scr = _FakeScr(korkeus=24, leveys=80, nappaimet=nappaimet)
    tulos = valitse_listasta(scr, "Otsikko", vaihtoehdot, kiintea_otsikko=otsikkorivit)
    assert tulos == 200
    # Viimeisin ruutu: kiinteät otsikkorivit yhä paikoillaan (rivit 3 ja 4)
    rivilla = {y: t for y, t in scr.piirretyt}
    assert rivilla.get(3) == otsikkorivit[0]
    assert rivilla.get(4) == otsikkorivit[1]


def test_lisaa_korkeakoulu_selvittaa_ja_tallentaa_api_osoitteen():
    from unittest.mock import patch
    from cliui import korkeakoulunaytto as kn

    class _Scr:
        def addstr(self, *a, **k): pass
        def refresh(self): pass

    with patch.object(kn, "piirra_otsikko"), \
         patch.object(kn, "nayta_viesti"), \
         patch.object(kn, "lue_teksti", side_effect=["Testiyliopisto", "https://opas.peppi.x.fi", "kyllä"]), \
         patch.object(kn, "_valitse_ops_tyyppi", return_value="Peppi"), \
         patch.object(kn.konfiguraatio, "selvita_konfiguraatio",
                      return_value={"api_osoite": "https://opasbe.x.fi"}) as selvita, \
         patch.object(kn.mallit, "lisaa_korkeakoulu", return_value=1) as lisaa:
        kn._lisaa(_Scr())

    selvita.assert_called_once_with("https://opas.peppi.x.fi", "Peppi")
    assert lisaa.call_args.kwargs["api_osoite"] == "https://opasbe.x.fi"


def test_valitse_monivalinta_on_olemassa():
    from cliui.apurit import valitse_monivalinta
    import inspect
    assert callable(valitse_monivalinta)
    params = inspect.signature(valitse_monivalinta).parameters
    assert "vaihtoehdot" in params
    assert "valitut" in params


def test_valitse_monivalinta_ei_kirjoita_ruudun_ulkopuolelle_pitkalla_listalla():
    import curses
    from cliui.apurit import valitse_monivalinta
    vaihtoehdot = [f"{i:03d} " + "x" * 120 for i in range(300)]  # pitkä JA leveä lista
    # Liiku 200 alas, valitse (Space) ja vahvista (Enter) — ei saa kaatua
    nappaimet = [curses.KEY_DOWN] * 200 + [ord(" "), 10]
    scr = _FakeScr(korkeus=24, leveys=80, nappaimet=nappaimet)
    assert valitse_monivalinta(scr, "Otsikko", vaihtoehdot) == [vaihtoehdot[200]]
