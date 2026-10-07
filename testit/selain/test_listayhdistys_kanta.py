"""Lista-arvojen yhdistäminen oikeaa MySQL:ää vasten (ei selainta): JSON_TABLE-määrät
binäärisellä kollaatiolla, JSON_OVERLAPS-rajattu uudelleenkirjoitus, päätösten
tallennus ja idempotenssi. Ajetaan ./testit/selaintesti.sh:lla (oma kertakäyttökanta)."""
import json

import pytest

from testit.selain.conftest import _db_asetukset

TID = 2


@pytest.fixture
def db(kanta, monkeypatch):
    """tietokanta.yhteys ajon kantaan + oma tutkimus (TID 2), joka siivotaan lopuksi."""
    import mysql.connector
    from tietokanta import yhteys
    asetukset = _db_asetukset()
    for avain, arvo in (("DB_HOST", asetukset["host"]), ("DB_PORT", str(asetukset["port"])),
                        ("DB_USER", asetukset["user"]), ("DB_PASSWORD", asetukset["password"]),
                        ("DB_NAME", kanta)):
        monkeypatch.setenv(avain, arvo)
    monkeypatch.setattr(yhteys, "_pooli", None)
    yht = mysql.connector.connect(**asetukset, database=kanta, autocommit=True)
    k = yht.cursor()
    k.execute("INSERT INTO Tutkimus (TID, LuokittelunNimi, Slug, Luokittelukehote, Arviointikehote) "
              "VALUES (%s, 'Listatesti', 'listatesti', '', '')", (TID,))
    k.execute("INSERT INTO Kysymykset (TID, Kysymys, Luokittelu) VALUES (%s, 'Menetelmät?', 'lista')", (TID,))
    kysid = k.lastrowid

    def vastaus(kid, lista, kayttaja=""):
        k.execute("INSERT INTO Vastaukset (TID, KysID, KID, Vastaus, Lista, Malli, KayttajaNimi, Kehotetiiviste) "
                  "VALUES (%s, %s, %s, '', %s, %s, %s, 'kt')",
                  (TID, kysid, kid, json.dumps(lista, ensure_ascii=False),
                   None if kayttaja else "malli", kayttaja))

    def listat():
        k.execute("SELECT KID, KayttajaNimi, Lista FROM Vastaukset WHERE TID = %s ORDER BY KID, KayttajaNimi", (TID,))
        return {(kid, nimi): json.loads(l) for kid, nimi, l in k.fetchall()}

    def kysy(sql, params=()):
        k.execute(sql, params)
        return k.fetchall()

    vastaus(1, ["ai", "Luennot"])
    vastaus(2, ["AI", "AI", "luennot"])
    vastaus(3, ["Ai", "Ryhmätyö"])
    vastaus(3, ["ai", "Ryhmätyöt"], kayttaja="Ihminen")   # HITL-rivi samalle kurssille
    vastaus(4, ["Muu"])
    try:
        yield {"kysid": kysid, "listat": listat, "kysy": kysy}
    finally:
        k.execute("DELETE FROM Tutkimus WHERE TID = %s", (TID,))
        yht.close()


def test_arvomaarat_erottavat_kirjainkoon(db):
    from tietokanta import mallit
    maarat = mallit.hae_lista_arvomaarat(TID, [db["kysid"]])[db["kysid"]]
    assert maarat == {"ai": 2, "AI": 2, "Ai": 1, "Luennot": 1, "luennot": 1,
                      "Ryhmätyö": 1, "Ryhmätyöt": 1, "Muu": 1}


