"""Testit kehotetiiviste-moduulille."""
from llm import tiiviste


def test_laske_on_deterministinen():
    assert tiiviste.laske("a", "b") == tiiviste.laske("a", "b")


def test_laske_jarjestys_vaikuttaa():
    assert tiiviste.laske("a", "b") != tiiviste.laske("b", "a")


def test_laske_erotin_estaa_rajan_hamartymisen():
    # "ab"+"" ei saa tuottaa samaa kuin "a"+"b"
    assert tiiviste.laske("ab", "") != tiiviste.laske("a", "b")


def test_laske_none_ja_tyhja_samat():
    assert tiiviste.laske(None) == tiiviste.laske("")


def test_luokittelu_muuttuu_kehotteesta():
    a = tiiviste.luokittelu("kehote 1", "jarjestelma")
    b = tiiviste.luokittelu("kehote 2", "jarjestelma")
    assert a != b


def test_luokittelu_muuttuu_jarjestelmasta():
    a = tiiviste.luokittelu("kehote", "jarjestelma 1")
    b = tiiviste.luokittelu("kehote", "jarjestelma 2")
    assert a != b


def test_kysymys_sama_kun_kaikki_sama():
    kys = {"Kysymys": "Onko relevantti?", "Luokittelu": "vapaa_teksti", "LuokitteluMaarittely": None}
    a = tiiviste.kysymys("kehote", "jarj", kys)
    b = tiiviste.kysymys("kehote", "jarj", dict(kys))
    assert a == b


def test_kysymys_muuttuu_tekstista():
    k1 = {"Kysymys": "Kysymys A", "Luokittelu": "vapaa_teksti", "LuokitteluMaarittely": None}
    k2 = {"Kysymys": "Kysymys B", "Luokittelu": "vapaa_teksti", "LuokitteluMaarittely": None}
    assert tiiviste.kysymys("kehote", "jarj", k1) != tiiviste.kysymys("kehote", "jarj", k2)


def test_kysymys_muuttuu_maarittelysta():
    k1 = {"Kysymys": "Q", "Luokittelu": "asteikko", "LuokitteluMaarittely": {"minimi": 1, "maksimi": 5}}
    k2 = {"Kysymys": "Q", "Luokittelu": "asteikko", "LuokitteluMaarittely": {"minimi": 1, "maksimi": 7}}
    assert tiiviste.kysymys("kehote", "jarj", k1) != tiiviste.kysymys("kehote", "jarj", k2)


def test_kysymys_muuttuu_arviointikehotteesta():
    kys = {"Kysymys": "Q", "Luokittelu": "vapaa_teksti", "LuokitteluMaarittely": None}
    assert tiiviste.kysymys("kehote 1", "jarj", kys) != tiiviste.kysymys("kehote 2", "jarj", kys)


def test_kysymys_avainjarjestys_ei_vaikuta():
    # LuokitteluMaarittely-dictin avainjärjestys ei saa muuttaa tiivistettä
    k1 = {"Kysymys": "Q", "Luokittelu": "asteikko", "LuokitteluMaarittely": {"minimi": 1, "maksimi": 5}}
    k2 = {"Kysymys": "Q", "Luokittelu": "asteikko", "LuokitteluMaarittely": {"maksimi": 5, "minimi": 1}}
    assert tiiviste.kysymys("kehote", "jarj", k1) == tiiviste.kysymys("kehote", "jarj", k2)
