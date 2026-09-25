"""Testit raaka-JSON-vastausten korjaukselle."""
from unittest.mock import patch
from arviointi import korjaus


KYSYMYKSET = [
    {"KysID": 1, "Kysymys": "luokittelukysymys", "Luokittelu": "luokittelu"},
    {"KysID": 2, "Kysymys": "asteikkokysymys", "Luokittelu": "asteikko"},
    {"KysID": 3, "Kysymys": "listakysymys", "Luokittelu": "lista"},
]


def _aja(rivit):
    with patch("arviointi.korjaus.mallit.hae_raakana_tallennetut_vastaukset", return_value=rivit), \
         patch("arviointi.korjaus.mallit.hae_kysymykset", return_value=KYSYMYKSET), \
         patch("arviointi.korjaus.mallit.aseta_vastaus") as aseta:
        tulos = korjaus.korjaa_raaka_json(1)
    return tulos, aseta


def test_korjaa_luokittelun_ja_sailyttaa_mallin_ja_tiivisteen():
    rivit = [{"VasID": 9, "KysID": 1, "KID": 5, "Malli": "gemini", "Kehotetiiviste": "abc",
              "Vastaus": '{"luokka": "Täysin", "perustelu": "Itsenäisesti suoritettavissa."}'}]
    (korjatut, ohitetut), aseta = _aja(rivit)
    assert (korjatut, ohitetut) == (1, 0)
    args, kwargs = aseta.call_args
    assert args[:3] == (1, 5, "Itsenäisesti suoritettavissa.")
    assert kwargs["luokka"] == "Täysin"
    assert args[3] == "gemini" and kwargs["tiiviste"] == "abc"  # alkuperäinen ajo säilyy


def test_korjaa_asteikon_ja_listan():
    rivit = [
        {"VasID": 1, "KysID": 2, "KID": 5, "Malli": "", "Kehotetiiviste": None,
         "Vastaus": '{"pisteet": 4, "perustelu": "Harjoitustöitä."}'},
        {"VasID": 2, "KysID": 3, "KID": 5, "Malli": "", "Kehotetiiviste": None,
         "Vastaus": '{"kohdat": ["Luennot", "Harjoitukset"], "perustelu": "Kaksi osaa."}'},
    ]
    (korjatut, ohitetut), aseta = _aja(rivit)
    assert (korjatut, ohitetut) == (2, 0)
    assert aseta.call_args_list[0].kwargs["pisteet"] == 4.0
    assert aseta.call_args_list[1].kwargs["lista"] == ["Luennot", "Harjoitukset"]


def test_katkennut_json_ohitetaan_eika_teksti_katoa():
    """Jäsentymätöntä ei kirjoiteta uusiksi — säilynyt teksti on parempi kuin tyhjä."""
    rivit = [{"VasID": 1, "KysID": 1, "KID": 5, "Malli": "", "Kehotetiiviste": None,
              "Vastaus": '{katkennut json'}]
    (korjatut, ohitetut), aseta = _aja(rivit)
    assert (korjatut, ohitetut) == (0, 1)
    aseta.assert_not_called()


def test_ei_korjattavaa_ei_kirjoita_mitaan():
    (korjatut, ohitetut), aseta = _aja([])
    assert (korjatut, ohitetut) == (0, 0)
    aseta.assert_not_called()


def test_edistyminen_kutsutaan_jokaisesta_rivista():
    rivit = [{"VasID": i, "KysID": 1, "KID": i, "Malli": "", "Kehotetiiviste": None,
              "Vastaus": '{"luokka": "A", "perustelu": "p"}'} for i in range(1, 4)]
    havainnot = []
    with patch("arviointi.korjaus.mallit.hae_raakana_tallennetut_vastaukset", return_value=rivit), \
         patch("arviointi.korjaus.mallit.hae_kysymykset", return_value=KYSYMYKSET), \
         patch("arviointi.korjaus.mallit.aseta_vastaus"):
        korjaus.korjaa_raaka_json(1, lambda n, yht, k, o: havainnot.append((n, yht, k, o)))
    assert havainnot == [(1, 3, 1, 0), (2, 3, 2, 0), (3, 3, 3, 0)]
