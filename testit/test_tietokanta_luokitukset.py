"""Tietokantamallien testit: luokittelu, luokitusnäkymät, suppilo, HITL-korjaukset (tietokanta/luokitukset.py)."""
from unittest.mock import patch
from tietokanta import mallit


class TestLaskeLuokittelemattomat:
    """Lukumäärä lasketaan COUNT(*):lla — ei haeta rivejä (raskas OpsKuvaus)
    pelkkää laskentaa varten, mikä hidasti LLM-näkymän avaamista."""

    def test_uudet_ja_vanhentuneet_yhdella_countilla(self, mock_yhteys):
        """Uudet + vanhentuneet yhdellä kyselyllä (ennen kaksi COUNT-kierrosta)."""
        yht, kursori = mock_yhteys
        kursori.fetchone.return_value = (10, 7)   # kaikki, uudet
        with patch("tietokanta.luokitukset._tutkimus_kurssi_scope", return_value=("k.KKID IN (%s)", [5])):
            assert mallit.laske_luokittelutyo(1, "tiiv-x") == (7, 3)
        kursori.execute.assert_called_once()
        sql, params = kursori.execute.call_args[0]
        assert "COUNT(*)" in sql and "SUM(kl.KID IS NULL OR kl.Mukana IS NULL)" in sql
        assert "k.*" not in sql and "OpsKuvaus" not in sql and "ORDER BY" not in sql
        assert "Kehotetiiviste" in sql and "k.KKID IN" in sql
        assert list(params) == [1, "tiiv-x", 1, 5]


