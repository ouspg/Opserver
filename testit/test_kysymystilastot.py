"""Testit raportti/kysymystilastot.py:lle (jaettu tilastorajapinnan ja kehotteen kesken)."""
from unittest.mock import patch

from raportti import kysymystilastot

JOUSTAVUUS = {"KysID": 2, "Kysymys": "Joustavuus?", "Luokittelu": "luokittelu", "LuokitteluMaarittely": {
    "luokat": [{"nimi": "Täysin", "kuvaus": "Kokonaan etänä"},
               {"nimi": "ei lainkaan", "kuvaus": "Kurssia ei ole mahdollista suorittaa etänä."},
               {"nimi": "ei voi päätellä", "kuvaus": "Opinto-oppaasta ei voi päätellä."}]}}
MODULAARISUUS = {"KysID": 6, "Kysymys": "Modulaarinen?", "Luokittelu": "luokittelu", "LuokitteluMaarittely": {
    "luokat": [{"nimi": "Kyllä", "kuvaus": "Useita moduuleja"},
               {"nimi": "EOS", "kuvaus": "Opinto-oppaan perusteella on hankala arvioida."}]}}
MENETELMAT = {"KysID": 1, "Kysymys": "Opetusmenetelmät?", "Luokittelu": "lista", "LuokitteluMaarittely": None}
TYO = {"KysID": 5, "Kysymys": "Työelämä?", "Luokittelu": "asteikko", "LuokitteluMaarittely": None}


def _v(kysid, kid, **kentat):
    return {"KysID": kysid, "KID": kid, "Vastaus": "p", **kentat}


def test_ei_paateltavissa_luokat_nimesta_tai_kuvauksesta():
    assert kysymystilastot.ei_paateltavissa_luokat(JOUSTAVUUS) == ["ei voi päätellä"]
    assert kysymystilastot.ei_paateltavissa_luokat(MODULAARISUUS) == ["EOS"]
    assert kysymystilastot.ei_paateltavissa_luokat({"LuokitteluMaarittely": None}) == []


def test_laske_luokittelu_ei_paateltavissa_ja_kanoniset_luokat():
    vs = [_v(2, 1, Luokka="Täysin"), _v(2, 2, Luokka="Ei voi päätellä"), _v(2, 3, Luokka="ei voi päätellä"),
          _v(2, 4, Luokka="Ei lainkaan")]
    (t,) = kysymystilastot.laske([JOUSTAVUUS], vs)
    assert t["jakauma"] == {"Täysin": 1, "ei voi päätellä": 2, "ei lainkaan": 1}
    assert t["yhteensa"] == 4 and t["ei_paateltavissa"] == 2


def test_laske_lista_viiva_on_ei_paateltavissa():
    vs = [_v(1, 1, Lista=["Luennot", "Tentti"]), _v(1, 2, Lista=["-"]), _v(1, 3, Lista=[])]
    (t,) = kysymystilastot.laske([MENETELMAT], vs)
    assert t["yhteensa"] == 2 and t["ei_paateltavissa"] == 1


def test_hae_rajaa_mukana_kursseihin():
    with patch("raportti.kysymystilastot.mallit.hae_vastaukset", return_value=[]) as hae:
        kysymystilastot.hae(7, [JOUSTAVUUS])
    hae.assert_called_once_with(7, vain_mukana=True)


def test_kehoteteksti_prosentit_ja_ei_paateltavissa():
    vs = [_v(2, k, Luokka=l) for k, l in [(1, "Täysin"), (2, "Täysin"), (3, "ei voi päätellä"), (4, "ei lainkaan")]]
    teksti = kysymystilastot.kehoteteksti(kysymystilastot.laske([JOUSTAVUUS], vs))
    assert "K1 (luokittelu): Joustavuus?" in teksti
    assert "- Täysin: 2 (50.0 %)" in teksti
    assert 'Ei pääteltävissä opinto-oppaasta ("ei voi päätellä"): 1 (25.0 %)' in teksti


def test_kehoteteksti_lista_top_n_ja_muut():
    vs = [_v(1, 1, Lista=["A", "B", "C"]), _v(1, 2, Lista=["A", "D"]), _v(1, 3, Lista=["-"])]
    teksti = kysymystilastot.kehoteteksti(kysymystilastot.laske([MENETELMAT], vs), top_n=2)
    assert "Luvut ovat mainintoja" in teksti
    assert "- A: 2 mainintaa (66.7 % kursseista)" in teksti
    assert "muita 3 eri arvoa (3 mainintaa)" in teksti
    assert 'Ei pääteltävissä opinto-oppaasta ("-"): 1 (33.3 %)' in teksti


def test_kehoteteksti_asteikko():
    vs = [_v(5, 1, Pisteet=4.0), _v(5, 2, Pisteet=2.0)]
    teksti = kysymystilastot.kehoteteksti(kysymystilastot.laske([TYO], vs))
    assert "Keskiarvo 3.0, vaihteluväli 2.0–4.0" in teksti
    assert "- 4: 1 (50.0 %)" in teksti
