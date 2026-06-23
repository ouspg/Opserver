"""Testit kysymysnäytön tietojen muotoilulle (tyyppi + määrittely)."""
from cliui import kysymysnaytto as k


def test_tiedot_rivit_luokittelu():
    ky = {"Kysymys": "Onko relevantti?", "Luokittelu": "luokittelu",
          "LuokitteluMaarittely": {"luokat": [{"nimi": "kyllä", "kuvaus": "on"},
                                              {"nimi": "ei", "kuvaus": "ei ole"}]}}
    rivit = k._tiedot_rivit(ky)
    yhteen = "\n".join(rivit)
    assert "Teksti:" in yhteen and "Onko relevantti?" in yhteen
    assert "Tyyppi: LUOKITUS" in yhteen
    assert "- kyllä: on" in yhteen and "- ei: ei ole" in yhteen


def test_tiedot_rivit_asteikko():
    ky = {"Kysymys": "Taso?", "Luokittelu": "asteikko",
          "LuokitteluMaarittely": {"minimi": 1, "maksimi": 5,
                                   "pisteet": [{"arvo": 1, "kuvaus": "matala"}]}}
    yhteen = "\n".join(k._tiedot_rivit(ky))
    assert "Tyyppi: ASTEIKKO" in yhteen
    assert "Asteikko 1–5" in yhteen
    assert "- 1: matala" in yhteen


def test_tiedot_rivit_vapaa_teksti_ei_maarittelya():
    ky = {"Kysymys": "Kuvaile.", "Luokittelu": "vapaa_teksti", "LuokitteluMaarittely": None}
    yhteen = "\n".join(k._tiedot_rivit(ky))
    assert "Tyyppi: TEKSTI" in yhteen
    assert "Määrittely:" not in yhteen


def test_maarittely_rivit_lista_ei_rajaa():
    assert k._maarittely_rivit("lista", {}) == ["  Kohtien yläraja: ei rajaa"]
    assert k._maarittely_rivit("lista", {"max_kohdat": 3}) == ["  Kohtien yläraja: 3"]