class TestHaeTutkimuksenTilanne:
    """Suppilo lasketaan SQL-aggregaateilla yhdessä yhteydessä (ei vedä kaikkia
    kursseja/luokituksia Pythoniin) — etäpalvelimella siirtomäärä ratkaisee."""

    def test_kokoaa_suppilon_aggregaateista(self, mock_yhteys):
        yht, kursori = mock_yhteys
        # järjestys: COUNT(*) Kurssi, (rajaus), kurssi-agg, luokitus-agg
        kursori.fetchone.side_effect = [(100,), (80, 65), (10, 5, 30, 15, 60)]
        with patch("tietokanta.luokitukset._rajaus", return_value=("2025-2026", [1, 2])):
            t = mallit.hae_tutkimuksen_tilanne(1)
        assert t == {
            "kursseja_yht": 100,
            "vuosi_lapi": 80, "vuosi_hyl": 20,
            "oppilaitos_lapi": 65, "oppilaitos_hyl": 15,
            "odottaa_meta": 5,          # in_scope 65 − luok 60
            "hyl_meta": 30, "odottaa_llm": 5, "hyl_llm": 15, "hyvaksytty": 10,
        }

    def test_ilman_lukuvuotta_kaikki_vuosihylattyja(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.fetchone.side_effect = [(100,)]   # kursseja_yht
        kursori.fetchall.return_value = [(None, None)]   # lukuvuosi=NULL, ei korkeakouluja
        t = mallit.hae_tutkimuksen_tilanne(1)
        assert t["kursseja_yht"] == 100 and t["vuosi_hyl"] == 100
        assert t["vuosi_lapi"] == 0 and t["hyvaksytty"] == 0


class TestHaeLuokittelemattomat:
    """LLM-luokittelun ehdokasjoukon täytyy noudattaa tutkimuksen rajausta
    (lukuvuosi + korkeakoulut) samoin kuin meta-suodatus ja tilastopaneeli —
    muuten rajauksen ulkopuoliset kurssit päätyisivät LLM-ajoon."""

    def test_soveltaa_tutkimuksen_rajausta(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.fetchone.return_value = (0,)
        with patch("tietokanta.luokitukset._tutkimus_kurssi_scope",
                   return_value=("k.KKID IN (%s,%s) AND vuosirajaus", [2, 3, 2024, 2025])):
            mallit.hae_luokittelemattomat_kevyet(1)
        sql, params = kursori.execute.call_args[0]
        assert "k.KKID IN" in sql and "vuosirajaus" in sql
        # rajausparametrit threadattu JOIN-tid:n jälkeen, oikeassa järjestyksessä
        assert list(params) == [1, 2, 3, 2024, 2025]

    def test_tiivisteella_soveltaa_rajausta_ja_threadaa_parametrit(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.fetchone.return_value = (0,)
        with patch("tietokanta.luokitukset._tutkimus_kurssi_scope",
                   return_value=("k.KKID IN (%s)", [5])):
            mallit.hae_luokittelemattomat_kevyet(1, "tiiv-abc")
        sql, params = kursori.execute.call_args[0]
        assert "k.KKID IN" in sql and "Kehotetiiviste" in sql
        # tid (JOIN), tiiviste (<=>), tid (EXISTS), sitten rajausparametrit
        assert list(params) == [1, "tiiv-abc", 1, 5]

    def test_ei_hae_opskuvausta_koko_joukolle(self, mock_yhteys):
        """Ehdokaslista ilman OpsKuvausta: koko joukko kuvauksineen on kymmeniä
        megatavuja (mitattu 7 696 riviä / 51 MB), ja sen nouto kerralla jumitti
        LLM-näytön. Kuvaukset haetaan erä kerrallaan (hae_kurssit_idlla)."""
        yht, kursori = mock_yhteys
        kursori.fetchone.return_value = (0,)
        mallit.hae_luokittelemattomat_kevyet(1)
        sql = kursori.execute.call_args[0][0]
        assert "OpsKuvaus" not in sql and "SELECT k.*" not in sql
        assert "ORDER BY k.KurssiNimi" not in sql  # filesort koko joukolle

    def test_hae_kurssit_idlla_on_perusavainhaku(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.fetchall.return_value = []
        kursori.description = []
        mallit.hae_kurssit_idlla([4, 7])
        sql, params = kursori.execute.call_args[0]
        assert "WHERE k.KID IN (%s,%s)" in sql
        assert list(params) == [4, 7]

    def test_hae_kurssit_idlla_tyhjalla_ei_kysele(self, mock_yhteys):
        yht, kursori = mock_yhteys
        assert mallit.hae_kurssit_idlla([]) == []
        kursori.execute.assert_not_called()


class TestKurssitLuokituksilla:
    def test_rajaa_korkeakouluihin_ja_lukuvuoteen_sqlssa(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.description = [("KID",)]
        kursori.fetchall.return_value = [(1,)]
        mallit.hae_kurssit_luokituksilla(1)
        kursori.execute.assert_called_once()      # rajaus alikyselyinä, ei omaa kierrosta
        sql, params = kursori.execute.call_args[0]
        assert "k.KKID IN (SELECT tk.KKID FROM TutkimusKorkeakoulu tk WHERE tk.TID = %s)" in sql
        assert "k.VuosiAlku <= (SELECT" in sql and "k.VuosiLoppu >= (SELECT" in sql
        assert list(params) == [1, 1, 1, 1]       # JOIN-TID + korkeakoulut, alku, loppu

    def test_tila_ja_sivutus(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.description = [("KID",)]
        kursori.fetchall.return_value = []
        mallit.hae_kurssit_luokituksilla(1, tila="hylätty", sivu=2, koko=100)
        sql, params = kursori.execute.call_args[0]
        assert "kl.Mukana = 0" in sql and "LIMIT %s OFFSET %s" in sql
        assert params[-2:] == (100, 200)  # koko, sivu*koko


class TestTilamaarat:
    def test_ryhmittelee_tiloittain(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.fetchall.return_value = [(1, 74), (None, 2526), (0, 31112)]
        m = mallit.hae_tutkimuksen_tilamaarat(1)
        assert m == {"mukana": 74, "odottaa": 2526, "hylätty": 31112}


class TestTutkimuksenTilanne:
    def test_funnel_jakaa_kurssit_vaiheittain(self, mock_yhteys):
        """7 kurssin skenaario: 6 vuosirajaus läpi, 5 in-scope, näistä
        hyväksytty/odottaa/meta-hyl/LLM-hyl/odottaa-meta yksi kutakin. Aggregaatti-
        SQL:n TUOTTAMAT luvut on syötetty kursorille; testaa Python-kokoonpanon.
        (SQL:n semantiikka varmennettu erikseen MySQL:ää vasten.)"""
        yht, kursori = mock_yhteys
        # järjestys: COUNT(*) Kurssi, rajaus (fetchall), kurssi-agg, luokitus-agg
        kursori.fetchone.side_effect = [(7,), (6, 5), (1, 1, 1, 1, 4)]
        kursori.fetchall.return_value = [("2025-2026", 1)]
        t = mallit.hae_tutkimuksen_tilanne(1)
        assert t["kursseja_yht"] == 7
        assert (t["vuosi_lapi"], t["vuosi_hyl"]) == (6, 1)
        assert (t["oppilaitos_lapi"], t["oppilaitos_hyl"]) == (5, 1)
        assert t["odottaa_meta"] == 1        # in_scope 5 − luok 4
        assert (t["hyl_meta"], t["odottaa_llm"], t["hyl_llm"], t["hyvaksytty"]) == (1, 1, 1, 1)
        # in-scope-summa täsmää
        assert (t["odottaa_meta"] + t["hyl_meta"] + t["odottaa_llm"]
                + t["hyl_llm"] + t["hyvaksytty"]) == t["oppilaitos_lapi"]


class TestKurssiluokitus:
    def test_aseta_luokitukset_monirivinen_upsert(self, mock_yhteys):
        yht, kursori = mock_yhteys
        mallit.aseta_luokitukset(1, [(7, True, "Relevantti"), (8, None, "meta: odottaa")], "m", tiiviste="t")
        kursori.execute.assert_called_once()
        sql, params = kursori.execute.call_args[0]
        assert "INSERT INTO Kurssiluokitus" in sql and sql.count("(%s,%s,%s,%s,%s,%s)") == 2
        assert params == [1, 7, True, "Relevantti", "m", "t", 1, 8, None, "meta: odottaa", "m", "t"]

    def test_aseta_luokitukset_paloittain(self, mock_yhteys):
        """Iso erä pilkotaan (paketin koko), mutta yksi kierros per 500 riviä."""
        yht, kursori = mock_yhteys
        mallit.aseta_luokitukset(1, [(k, False, "x") for k in range(1201)])
        assert kursori.execute.call_count == 3

    def test_hae_luokitukset_suodattaa_tid_ja_mukana(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.fetchall.return_value = []
        kursori.description = []
        mallit.hae_luokitukset(tid=1, mukana=True)
        sql, params = kursori.execute.call_args[0]
        assert "TID" in sql
        assert "Mukana" in sql

    def test_laske_luokitukset_mukana_count_ei_riveja(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.fetchone.return_value = (12,)
        assert mallit.laske_luokitukset(1, mukana=True) == 12
        sql, params = kursori.execute.call_args[0]
        assert "COUNT(*)" in sql and "Mukana = %s" in sql
        assert list(params) == [1, True]

    def test_laske_luokitukset_ilman_mukana(self, mock_yhteys):
        yht, kursori = mock_yhteys
        kursori.fetchone.return_value = (30,)
        assert mallit.laske_luokitukset(1) == 30
        sql, params = kursori.execute.call_args[0]
        assert "COUNT(*)" in sql and "Mukana" not in sql
        assert list(params) == [1]

    def test_aseta_luokitus_nollaa_hyvaksynnan(self, mock_yhteys):
        """LLM:n uusi päätös ei peri vanhan päätöksen peukutusta."""
        yht, kursori = mock_yhteys
        mallit.aseta_luokitukset(1, [(7, True, "x")])
        sql = kursori.execute.call_args[0][0]
        assert "KayttajaNimi = NULL" in sql and "Sahkoposti = NULL" in sql

    def test_hyvaksy_luokitus_vain_mukana_oleville(self, mock_yhteys):
        yht, kursori = mock_yhteys
        mallit.hyvaksy_luokitus(2, 9, "Liisa", "")
        sql, params = kursori.execute.call_args[0]
        assert "UPDATE Kurssiluokitus" in sql and "Mukana = 1" in sql
        assert params == ("Liisa", None, 2, 9)

    def test_aseta_vastaus_nollaa_hyvaksynnan(self, mock_yhteys):
        """LLM:n uusi vastaus ei peri vanhan vastauksen peukutusta."""
        yht, kursori = mock_yhteys
        mallit.aseta_vastaukset(1, [(3, 7, "x", "m", None, None, None, None)])
        sql = kursori.execute.call_args[0][0]
        assert "HyvaksyjaNimi = NULL" in sql and "HyvaksyjaSahkoposti = NULL" in sql

    def test_hyvaksy_vastaus_vain_llm_riville(self, mock_yhteys):
        yht, kursori = mock_yhteys
        mallit.hyvaksy_vastaus(1, 7, 3, "Liisa", "l@e.fi")
        sql, params = kursori.execute.call_args[0]
        assert "UPDATE Vastaukset" in sql and "Malli IS NOT NULL" in sql
        assert params == ("Liisa", "l@e.fi", 1, 7, 3)


class TestHitlKorjaus:
    def test_tallenna_hitl_korjaus_tekee_insert_ja_update(self, mock_yhteys):
        yht, kursori = mock_yhteys
        mallit.tallenna_hitl_korjaus(
            tid=1, kid=7, uusi_tila=False,
            perustelu="Ei kuulu aiheeseen", nimi="Matti", sahkoposti="matti@esim.fi",
            juurisyy="llm_virhe",
        )
        assert kursori.execute.call_count == 2
        insert_sql = kursori.execute.call_args_list[0][0][0]
        update_sql = kursori.execute.call_args_list[1][0][0]
        assert "INSERT" in insert_sql.upper()
        assert "HitlKorjaus" in insert_sql
        assert "Juurisyy" in insert_sql
        assert "UPDATE" in update_sql.upper()
        assert "Kurssiluokitus" in update_sql

    def test_tallenna_hitl_korjaus_on_idempotentti(self, mock_yhteys):
        """WebUI lähettää pyynnön uudelleen jos vastaus katoaa → sama korjaus ei
        saa tuplata historiariviä (vääristäisi HITL-tilastot)."""
        yht, kursori = mock_yhteys
        mallit.tallenna_hitl_korjaus(tid=2, kid=9, uusi_tila=True, perustelu="p",
                                     nimi="Liisa", sahkoposti="l@e.fi")
        sql, params = kursori.execute.call_args_list[0][0]
        assert "NOT EXISTS" in sql and "ORDER BY HID DESC LIMIT 1" in sql
        assert params[7:] == (2, 9, True, "p", "Liisa")

    def test_tallenna_hitl_korjaus_valittaa_oikeat_parametrit(self, mock_yhteys):
        yht, kursori = mock_yhteys
        mallit.tallenna_hitl_korjaus(
            tid=2, kid=9, uusi_tila=True,
            perustelu="Sopii hyvin", nimi="Liisa", sahkoposti="liisa@esim.fi",
            juurisyy="riittamaton_opas",
        )
        insert_params = kursori.execute.call_args_list[0][0][1]
        assert insert_params[:7] == (2, 9, True, "Sopii hyvin", "Liisa", "liisa@esim.fi",
                                     "riittamaton_opas")
        update_params = kursori.execute.call_args_list[1][0][1]
        assert update_params == (True, 2, 9)

    def test_tallenna_hitl_korjaus_juurisyy_oletuksena_none(self, mock_yhteys):
        """Juurisyy on valinnainen malliparametri (vanhat kutsut, NULL kannassa)."""
        yht, kursori = mock_yhteys
        mallit.tallenna_hitl_korjaus(
            tid=3, kid=4, uusi_tila=False,
            perustelu="x", nimi="N", sahkoposti="n@esim.fi",
        )
        insert_params = kursori.execute.call_args_list[0][0][1]
        assert insert_params[6] is None

    def test_JUURISYYT_sisaltaa_kaksi_taksonomia_arvoa(self):
        assert set(mallit.JUURISYYT) == {"riittamaton_opas", "llm_virhe"}


def test_hitl_historia_rajataan_sivun_kursseihin(mock_yhteys):
    yht, kursori = mock_yhteys
    kursori.description = [("KID",)]
    kursori.fetchall.return_value = []
    mallit.hae_hitl_historia(1, [4, 7])
    sql, params = kursori.execute.call_args[0]
    assert "TID = %s AND KID IN (%s,%s)" in sql and list(params) == [1, 4, 7]
    kursori.execute.reset_mock()
    assert mallit.hae_hitl_historia(1, []) == []
    kursori.execute.assert_not_called()
