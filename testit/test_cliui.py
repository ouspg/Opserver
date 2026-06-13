"""Curses-UI testataan pääosin manuaalisesti; tässä vain savutestit."""


def test_moduulit_latautuvat():
    from cliui import valikko, korkeakoulunaytto, tutkimusnaytto, luokittelunaytto, apurit  # noqa: F401


def test_paavalikossa_viisi_kohtaa():
    from cliui import valikko
    assert len(valikko.VALIKKO) == 5


def test_korkeakoulunaytto_ops_tyypit():
    from cliui import korkeakoulunaytto
    assert korkeakoulunaytto.OPS_TYYPIT == ["Peppi", "Sisu"]


def test_tutkimusnaytto_tasot():
    from cliui import tutkimusnaytto
    assert tutkimusnaytto.TASOT == ["Yleisopinnot", "Perusopinnot", "Aineopinnot", "Syventävät opinnot"]


def test_valitse_monivalinta_on_olemassa():
    from cliui.apurit import valitse_monivalinta
    import inspect
    assert callable(valitse_monivalinta)
    params = inspect.signature(valitse_monivalinta).parameters
    assert "vaihtoehdot" in params
    assert "valitut" in params
