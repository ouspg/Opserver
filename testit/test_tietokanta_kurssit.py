"""Tietokantamallien testit: korkeakoulut, kurssit, lukuvuodet, tasot, oppiaineet (tietokanta/kurssit.py)."""
from unittest.mock import patch
from tietokanta import mallit


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
    def test_tallenna_kurssit_erana_kolmella_kierroksella(self, mock_yhteys):
        """Kurssit monirivisenä upsertina, KID:t yhdellä haulla, kuvaukset monirivisenä.
        OpsKuvaus omassa taulussaan (KurssiKuvaus), jotta Kurssi-rivit pysyvät kapeina."""
        yht, kursori = mock_yhteys
        kursori.fetchall.return_value = [("45690", 7), ("45691", 8)]
        kurssi = {"lahde_id": "45690", "koodi": "IC00AU61", "kurssi_nimi": "Kyberturvallisuuden perusteet",
                   "taso": "aine", "oppiaine": "Tietotekniikka", "opintopisteet": 5.0}
        mallit.tallenna_kurssit(1, "2025-2026", [
            {**kurssi, "ops_kuvaus": '{"id":"45690"}'},
            {**kurssi, "lahde_id": "45691", "ops_kuvaus": '{"id":"45691"}'},
        ])
        (kurssi_sql, kurssi_p), (hae_sql, hae_p), (kuvaus_sql, kuvaus_p) = \
            [c[0] for c in kursori.execute.call_args_list]
        assert "INSERT INTO Kurssi " in kurssi_sql and "DUPLICATE" in kurssi_sql
        assert kurssi_sql.count("(%s,%s,%s,%s,%s,%s,%s,%s)") == 2 and "OpsKuvaus" not in kurssi_sql
        assert kurssi_p[:2] == [1, "45690"] and kurssi_p[7] == "2025-2026"
        assert "LahdeId IN (%s,%s)" in hae_sql and hae_p[:2] == (1, "2025-2026")
        assert "INTO KurssiKuvaus" in kuvaus_sql and "DUPLICATE" in kuvaus_sql
        assert kuvaus_p == [7, '{"id":"45690"}', 8, '{"id":"45691"}']

    def test_tallenna_kurssit_tyhja_ei_kysele(self, mock_yhteys):
        yht, kursori = mock_yhteys
        mallit.tallenna_kurssit(1, "2025-2026", [])
        kursori.execute.assert_not_called()

    def test_hae_kurssi_liittaa_kuvauksen(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.fetchone.return_value = None
        mallit.hae_kurssi(7)
        sql = kursori.execute.call_args[0][0]
        assert "LEFT JOIN KurssiKuvaus" in sql and "OpsKuvaus" in sql

    def test_hae_kurssi_idlla_liittaa_kuvauksen(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.fetchall.return_value = []
        kursori.description = []
        mallit.hae_kurssit_idlla([4])
        sql = kursori.execute.call_args[0][0]
        assert "LEFT JOIN KurssiKuvaus" in sql and "OpsKuvaus" in sql

    def test_hae_valitut_kurssit_kuvauksin_tai_ilman(self, mock_yhteys):
        """LLM-arviointi tarvitsee kuvaukset; WebUI:n listat eivät (kuvaus vain kurssimodaalissa)."""
        yht, kursori = mock_yhteys
        kursori.fetchall.return_value = []
        kursori.description = []
        mallit.hae_valitut_kurssit(1)
        assert "LEFT JOIN KurssiKuvaus" in kursori.execute.call_args[0][0]
        mallit.hae_valitut_kurssit(1, kuvaukset=False)
        assert "KurssiKuvaus" not in kursori.execute.call_args[0][0]

    def test_hae_kurssit_suodattaa_kkid_perusteella(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.fetchall.return_value = []
        kursori.description = []
        mallit.hae_kurssit(kkid=2)
        sql, params = kursori.execute.call_args[0]
        assert "KKID" in sql
        assert 2 in params
        # Listanäkymä ei tarvitse raskasta OpsKuvaus-kenttää (248 MB koko aineistossa)
        assert "OpsKuvaus" not in sql

    def test_hae_kurssit_ei_hae_opskuvausta(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.fetchall.return_value = []
        kursori.description = []
        mallit.hae_kurssit()
        sql = kursori.execute.call_args[0][0]
        assert "OpsKuvaus" not in sql and "SELECT *" not in sql

    def test_hae_kurssi_palauttaa_yhden(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.fetchone.return_value = (7, 1, "Kurssi", "perus", "Aine", 5.0, "Kuvaus")
        kursori.description = [("KID",), ("KKID",), ("KurssiNimi",), ("Taso",), ("Oppiaine",), ("Opintopisteet",), ("OpsKuvaus",)]
        tulos = mallit.hae_kurssi(7)
        assert tulos["KurssiNimi"] == "Kurssi"


class TestLukuvuodet:
    def test_hae_lukuvuodet_kokoaa_katetut_vuodet_uusin_ensin(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.fetchall.return_value = [("2024-2027",), ("2026-27",), ("rikki",)]
        # "2024-2027" kattaa 2024-2025, 2025-2026, 2026-2027; "2026-27" -> 2026-2027; "rikki" ohitetaan
        assert mallit.hae_lukuvuodet() == ["2026-2027", "2025-2026", "2024-2025"]

    def test_hae_kurssit_suodattaa_lukuvuoden_sqlssa(self, mock_yhteys):
        """Vuosirajaus SQL:ssä (generoidut VuosiAlku/VuosiLoppu, idx_kkid_vuosi),
        ei koko luetteloa Pythoniin."""
        yht, kursori = mock_yhteys
        kursori.description = [("KID",)]
        kursori.fetchall.return_value = []
        mallit.hae_kurssit(kkid=2, lukuvuosi="2026-2027")
        sql, params = kursori.execute.call_args[0]
        assert "KKID = %s AND VuosiAlku <= %s AND VuosiLoppu >= %s" in sql
        assert list(params) == [2, 2026, 2027]

    def test_hae_kurssit_virheellinen_lukuvuosi_tyhja(self, mock_yhteys):
        yht, kursori = mock_yhteys
        assert mallit.hae_kurssit(lukuvuosi="rikki") == []
        kursori.execute.assert_not_called()

    def test_hae_meta_ehdokkaat_rajaus_ja_luokitus_samassa_kyselyssa(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.description = [("KID",)]
        kursori.fetchall.return_value = []
        with patch("tietokanta.luokitukset._rajaus", return_value=("2025-2026", [4])), \
             patch("tietokanta.luokitukset._tutkimus_kurssi_scope",
                   return_value=("k.KKID IN (%s) AND vuosirajaus", [4, 2025, 2026])):
            assert mallit.hae_meta_ehdokkaat(1) == []
        sql, params = kursori.execute.call_args[0]
        assert "LEFT JOIN Kurssiluokitus kl ON kl.KID = k.KID AND kl.TID = %s" in sql
        assert "k.KKID IN (%s) AND vuosirajaus" in sql and "OpsKuvaus" not in sql
        assert list(params) == [1, 4, 2025, 2026]
        # metasuodatus vaatii rajauksen: puuttuva lukuvuosi tai korkeakoulut → None
        for rajaus in ((None, [4]), ("2025-2026", [])):
            with patch("tietokanta.luokitukset._rajaus", return_value=rajaus):
                assert mallit.hae_meta_ehdokkaat(1) is None



class TestTasot:
    def test_ilman_rajausta(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.fetchall.return_value = [("syventävä",), ("aine",)]
        assert mallit.hae_tasot() == ["syventävä", "aine"]
        sql, params = kursori.execute.call_args[0]
        assert "k.KKID IN" not in sql and "Opetusvuosi" not in sql
        assert params == ()

    def test_rajaa_kkid_ja_lukuvuosi(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.fetchall.return_value = [("Aineopinnot",)]
        mallit.hae_tasot(kkid=4, lukuvuosi="2026-2027")
        sql, params = kursori.execute.call_args[0]
        assert "KKID = %s" in sql and "VuosiAlku <= %s" in sql
        assert list(params) == [4, 2026, 2027]


class TestKurssimaarat:
    def test_ryhmittelee_kkid_ja_opetusvuosi(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.fetchall.return_value = [
            (1, "2025-2026", 2435),
            (1, "2026-2027", 2522),
            (3, "2026-27", 625),
        ]
        tulos = mallit.hae_kurssimaarat_kouluittain()
        assert tulos == {
            1: [{"Opetusvuosi": "2025-2026", "lkm": 2435},
                {"Opetusvuosi": "2026-2027", "lkm": 2522}],
            3: [{"Opetusvuosi": "2026-27", "lkm": 625}],
        }


class TestOppiaineet:
    def test_pilkkoo_dedupoi_ja_jarjestaa_peppi(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.fetchall.return_value = [
            ("Tietotekniikka, Fysiikka", "Peppi"),
            ("Arkeologia, Kulttuuriantropologia", "Peppi"),
            ("Fysiikka", "Peppi"),      # duplikaatti
            ("", "Peppi"),              # tyhjä → ohitetaan
            (None, "Peppi"),            # NULL → ohitetaan
        ]
        tulos = mallit.hae_oppiaineet([1, 2])
        assert tulos == ["Arkeologia", "Fysiikka", "Kulttuuriantropologia", "Tietotekniikka"]
        sql, params = kursori.execute.call_args[0]
        assert "IN (%s,%s)" in sql and "KKID" in sql
        assert list(params) == [1, 2]

    def test_ei_pilko_sisun_oppiaineita(self, mock_yhteys):
        """Sisussa pilkku on osa nimeä (esim. 'LBS, Kauppatiede') — ei pilkota."""
        yht, kursori = mock_yhteys
        kursori.fetchall.return_value = [
            ("LBS, Kauppatiede", "Sisu"),
            ("Master's Programme in Russian, Eurasian and Eastern European Studies", "Sisu"),
            ("LBS, Kauppatiede", "Sisu"),  # duplikaatti
        ]
        tulos = mallit.hae_oppiaineet([4])
        assert tulos == [
            "LBS, Kauppatiede",
            "Master's Programme in Russian, Eurasian and Eastern European Studies",
        ]

    def test_sekalahteet_pilkkoo_vain_pepin(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.fetchall.return_value = [
            ("Hoitotiede, Terveyshallintotiede", "Peppi"),
            ("LENS, Tietotekniikka", "Sisu"),
        ]
        tulos = mallit.hae_oppiaineet([1, 4])
        assert tulos == ["Hoitotiede", "LENS, Tietotekniikka", "Terveyshallintotiede"]

    def test_tyhja_kkid_lista_ei_kysele(self, mock_yhteys):
        yht, kursori = mock_yhteys
        assert mallit.hae_oppiaineet([]) == []
        kursori.execute.assert_not_called()
