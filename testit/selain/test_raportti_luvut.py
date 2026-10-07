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
    h = tilastot["hitl"]
    assert sivu.text_content(f"{osio} .hitl-lisatty td:nth-child(2)") == str(h["lisatty_llm"])
    assert sivu.text_content(f"{osio} .hitl-lisatty td:nth-child(3)") == str(h["lisatty_meta"])
    assert sivu.text_content(f"{osio} .hitl-poistettu td:nth-child(2)") == str(h["poistettu_llm"])
    assert sivu.text_content(f"{osio} .hitl-alkuperainen") == str(h["llm_alkuperainen"])
    assert sivu.text_content(f"{osio} .hitl-palautettu") == str(h["palautettu"])
    assert f"{h['mukana_tarkistettu']} / {h['mukana']}" in sivu.text_content(f"{osio} .hitl-kattavuus")


def test_hitl_suunta_ja_kumottu_vaihe(tilastot, kysy):
    """siemen: %50==11 LLM-hylkäys → lisätty, %50==20 meta-hylkäys → lisätty,
    %50==2 LLM-valinta → poistettu, %50==4 lisätty+poistettu → palautettu."""
    lkm = lambda j: kysy(f"SELECT COUNT(*) FROM Kurssiluokitus WHERE TID = 1 AND MOD(KID, 50) = {j}")
    h = tilastot["hitl"]
    assert (h["lisatty_llm"], h["lisatty_meta"]) == (lkm(11), lkm(20))
    assert (h["poistettu_llm"], h["poistettu_meta"]) == (lkm(2), 0)
    assert h["palautettu"] == lkm(4) > 0
    assert (h["lisatty_opas"], h["lisatty_tuntematon"], h["poistettu_llm_virhe"]) == (lkm(11), lkm(20), lkm(2))
    assert h["llm_virhe"] == lkm(2)     # palautetun kurssin llm_virhe ei ole nettomuutos
    assert h["llm_alkuperainen"] == h["mukana"] - lkm(11) - lkm(20) + lkm(2)


def test_jakauma_kokoaa_luokat_kanonisesti(tilastot):
    """siemen: KID % 20 == 1 → ' täysin ' tms., KID 10 → 'Ehkä' (tuntematon, näkyy omana luokkanaan)."""
    assert set(_kysymys(tilastot, "Joustavuus")["jakauma"]) == {"Täysin", "Osittain", "Ei lainkaan", "Ehkä"}


def test_korjaa_luokat_oikeaa_kantaa_vasten(kanta, kysy, monkeypatch):
    """Vanhojen rivien korjausajo (CLI-valikko): binäärivertailu löytää epäkanoniset,
    korjaa ne ja jättää tuntemattoman ennalleen; toinen ajo ei muuta mitään. Viimeisenä,
    koska muuttaa kantaa (tilastot-fixture on jo laskettu)."""
    from tietokanta import yhteys
    from arviointi import korjaus
    db = _db_asetukset()
    for avain, arvo in (("DB_HOST", db["host"]), ("DB_PORT", str(db["port"])), ("DB_USER", db["user"]),
                        ("DB_PASSWORD", db["password"]), ("DB_NAME", kanta)):
        monkeypatch.setenv(avain, arvo)
    monkeypatch.setattr(yhteys, "_pooli", None)
    vaarat = kysy("SELECT COUNT(*) FROM Vastaukset WHERE KysID = 2 AND Luokka COLLATE utf8mb4_bin "
                  "NOT IN ('Täysin', 'Osittain', 'Ei lainkaan', 'Ehkä')")
    korjatut, tuntemattomat = korjaus.korjaa_luokat(1)
    assert korjatut == vaarat > 0
    assert [(r["KID"], r["Luokka"]) for r in tuntemattomat] == [(10, "Ehkä")]
    assert korjaus.korjaa_luokat(1)[0] == 0
    monkeypatch.setattr(yhteys, "_pooli", None)


def test_hitl_kattavuus(tilastot, kysy):
    """Tarkistettu mukana-kurssi = hyväksytty (KayttajaNimi) tai ihmisen korjaama."""
    odotettu = kysy("SELECT COUNT(*) FROM Kurssiluokitus kl WHERE TID = 1 AND Mukana = 1 AND "
                    "(KayttajaNimi IS NOT NULL OR EXISTS (SELECT 1 FROM HitlKorjaus hk "
                    "WHERE hk.TID = 1 AND hk.KID = kl.KID))")
    assert tilastot["hitl"]["mukana_tarkistettu"] == odotettu > 0
