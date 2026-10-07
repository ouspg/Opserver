"""Raportin luvut oikeaa MySQL:ää vasten (tilastorajapinta, ei selainta): siemen.py:n
_raportin_poikkeamat antaa meta-hylätyt, HITL-korjaukset molempiin suuntiin, palautetun
kurssin ja epäkanoniset luokat."""
import json
import urllib.request

import pytest

from testit.selain.conftest import SLUG, _db_asetukset


@pytest.fixture(scope="module")
def tilastot(pohja):
    with urllib.request.urlopen(f"{pohja}/api/tutkimukset/{SLUG}/raportti/tilastot", timeout=30) as v:
        return json.load(v)


@pytest.fixture(scope="module")
def kysy(kanta):
    import mysql.connector
    yht = mysql.connector.connect(**_db_asetukset(), database=kanta)

    def arvo(sql):
        kursori = yht.cursor()
        kursori.execute(sql)
        return kursori.fetchone()[0]
    yield arvo
    yht.close()


def _kysymys(tilastot, alku):
    return next(k for k in tilastot["kysymykset"] if k["kysymys"].startswith(alku))


def test_tilastot_vain_nykyisista_mukana_kursseista(tilastot, kysy):
    """HITL:ssä poistetun kurssin vanhat vastaukset jäävät kantaan, mutta eivät tilastoihin."""
    mukana = kysy("SELECT COUNT(*) FROM Kurssiluokitus WHERE TID = 1 AND Mukana = 1")
    poistettujen_vastauksia = kysy("SELECT COUNT(*) FROM Vastaukset v JOIN Kurssiluokitus kl "
                                   "ON kl.KID = v.KID AND kl.TID = 1 AND kl.Mukana = 0 WHERE v.KysID = 5")
    assert poistettujen_vastauksia > 0
    assert _kysymys(tilastot, "Mitä muuta")["yhteensa"] == mukana
    assert _kysymys(tilastot, "Työelämälähtöisyys")["yhteensa"] == mukana
    assert _kysymys(tilastot, "Joustavuus")["yhteensa"] == mukana


def test_suppilo_erottelee_meta_hylkaamat(tilastot, kysy):
    """Meta-hylkäämät (myös ihmisen myöhemmin lisäämät) eivät ole 'LLM:n käsittelemiä'."""
    meta = kysy("SELECT COUNT(*) FROM Kurssiluokitus WHERE TID = 1 AND Luokitteluperuste LIKE 'meta:%' "
                "AND Luokitteluperuste <> 'meta: odottaa LLM-seulontaa'")
    kaikki = kysy("SELECT COUNT(*) FROM Kurssiluokitus WHERE TID = 1")
    s = tilastot["suppilo"]
    assert s["meta_hylkaama"] == meta > 0
    assert s["llm_lle"] == kaikki - meta
    assert s["odottaa_llm"] == kysy("SELECT COUNT(*) FROM Kurssiluokitus WHERE TID = 1 AND Mukana IS NULL") > 0
    assert s["llm_kasitelty"] == s["llm_lle"] - s["odottaa_llm"]
    assert s["mukana"] == kysy("SELECT COUNT(*) FROM Kurssiluokitus WHERE TID = 1 AND Mukana = 1")
    assert tilastot["hitl"]["llm_kasitelty"] == s["llm_kasitelty"]


def test_raporttinakyma_nayttaa_suppilon(kayttaja, tilastot):
    sivu = kayttaja(f"/tutkimukset/{SLUG}/raportti", ".raportti-osio[data-avain=kurssit] .suppilo-taulu")
    osio = ".raportti-osio[data-avain=kurssit]"
    for luokka, avain in (("suppilo-meta", "meta_hylkaama"), ("suppilo-llm", "llm_lle"),
                          ("suppilo-mukana", "mukana")):
        assert sivu.text_content(f"{osio} .{luokka} td:last-child") == str(tilastot["suppilo"][avain])
    assert "nimittäjänä meta-suodatuksen läpäisseet" in sivu.text_content(f"{osio} .hitl-mittarit")
