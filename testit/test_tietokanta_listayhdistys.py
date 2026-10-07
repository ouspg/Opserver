"""tietokanta/listayhdistys.py ilman kantaa: kyselyjen muoto etälatenssia varten.
Oikean MySQL:n käytös: testit/selain/test_listayhdistys_kanta.py."""
import json

from tietokanta import mallit
from raportti.listanormalisointi import uusi_lista


def test_arvomaarat_aggregoidaan_kannassa_binaarikollaatiolla(mock_yhteys):
    _, kursori = mock_yhteys
    kursori.description = [("KysID",), ("arvo",), ("lkm",)]
    kursori.fetchall.return_value = [(11, "ai", 2), (11, "AI", 3)]
    assert mallit.hae_lista_arvomaarat(1, [11]) == {11: {"ai": 2, "AI": 3}}
    sql, params = kursori.execute.call_args[0]
    assert "JSON_TABLE" in sql and "GROUP BY" in sql and "utf8mb4_bin" in sql
    assert params == (1, 11)


def test_arvomaarat_ilman_kysymyksia_ei_kyselya(mock_yhteys):
    _, kursori = mock_yhteys
    assert mallit.hae_lista_arvomaarat(1, []) == {}
    kursori.execute.assert_not_called()


def test_paivitys_hakee_vain_lahdearvoja_sisaltavat_ja_paivittaa_vain_muuttuvat(mock_yhteys):
    _, kursori = mock_yhteys
    kursori.fetchall.return_value = [
        (1, 11, json.dumps(["ai", "x"])),
        (2, 11, json.dumps(["AI"])),          # osuma (JSON_OVERLAPS) mutta ei muutosta
    ]
    muuttui = mallit.paivita_listat(7, {11: {"ai": "AI"}}, uusi_lista, [(11, "ai", "AI", True)], {})
    assert muuttui == 1
    lauseet = [c[0][0] for c in kursori.execute.call_args_list]
    assert "JSON_OVERLAPS" in lauseet[0] and "FOR UPDATE" in lauseet[0]
    paivitys = next(c[0] for c in kursori.execute.call_args_list if c[0][0].lstrip().startswith("UPDATE"))
    assert paivitys[1] == [1, json.dumps(["AI", "x"]), 1]
    assert any("INSERT INTO ListaYhdistys" in s for s in lauseet)
    assert not any("ListaLlmKasitelty" in s for s in lauseet)


def test_pelkat_hylkaykset_eivat_koske_vastauksiin(mock_yhteys):
    _, kursori = mock_yhteys
    assert mallit.paivita_listat(7, {}, uusi_lista, [(11, "a", "b", False)], {}) == 0
    lauseet = [c[0][0] for c in kursori.execute.call_args_list]
    assert len(lauseet) == 1 and "INSERT INTO ListaYhdistys" in lauseet[0]
