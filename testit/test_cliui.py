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


def test_nayta_tilanne_yhdenmukainen_suppilo():
    """Tilannenäkymä esittää meta- ja LLM-vaiheet samalla suppiloperiaatteella
    kuin rajausrivit: läpäisseet päälukuna, hylätyt + odottavat suluissa."""
    from unittest.mock import patch
    from cliui import luokittelunaytto as ln

    tilanne = {
        "kursseja_yht": 42533,
        "vuosi_lapi": 33716, "vuosi_hyl": 8817,
        "oppilaitos_lapi": 33716, "oppilaitos_hyl": 0,
        "odottaa_meta": 1, "hyl_meta": 26016,
        "odottaa_llm": 1210, "hyl_llm": 6337, "hyvaksytty": 152,
    }
    scr = _FakeScr(korkeus=24, leveys=120, nappaimet=[ord("q")])
    with patch.object(ln.mallit, "hae_tutkimuksen_tilanne", return_value=tilanne), \
         patch.object(ln.mallit, "laske_arvioimattomat", return_value=162):
        ln._nayta_tilanne(scr, {"TID": 1, "LuokittelunNimi": "Testi"})
    teksti = "\n".join(t for _, t in scr.piirretyt)

    # Meta: läpäisi 33716 − 1 − 26016 = 7699; LLM: läpäisi (= hyväksytty) 152
    assert "Kursseja (metaluokitus)" in teksti and "7699" in teksti
    assert "(26016 hylätty, 1 odottaa luokitusta)" in teksti
    assert "Kursseja (LLM-luokitus)" in teksti
    assert "(6337 hylätty, 1210 odottaa luokitusta)" in teksti
    # Vanhat erilliset odottaa/hylätty-rivit poistettu
    for vanha in ("Odottaa metaluokitusta", "Hylätty metaluokituksella",
                  "Odottaa LLM-luokitusta", "Hylätty LLM-luokituksella"):
        assert vanha not in teksti


def test_aja_llm_tyhjentaa_ruudun_vahvistusvalikon_jalkeen():
    """Regressio: 'kehote muuttunut' -vahvistusvalikon jälkeen ruutu on
    tyhjennettävä (piirra_otsikko) ennen ajonäkymää, muuten valikkojäänne
    ('… uudelleen (kehote muuttui) …') jää 'Yhdistetään LLM:ään…' -rivin päälle."""
    from unittest.mock import patch
    from cliui import luokittelunaytto as ln

    class _Scr:
        def addstr(self, *a, **k): pass
        def refresh(self): pass

    tutkimus = {"TID": 1, "LuokittelunNimi": "Testi", "Luokittelukehote": "kehote"}
    tapahtumat = []

    with patch.object(ln, "piirra_otsikko", side_effect=lambda *a, **k: tapahtumat.append("otsikko")), \
         patch.object(ln, "nayta_viesti"), \
         patch.object(ln, "valitse_listasta", side_effect=lambda *a, **k: tapahtumat.append("valikko") or 0), \
         patch.object(ln.mallit, "laske_luokittelemattomat", side_effect=[1, 2]), \
         patch("luokittelu.llmluokittelu.laske_tiiviste", return_value="tiiv"), \
         patch("tietokanta.testimallit.hae_siirrettavat_ajot_luokittelu", return_value=[]), \
         patch("llm.mallitiedot.tarkista_saatavuus"), \
         patch("luokittelu.llmluokittelu.aja",
               side_effect=lambda *a, **k: tapahtumat.append("ajo") or (1, 1, 0)):
        ln._aja_llm(_Scr(), tutkimus)

    # Joukossa on piirra_otsikko, joka tulee vahvistusvalikon JÄLKEEN ja ennen ajoa.
    viim_valikko = max(i for i, t in enumerate(tapahtumat) if t == "valikko")
    ajo = tapahtumat.index("ajo")
    assert any(t == "otsikko" for t in tapahtumat[viim_valikko + 1:ajo]), tapahtumat


