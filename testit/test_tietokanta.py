import pytest
from unittest.mock import MagicMock, patch, call
from tietokanta import mallit


@pytest.fixture
def mock_yhteys():
    with patch("tietokanta.mallit.yhteys") as mock:
        yht = MagicMock()
        kursori = MagicMock()
        yht.__enter__ = MagicMock(return_value=yht)
        yht.__exit__ = MagicMock(return_value=False)
        yht.cursor.return_value.__enter__ = MagicMock(return_value=kursori)
        yht.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock.return_value = yht
        yield yht, kursori


class TestKorkeakoulu:
    def test_lisaa_korkeakoulu_palauttaa_id(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.lastrowid = 42
        tulos = mallit.lisaa_korkeakoulu("Tampereen yliopisto", "https://esim.fi/ops", "Peppi")
        assert tulos == 42

    def test_lisaa_korkeakoulu_kutsuu_insert(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.lastrowid = 1
        mallit.lisaa_korkeakoulu("Tampereen yliopisto", "https://esim.fi/ops", "Peppi")
        kursori.execute.assert_called_once()
        sql = kursori.execute.call_args[0][0]
        assert "INSERT" in sql.upper()
        assert "Korkeakoulu" in sql

    def test_hae_korkeakoulut_palauttaa_listan(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.fetchall.return_value = [
            (1, "Tampereen yliopisto", "https://esim.fi/ops", "Peppi"),
        ]
        kursori.description = [("KKID",), ("KouluNimi",), ("OpsOsoite",), ("OpsTyyppi",)]
        tulos = mallit.hae_korkeakoulut()
        assert len(tulos) == 1
        assert tulos[0]["KouluNimi"] == "Tampereen yliopisto"

    def test_paivita_korkeakoulu_kutsuu_update(self, mock_yhteys):
        yht, kursori = mock_yhteys
        mallit.paivita_korkeakoulu(1, "Uusi nimi", "https://uusi.fi", "Sisu")
        kursori.execute.assert_called_once()
        sql, params = kursori.execute.call_args[0]
        assert "UPDATE" in sql.upper()
        assert "Korkeakoulu" in sql
        assert 1 in params

    def test_poista_korkeakoulu_kutsuu_delete(self, mock_yhteys):
        yht, kursori = mock_yhteys
        mallit.poista_korkeakoulu(1)
        kursori.execute.assert_called_once()
        sql = kursori.execute.call_args[0][0]
        assert "DELETE" in sql.upper()


class TestKurssi:
    def test_tallenna_kurssi_palauttaa_id(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.lastrowid = 7
        tulos = mallit.tallenna_kurssi(
            kkid=1, lahde_id="45690", koodi="IC00AU61",
            kurssi_nimi="Kyberturvallisuuden perusteet", taso="aine",
            oppiaine="Tietotekniikka", opintopisteet=5.0,
            opetusvuosi="2025-2026", ops_kuvaus='{"id":"45690"}',
        )
        assert tulos == 7

    def test_tallenna_kurssi_tekee_upsert(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.lastrowid = 7
        mallit.tallenna_kurssi(
            kkid=1, lahde_id="45690", koodi="IC00AU61",
            kurssi_nimi="Kyberturvallisuuden perusteet", taso="aine",
            oppiaine="Tietotekniikka", opintopisteet=5.0,
            opetusvuosi="2025-2026", ops_kuvaus='{}',
        )
        sql = kursori.execute.call_args[0][0]
        assert "INSERT" in sql.upper()
        assert "DUPLICATE" in sql.upper()

    def test_hae_kurssit_suodattaa_kkid_perusteella(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.fetchall.return_value = []
        kursori.description = []
        mallit.hae_kurssit(kkid=2)
        sql, params = kursori.execute.call_args[0]
        assert "KKID" in sql
        assert 2 in params

    def test_hae_kurssi_palauttaa_yhden(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.fetchone.return_value = (7, 1, "Kurssi", "perus", "Aine", 5.0, "Kuvaus")
        kursori.description = [("KID",), ("KKID",), ("KurssiNimi",), ("Taso",), ("Oppiaine",), ("Opintopisteet",), ("OpsKuvaus",)]
        tulos = mallit.hae_kurssi(7)
        assert tulos["KurssiNimi"] == "Kurssi"


class TestTutkimus:
    def test_lisaa_tutkimus_palauttaa_id(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.lastrowid = 3
        tulos = mallit.lisaa_tutkimus("Kyber-tutkimus", "kyber-2025", "luokittelukehote", "perus,aine", "Tietojenkäsittely", "arviointikehote")
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
        mallit.paivita_tutkimus(1, "Uusi", "uusi-slug", "uusi kehote", "perus", "aine", "uusi arviointi")
        sql = kursori.execute.call_args[0][0]
        assert "UPDATE" in sql.upper()

    def test_poista_tutkimus_tekee_delete(self, mock_yhteys):
        yht, kursori = mock_yhteys
        mallit.poista_tutkimus(1)
        sql = kursori.execute.call_args[0][0]
        assert "DELETE" in sql.upper()


class TestKysymykset:
    def test_lisaa_kysymys_palauttaa_id(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.lastrowid = 7
        tulos = mallit.lisaa_kysymys(tid=1, kysymys="Onko kurssi pakollinen?")
        assert tulos == 7

    def test_hae_kysymykset_palauttaa_listan(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.fetchall.return_value = [(1, 1, "Onko pakollinen?"), (2, 1, "Mikä taso?")]
        kursori.description = [("KysID",), ("TID",), ("Kysymys",)]
        tulos = mallit.hae_kysymykset(1)
        assert len(tulos) == 2
        assert tulos[0]["Kysymys"] == "Onko pakollinen?"

    def test_paivita_kysymys_tekee_update(self, mock_yhteys):
        yht, kursori = mock_yhteys
        mallit.paivita_kysymys(kysid=1, kysymys="Uusi kysymys")
        sql = kursori.execute.call_args[0][0]
        assert "UPDATE" in sql.upper()

    def test_poista_kysymys_tekee_delete(self, mock_yhteys):
        yht, kursori = mock_yhteys
        mallit.poista_kysymys(kysid=1)
        sql = kursori.execute.call_args[0][0]
        assert "DELETE" in sql.upper()

    def test_aseta_vastaus_tekee_insert(self, mock_yhteys):
        yht, kursori = mock_yhteys
        mallit.aseta_vastaus(kysid=1, kid=7, vastaus="Kyllä")
        sql = kursori.execute.call_args[0][0]
        assert "INSERT" in sql.upper()


class TestKurssiluokitus:
    def test_aseta_luokitus_tekee_insert(self, mock_yhteys):
        yht, kursori = mock_yhteys
        mallit.aseta_luokitus(tid=1, kid=7, mukana=True, perustelu="Relevantti kurssi")
        kursori.execute.assert_called_once()
        sql = kursori.execute.call_args[0][0]
        assert "INSERT" in sql.upper()

    def test_hae_luokitukset_suodattaa_tid_ja_mukana(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.fetchall.return_value = []
        kursori.description = []
        mallit.hae_luokitukset(tid=1, mukana=True)
        sql, params = kursori.execute.call_args[0]
        assert "TID" in sql
        assert "Mukana" in sql


class TestHitlKorjaus:
    def test_tallenna_hitl_korjaus_tekee_insert_ja_update(self, mock_yhteys):
        yht, kursori = mock_yhteys
        mallit.tallenna_hitl_korjaus(
            tid=1, kid=7, uusi_tila=False,
            perustelu="Ei kuulu aiheeseen", nimi="Matti", sahkoposti="matti@esim.fi",
        )
        assert kursori.execute.call_count == 2
        insert_sql = kursori.execute.call_args_list[0][0][0]
        update_sql = kursori.execute.call_args_list[1][0][0]
        assert "INSERT" in insert_sql.upper()
        assert "HitlKorjaus" in insert_sql
        assert "UPDATE" in update_sql.upper()
        assert "Kurssiluokitus" in update_sql

    def test_tallenna_hitl_korjaus_valittaa_oikeat_parametrit(self, mock_yhteys):
        yht, kursori = mock_yhteys
        mallit.tallenna_hitl_korjaus(
            tid=2, kid=9, uusi_tila=True,
            perustelu="Sopii hyvin", nimi="Liisa", sahkoposti="liisa@esim.fi",
        )
        insert_params = kursori.execute.call_args_list[0][0][1]
        assert insert_params == (2, 9, True, "Sopii hyvin", "Liisa", "liisa@esim.fi")
        update_params = kursori.execute.call_args_list[1][0][1]
        assert update_params == (True, 2, 9)


class TestKurssiarviointi:
    def test_aseta_arviointi_tekee_insert(self, mock_yhteys):
        yht, kursori = mock_yhteys
        mallit.aseta_arviointi(tid=1, kid=7, arviointi="Hyvä", perustelu="Kattava")
        kursori.execute.assert_called_once()
        sql = kursori.execute.call_args[0][0]
        assert "INSERT" in sql.upper()

    def test_hae_arvioinnit_suodattaa_tid_perusteella(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.fetchall.return_value = []
        kursori.description = []
        mallit.hae_arvioinnit(tid=1)
        sql, params = kursori.execute.call_args[0]
        assert "TID" in sql
