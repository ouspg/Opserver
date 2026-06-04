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

    def test_poista_korkeakoulu_kutsuu_delete(self, mock_yhteys):
        yht, kursori = mock_yhteys
        mallit.poista_korkeakoulu(1)
        kursori.execute.assert_called_once()
        sql = kursori.execute.call_args[0][0]
        assert "DELETE" in sql.upper()


class TestKurssi:
    def test_lisaa_kurssi_palauttaa_id(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.lastrowid = 7
        tulos = mallit.lisaa_kurssi(1, "Tietoturvan perusteet", "perus", "Tietojenkäsittely", 5.0, "Kuvaus tässä")
        assert tulos == 7

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
        tulos = mallit.lisaa_tutkimus("Kyber-tutkimus", "luokittelukehote", "perus,aine", "Tietojenkäsittely", "arviointikehote")
        assert tulos == 3

    def test_hae_tutkimukset_palauttaa_listan(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.fetchall.return_value = [(1, "Kyber", "kehote", "perus", "aine", "arviointikehote")]
        kursori.description = [("TID",), ("LuokittelunNimi",), ("Luokittelukehote",), ("Tasorajaus",), ("Oppiainerajaus",), ("Arviointikehote",)]
        tulos = mallit.hae_tutkimukset()
        assert len(tulos) == 1

    def test_hae_tutkimus_palauttaa_yhden(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.fetchone.return_value = (1, "Kyber", "kehote", "perus", "aine", "arviointikehote")
        kursori.description = [("TID",), ("LuokittelunNimi",), ("Luokittelukehote",), ("Tasorajaus",), ("Oppiainerajaus",), ("Arviointikehote",)]
        tulos = mallit.hae_tutkimus(1)
        assert tulos["LuokittelunNimi"] == "Kyber"


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
