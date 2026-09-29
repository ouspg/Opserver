"""Tietokantamallien testit: tutkimukset, niiden korkeakoulut, kysymykset (tietokanta/tutkimukset.py)."""
import pytest
from unittest.mock import MagicMock
from tietokanta import mallit, _yhteiset, tutkimukset


class TestTutkimus:
    def test_lisaa_tutkimus_palauttaa_id(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.lastrowid = 3
        tulos = mallit.lisaa_tutkimus("Kyber-tutkimus", "kyber-2025", "2025-2026", "luokittelukehote", "perus,aine", "Tietojenkäsittely", "arviointikehote")
        assert tulos == 3

    def test_hae_tutkimukset_palauttaa_listan(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.fetchall.return_value = [(1, "Kyber", "kyber", "kehote", "perus", "aine", "arviointikehote")]
        kursori.description = [("TID",), ("LuokittelunNimi",), ("Slug",), ("Luokittelukehote",), ("Tasorajaus",), ("Oppiainerajaus",), ("Arviointikehote",)]
        tulos = mallit.hae_tutkimukset()
        assert len(tulos) == 1

    def test_hae_tutkimus_palauttaa_yhden(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.fetchone.return_value = (1, "Kyber", "kyber", "kehote", "perus", "aine", "arviointikehote")
        kursori.description = [("TID",), ("LuokittelunNimi",), ("Slug",), ("Luokittelukehote",), ("Tasorajaus",), ("Oppiainerajaus",), ("Arviointikehote",)]
        tulos = mallit.hae_tutkimus(1)
        assert tulos["LuokittelunNimi"] == "Kyber"

    def test_hae_tutkimus_slugilla_palauttaa_yhden(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.fetchone.return_value = (1, "Kyber", "kyber", "kehote", "perus", "aine", "arviointi")
        kursori.description = [("TID",), ("LuokittelunNimi",), ("Slug",), ("Luokittelukehote",), ("Tasorajaus",), ("Oppiainerajaus",), ("Arviointikehote",)]
        tulos = mallit.hae_tutkimus_slugilla("kyber")
        assert tulos["Slug"] == "kyber"

    def test_paivita_tutkimus_tekee_update(self, mock_yhteys):
        yht, kursori = mock_yhteys
        mallit.paivita_tutkimus(1, "Uusi", "uusi-slug", "2025-2026", "uusi kehote", "perus", "aine", "uusi arviointi")
        sql = kursori.execute.call_args[0][0]
        assert "UPDATE" in sql.upper()

    def test_lisaa_tutkimus_tallentaa_verkkosivun(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.lastrowid = 5
        mallit.lisaa_tutkimus("T", "t", "2025-2026", "k", "aine", "Tieto", "a",
                              verkkosivu="https://hanke.fi")
        sql, params = kursori.execute.call_args[0]
        assert "Verkkosivu" in sql
        assert "https://hanke.fi" in params

    def test_paivita_tutkimus_tallentaa_verkkosivun(self, mock_yhteys):
        yht, kursori = mock_yhteys
        mallit.paivita_tutkimus(1, "T", "t", "2025-2026", "k", "aine", "Tieto", "a",
                                verkkosivu="https://hanke.fi")
        sql, params = kursori.execute.call_args[0]
        assert "Verkkosivu=%s" in sql
        assert "https://hanke.fi" in params

    def test_poista_tutkimus_tekee_delete(self, mock_yhteys):
        yht, kursori = mock_yhteys
        mallit.poista_tutkimus(1)
        sql = kursori.execute.call_args[0][0]
        assert "DELETE" in sql.upper()

    def test_monista_tutkimus_yhdessa_transaktiossa(self, mock_yhteys):
        """Kopio tehdään yhdellä yhteydellä (commit/rollback yhdessä) INSERT…SELECTeillä:
        kaatunut kopiointi ei jätä puolikasta tutkimusta."""
        yht, kursori = mock_yhteys
        kursori.lastrowid = 9
        assert mallit.monista_tutkimus(1, "Kopio", "kopio") == 9
        assert tutkimukset.yhteys.call_count == 1   # yksi yhteys = yksi transaktio
        sqlt = [c.args for c in kursori.execute.call_args_list]
        assert len(sqlt) == 3
        tutkimus_sql, tutkimus_p = sqlt[0]
        assert "INSERT INTO Tutkimus" in tutkimus_sql and "FROM Tutkimus WHERE TID" in tutkimus_sql
        assert tutkimus_p == ("Kopio", "kopio", 1)
        assert "INSERT INTO TutkimusKorkeakoulu" in sqlt[1][0] and sqlt[1][1] == (9, 1)
        assert "INSERT INTO Kysymykset" in sqlt[2][0] and "ORDER BY KysID" in sqlt[2][0]
        assert sqlt[2][1] == (9, 1)

    def test_monista_tutkimus_tuntematon_lahde(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.rowcount = 0
        with pytest.raises(ValueError):
            mallit.monista_tutkimus(404, "Kopio", "kopio")


class TestTutkimuksenKorkeakoulut:
    def test_aseta_korvaa_valinnan(self, mock_yhteys):
        yht, kursori = mock_yhteys
        mallit.aseta_tutkimuksen_korkeakoulut(1, [2, 3])
        sqlt = [c.args[0] for c in kursori.execute.call_args_list]
        assert any("DELETE" in s.upper() for s in sqlt)
        assert sum("INSERT" in s.upper() for s in sqlt) == 2

    def test_hae_palauttaa_kkid_listan(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.fetchall.return_value = [(2,), (3,)]
        assert mallit.hae_tutkimuksen_korkeakoulut(1) == [2, 3]


class TestKysymykset:
    def test_lisaa_kysymys_palauttaa_id(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.lastrowid = 7
        tulos = mallit.lisaa_kysymys(tid=1, kysymys="Onko kurssi pakollinen?")
        assert tulos == 7

    def test_lisaa_kysymys_luokittelulla(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.lastrowid = 8
        maarittely = {"luokat": [{"nimi": "korkea", "kuvaus": "Paljon"}]}
        mallit.lisaa_kysymys(tid=1, kysymys="Taso?", luokittelu="luokittelu", luokittelu_maarittely=maarittely)
        sql, params = kursori.execute.call_args[0]
        assert "LuokitteluMaarittely" in sql
        import json
        assert json.loads(params[3]) == maarittely

    def test_lisaa_kysymys_asteikolla(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.lastrowid = 9
        maarittely = {"minimi": 1, "maksimi": 5, "pisteet": [{"arvo": 1, "kuvaus": "Huono"}]}
        mallit.lisaa_kysymys(tid=1, kysymys="Pisteet?", luokittelu="asteikko", luokittelu_maarittely=maarittely)
        _, params = kursori.execute.call_args[0]
        assert params[2] == "asteikko"

    def test_hae_kysymykset_palauttaa_listan(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.fetchall.return_value = [(1, 1, "Onko pakollinen?"), (2, 1, "Mikä taso?")]
        kursori.description = [("KysID",), ("TID",), ("Kysymys",)]
        tulos = mallit.hae_kysymykset(1)
        assert len(tulos) == 2
        assert tulos[0]["Kysymys"] == "Onko pakollinen?"

    def test_hae_kysymykset_parsii_json_maarittelyt(self, mock_yhteys):
        yht, kursori = mock_yhteys
        import json
        maarittely = {"luokat": [{"nimi": "korkea", "kuvaus": "Paljon"}]}
        kursori.fetchall.return_value = [
            (1, 1, "Taso?", "luokittelu", json.dumps(maarittely)),
        ]
        kursori.description = [("KysID",), ("TID",), ("Kysymys",), ("Luokittelu",), ("LuokitteluMaarittely",)]
        tulos = mallit.hae_kysymykset(1)
        assert isinstance(tulos[0]["LuokitteluMaarittely"], dict)
        assert tulos[0]["LuokitteluMaarittely"]["luokat"][0]["nimi"] == "korkea"

    def test_paivita_kysymys_tekee_update(self, mock_yhteys):
        yht, kursori = mock_yhteys
        mallit.paivita_kysymys(kysid=1, kysymys="Uusi kysymys")
        sql = kursori.execute.call_args[0][0]
        assert "UPDATE" in sql.upper()

    def test_paivita_kysymys_tallentaa_luokittelun(self, mock_yhteys):
        yht, kursori = mock_yhteys
        mallit.paivita_kysymys(kysid=1, kysymys="Q", luokittelu="asteikko",
                               luokittelu_maarittely={"minimi": 1, "maksimi": 3, "pisteet": []})
        sql, params = kursori.execute.call_args[0]
        assert "Luokittelu" in sql
        assert params[1] == "asteikko"

    def test_poista_kysymys_tekee_delete(self, mock_yhteys):
        yht, kursori = mock_yhteys
        mallit.poista_kysymys(kysid=1)
        sql = kursori.execute.call_args[0][0]
        assert "DELETE" in sql.upper()

    def test_aseta_vastaukset_monirivinen_upsert(self, mock_yhteys):
        """Yksi INSERT koko erälle; TID annetaan (ei alikyselyä per rivi); lista JSONiksi."""
        yht, kursori = mock_yhteys
        mallit.aseta_vastaukset(2, [(1, 7, "Perustelu", "m", 4.0, "korkea", ["a", "b"], "t1"),
                                    (1, 8, "x", "", None, None, None, None)])
        kursori.execute.assert_called_once()
        sql, params = kursori.execute.call_args[0]
        assert "INSERT INTO Vastaukset" in sql and sql.count("(%s,%s,%s,%s,%s,%s,%s,%s,%s)") == 2
        assert params[:9] == [2, 1, 7, "Perustelu", "m", 4.0, "korkea", '["a", "b"]', "t1"]
        assert params[9:] == [2, 1, 8, "x", "", None, None, None, None]   # lista None → NULL

    def test_hae_vastaukset_parsii_lista_jsonin(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.description = [("KysID",), ("KID",), ("Lista",)]
        kursori.fetchall.return_value = [(1, 7, '["a", "b"]')]
        rivit = mallit.hae_vastaukset(tid=1)
        assert rivit[0]["Lista"] == ["a", "b"]

    def test_hae_vastausten_lkm(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.fetchone.return_value = (5,)
        tulos = mallit.hae_vastausten_lkm(kysid=1)
        assert tulos == 5
        sql, params = kursori.execute.call_args[0]
        assert "COUNT" in sql.upper()
        assert 1 in params

    def test_poista_vastaukset_kysymykselta(self, mock_yhteys):
        yht, kursori = mock_yhteys
        mallit.poista_vastaukset_kysymykselta(kysid=3)
        sql, params = kursori.execute.call_args[0]
        assert "DELETE" in sql.upper()
        assert "Vastaukset" in sql
        assert 3 in params


def test_rajaus_lukuvuosi_ja_korkeakoulut_yhdella_kyselylla():
    kursori = MagicMock()
    kursori.fetchall.return_value = [("2025-2026", 1), ("2025-2026", 3)]
    assert _yhteiset._rajaus(kursori, 1) == ("2025-2026", [1, 3])
    kursori.fetchall.return_value = [("2025-2026", None)]   # ei valittuja korkeakouluja
    assert _yhteiset._rajaus(kursori, 1) == ("2025-2026", [])
    kursori.fetchall.return_value = []                      # tuntematon tutkimus
    assert _yhteiset._rajaus(kursori, 1) == (None, [])
    assert kursori.execute.call_count == 3