class TestKoostaTilanne:
    """raporttinaytto.koosta_tilanne: raportin tuoreustiedot status-sivulle."""

    TUTKIMUS = {"TID": 1, "LuokittelunNimi": "Testi"}

    def _tila(self, avaimet_ja_tiivisteet):
        return [{"OsioAvain": a, "Aikaleima": aika, "Laskentatiiviste": t}
                for a, aika, t in avaimet_ja_tiivisteet]

    def test_ei_generoitu(self):
        from unittest.mock import patch
        from cliui import raporttinaytto
        with patch.object(raporttinaytto.mallit, "hae_raportti_tila", return_value=[]):
            tulos = raporttinaytto.koosta_tilanne(self.TUTKIMUS)
        assert tulos == {"generoitu": False}

    def test_ajan_tasalla_kun_tiiviste_tasmaa(self):
        from unittest.mock import patch
        from cliui import raporttinaytto
        tila = self._tila([
            ("johdanto", "2026-07-15 10:00:00", "abc"),
            ("kurssit", "2026-07-15 10:00:05", "abc"),
            ("arvioinnit", "2026-07-15 10:00:10", "abc"),
        ])
        with patch.object(raporttinaytto.mallit, "hae_raportti_tila", return_value=tila), \
             patch.object(raporttinaytto.mallit, "laske_hitl_korjaukset_jalkeen", return_value=0), \
             patch.object(raporttinaytto.mallit, "laske_arviokommentit_jalkeen", return_value=0), \
             patch("raportti.llmraportti.raporttitiiviste", return_value="abc"):
            tulos = raporttinaytto.koosta_tilanne(self.TUTKIMUS)
        assert tulos["generoitu"] is True
        assert tulos["tuoreus"] == "ajan_tasalla"
        assert tulos["puuttuu"] == []
        assert tulos["generoitu_aika"] == "2026-07-15 10:00:00"  # varhaisin

    def test_vanhentunut_kun_tiiviste_eroaa(self):
        from unittest.mock import patch
        from cliui import raporttinaytto
        tila = self._tila([("johdanto", "2026-07-15 10:00:00", "vanha")])
        with patch.object(raporttinaytto.mallit, "hae_raportti_tila", return_value=tila), \
             patch.object(raporttinaytto.mallit, "laske_hitl_korjaukset_jalkeen", return_value=2), \
             patch.object(raporttinaytto.mallit, "laske_arviokommentit_jalkeen", return_value=1), \
             patch("raportti.llmraportti.raporttitiiviste", return_value="uusi"):
            tulos = raporttinaytto.koosta_tilanne(self.TUTKIMUS)
        assert tulos["tuoreus"] == "vanhentunut"
        assert tulos["hitl_jalkeen"] == 2
        assert tulos["kommentit_jalkeen"] == 1

    def test_tuntematon_kun_tiiviste_puuttuu(self):
        """Ennen tuoreusseurantaa generoitu raportti (Laskentatiiviste NULL)."""
        from unittest.mock import patch
        from cliui import raporttinaytto
        tila = self._tila([("johdanto", "2026-07-15 10:00:00", None)])
        with patch.object(raporttinaytto.mallit, "hae_raportti_tila", return_value=tila), \
             patch.object(raporttinaytto.mallit, "laske_hitl_korjaukset_jalkeen", return_value=0), \
             patch.object(raporttinaytto.mallit, "laske_arviokommentit_jalkeen", return_value=0), \
             patch("raportti.llmraportti.raporttitiiviste", return_value="x"):
            tulos = raporttinaytto.koosta_tilanne(self.TUTKIMUS)
        assert tulos["tuoreus"] == "tuntematon"

    def test_puuttuva_osio_listataan(self):
        from unittest.mock import patch
        from cliui import raporttinaytto
        tila = self._tila([
            ("johdanto", "2026-07-15 10:00:00", "abc"),
            ("kurssit", "2026-07-15 10:00:05", "abc"),
        ])
        with patch.object(raporttinaytto.mallit, "hae_raportti_tila", return_value=tila), \
             patch.object(raporttinaytto.mallit, "laske_hitl_korjaukset_jalkeen", return_value=0), \
             patch.object(raporttinaytto.mallit, "laske_arviokommentit_jalkeen", return_value=0), \
             patch("raportti.llmraportti.raporttitiiviste", return_value="abc"):
            tulos = raporttinaytto.koosta_tilanne(self.TUTKIMUS)
        assert tulos["puuttuu"] == ["arvioinnit"]
