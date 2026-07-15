"""Laiskan yhteyspoolin testit.

Ydinvaatimus: pooli EI avaa kaikkia DB_POOLI_KOKO-yhteyksiä heti (kuten
mysql.connector.MySQLConnectionPool), vaan luo ne tarvittaessa ja käyttää
palautetut uudelleen. Etäpalvelinta (Tailscale) vasten eager-luonti maksoi
~24 s ennen ensimmäistäkään kyselyä.
"""
from unittest.mock import patch, MagicMock
import threading
from tietokanta import yhteys as y


def _tee_yhteys():
    """Uusi mock-yhteys, joka näyttää elävältä ja jäljittää commit/rollback/close."""
    m = MagicMock()
    return m


def _laiska_pooli(koko=8):
    return y._LaiskaPooli(koko, {"host": "x"})


def test_ensimmainen_haku_luo_vain_yhden_yhteyden():
    with patch("tietokanta.yhteys.mysql.connector.connect", side_effect=lambda **k: _tee_yhteys()) as mc:
        pooli = _laiska_pooli()
        pooli.hae()
    assert mc.call_count == 1  # laiska: yksi kättely, ei kahdeksaa


def test_palautettu_yhteys_kaytetaan_uudelleen():
    with patch("tietokanta.yhteys.mysql.connector.connect", side_effect=lambda **k: _tee_yhteys()) as mc:
        pooli = _laiska_pooli()
        yht, pooloitu = pooli.hae()
        pooli.palauta(yht, pooloitu)
        yht2, _ = pooli.hae()
    assert mc.call_count == 1        # ei uutta kättelyä
    assert yht2 is yht               # sama yhteys


def test_katto_taynna_luo_valiaikaisen_joka_suljetaan():
    luodut = []
    with patch("tietokanta.yhteys.mysql.connector.connect",
               side_effect=lambda **k: luodut.append(_tee_yhteys()) or luodut[-1]):
        pooli = _laiska_pooli(koko=1)
        yht1, p1 = pooli.hae()           # pooliyhteys
        yht2, p2 = pooli.hae()           # katto täynnä → väliaikainen
        assert p1 is True and p2 is False
        pooli.palauta(yht2, p2)          # väliaikainen suljetaan
        yht2.close.assert_called_once()
        pooli.palauta(yht1, p1)          # pooliyhteys ei sulkeudu
        yht1.close.assert_not_called()


def test_luonti_epaonnistuu_vapauttaa_slotin():
    kutsut = {"n": 0}
    def connect(**k):
        kutsut["n"] += 1
        if kutsut["n"] == 1:
            raise RuntimeError("verkko alhaalla")
        return _tee_yhteys()
    with patch("tietokanta.yhteys.mysql.connector.connect", side_effect=connect):
        pooli = _laiska_pooli(koko=1)
        try:
            pooli.hae()
        except RuntimeError:
            pass
        # slotti vapautui → seuraava haku yrittää luoda uudelleen (ei jää jumiin)
        yht, pooloitu = pooli.hae()
        assert pooloitu is True


def test_yhteys_kontekstimanageri_commit_onnistuessa():
    yht = _tee_yhteys()
    with patch.object(y, "_hae_pooli", return_value=MagicMock(hae=lambda: (yht, True))):
        with y.yhteys() as k:
            assert k is yht
    yht.commit.assert_called_once()
    yht.rollback.assert_not_called()


def test_yhteys_kontekstimanageri_rollback_virheessa():
    yht = _tee_yhteys()
    pooli = MagicMock(hae=lambda: (yht, True))
    with patch.object(y, "_hae_pooli", return_value=pooli):
        try:
            with y.yhteys():
                raise ValueError("kysely kaatui")
        except ValueError:
            pass
    yht.rollback.assert_called_once()
    yht.commit.assert_not_called()
    pooli.palauta.assert_called_once()  # aina palautetaan


def test_rinnakkaiset_haut_eivat_ylita_kattoa():
    """koko yhteyttä lainataan yhtä aikaa → tasan koko pooliyhteyttä, loput
    väliaikaisia. Varmistaa ettei laskenta mene sekaisin lukituksessa."""
    with patch("tietokanta.yhteys.mysql.connector.connect", side_effect=lambda **k: _tee_yhteys()):
        pooli = _laiska_pooli(koko=4)
        lainat = []
        lukko = threading.Lock()

        def lainaa():
            y_, p = pooli.hae()
            with lukko:
                lainat.append(p)

        saikeet = [threading.Thread(target=lainaa) for _ in range(10)]
        for s in saikeet:
            s.start()
        for s in saikeet:
            s.join()
    assert sum(1 for p in lainat if p) == 4        # tasan koko pooloitua
    assert sum(1 for p in lainat if not p) == 6    # loput väliaikaisia
