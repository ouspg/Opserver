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
         patch("arviointi.korjaus.mallit.aseta_vastaukset") as aseta:
        tulos = korjaus.korjaa_raaka_json(1)
    return tulos, aseta


def test_korjaa_luokittelun_ja_sailyttaa_mallin_ja_tiivisteen():
    rivit = [{"VasID": 9, "KysID": 1, "KID": 5, "Malli": "gemini", "Kehotetiiviste": "abc",
              "Vastaus": '{"luokka": "Täysin", "perustelu": "Itsenäisesti suoritettavissa."}'}]
    (korjatut, ohitetut), aseta = _aja(rivit)
    assert (korjatut, ohitetut) == (1, 0)
    tid, (rivi,) = aseta.call_args.args   # (kysid, kid, vastaus, malli, pisteet, luokka, lista, tiiviste)
    assert tid == 1 and rivi[:3] == (1, 5, "Itsenäisesti suoritettavissa.")
    assert rivi[5] == "Täysin"
    assert rivi[3] == "gemini" and rivi[7] == "abc"  # alkuperäinen ajo säilyy


def test_korjaa_asteikon_ja_listan():
    rivit = [
        {"VasID": 1, "KysID": 2, "KID": 5, "Malli": "", "Kehotetiiviste": None,
         "Vastaus": '{"pisteet": 4, "perustelu": "Harjoitustöitä."}'},
        {"VasID": 2, "KysID": 3, "KID": 5, "Malli": "", "Kehotetiiviste": None,
         "Vastaus": '{"kohdat": ["Luennot", "Harjoitukset"], "perustelu": "Kaksi osaa."}'},
    ]
    (korjatut, ohitetut), aseta = _aja(rivit)
    assert (korjatut, ohitetut) == (2, 0)
    rivit = aseta.call_args.args[1]   # molemmat yhdessä kirjoituksessa
    assert rivit[0][4] == 4.0
    assert rivit[1][6] == ["Luennot", "Harjoitukset"]


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


def test_edistyminen_kutsutaan_eran_jalkeen():
    rivit = [{"VasID": i, "KysID": 1, "KID": i, "Malli": "", "Kehotetiiviste": None,
              "Vastaus": '{"luokka": "A", "perustelu": "p"}'} for i in range(1, 4)]
    havainnot = []
    with patch("arviointi.korjaus.mallit.hae_raakana_tallennetut_vastaukset", return_value=rivit), \
         patch("arviointi.korjaus.mallit.hae_kysymykset", return_value=KYSYMYKSET), \
         patch("arviointi.korjaus.mallit.aseta_vastaukset"):
        korjaus.korjaa_raaka_json(1, lambda n, yht, k, o: havainnot.append((n, yht, k, o)))
    assert havainnot == [(3, 3, 3, 0)]   # kaikki 3 yhdessä erässä