def test_kuittaus_kirjoittaa_listat_ja_paatokset_idempotentisti(db):
    from raportti import listanormalisointi as ln
    kysid = db["kysid"]
    aikaleimat = db["kysy"]("SELECT VasID, Aikaleima, Kehotetiiviste FROM Vastaukset WHERE TID = %s", (TID,))
    ehdotukset = [ln.Ehdotus(kysid, 1, "k", "ai", "AI"), ln.Ehdotus(kysid, 1, "k", "Ai", "AI"),
                  ln.Ehdotus(kysid, 1, "k", "luennot", "Luennot", valittu=False)]
    assert ln.tallenna_kuittaus(TID, ehdotukset) == 3   # kurssit 1, 3 (LLM) ja 3 (HITL)
    assert db["listat"]() == {
        (1, ""): ["AI", "Luennot"],
        (2, ""): ["AI", "AI", "luennot"],          # ei lähdearvoja → ei kosketa (vanhat duplikaatit jäävät)
        (3, ""): ["AI", "Ryhmätyö"],
        (3, "Ihminen"): ["AI", "Ryhmätyöt"],
        (4, ""): ["Muu"],
    }
    # Normalisointi ei ole uusi vastaus: aikaleima ja kehotetiiviste säilyvät
    assert db["kysy"]("SELECT VasID, Aikaleima, Kehotetiiviste FROM Vastaukset WHERE TID = %s", (TID,)) == aikaleimat
    assert sorted(db["kysy"]("SELECT Lahde, Kohde, Hyvaksytty FROM ListaYhdistys WHERE KysID = %s", (kysid,))) == [
        ("Ai", "AI", 1), ("ai", "AI", 1), ("luennot", "Luennot", 0)]
    # Toinen kuittaus samoilla ehdotuksilla: ei muutettavaa, ei tuplarivejä
    assert ln.tallenna_kuittaus(TID, ehdotukset) == 0
    assert db["kysy"]("SELECT COUNT(*) FROM ListaYhdistys WHERE KysID = %s", (kysid,)) == [(3,)]
    # Hylätty muistetaan: a)-vaihe ei ehdota sitä uudelleen
    jaljella = ln.kirjainkoko_ehdotukset(TID, [{"KysID": kysid, "nro": 1, "Kysymys": "k"}])
    assert [(e.lahde, e.kohde) for e in jaljella] == []


def test_tallennetut_sovelletaan_uudelleenajon_jalkeen(db):
    from raportti import listanormalisointi as ln
    kysid = db["kysid"]
    ln.tallenna_kuittaus(TID, [ln.Ehdotus(kysid, 1, "k", "ai", "AI"),
                               ln.Ehdotus(kysid, 1, "k", "Ryhmätyöt", "Ryhmätyö")])
    # Arviointien uudelleenajo tuottaa taas raa'an arvon
    db["kysy"]("UPDATE Vastaukset SET Lista = JSON_ARRAY('ai', 'Muu') WHERE TID = %s AND KID = 4", (TID,))
    assert ln.sovella_tallennetut(TID) == 1
    assert db["listat"]()[(4, "")] == ["AI", "Muu"]
    assert ln.sovella_tallennetut(TID) == 0


def test_uusi_hyvaksynta_korvaa_saman_lahteen_vanhan(db):
    from tietokanta import mallit
    from raportti import listanormalisointi as ln
    kysid = db["kysid"]
    ln.tallenna_kuittaus(TID, [ln.Ehdotus(kysid, 1, "k", "Muu", "Muut")])
    ln.tallenna_kuittaus(TID, [ln.Ehdotus(kysid, 1, "k", "Muu", "Jokin muu")])
    hyvaksytyt = [p for p in mallit.hae_lista_paatokset(TID) if p["Hyvaksytty"]]
    assert [(p["Lahde"], p["Kohde"]) for p in hyvaksytyt] == [("Muu", "Jokin muu")]


def test_llm_kasitellyt_tallentuvat(db):
    from tietokanta import mallit
    from raportti import listanormalisointi as ln
    kysid = db["kysid"]
    ln.tallenna_kuittaus(TID, [], lahetetyt={kysid: {"Muu"}}, kehote="K")
    assert mallit.hae_llm_kasitellyt(TID) == {kysid: ln.arvojoukon_tiiviste({"Muu"}, "K")}
    ln.tallenna_kuittaus(TID, [], lahetetyt={kysid: {"Muu", "X"}}, kehote="K")
    assert mallit.hae_llm_kasitellyt(TID) == {kysid: ln.arvojoukon_tiiviste({"Muu", "X"}, "K")}


def test_yhdistaminen_muuttaa_raportin_tuoreustietoa(db):
    """raporttitiiviste lukee listan MD5:n hae_vastaus_tiivisteet-kyselystä."""
    from tietokanta import mallit
    from raportti import listanormalisointi as ln
    ennen = mallit.hae_vastaus_tiivisteet(TID)
    ln.tallenna_kuittaus(TID, [ln.Ehdotus(db["kysid"], 1, "k", "Muu", "Muut")])
    jalkeen = mallit.hae_vastaus_tiivisteet(TID)
    assert ennen[(4, db["kysid"])]["lista"] != jalkeen[(4, db["kysid"])]["lista"]
    assert ennen[(1, db["kysid"])] == jalkeen[(1, db["kysid"])]
