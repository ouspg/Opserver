"""Testierä-taulujen pysyvyys (Kurssiluokitus_testi, Vastaukset_testi).

Erillään oikeiden tulosten funktioista (mallit.py): testiajot kirjataan
ajotunnuksella (Ajo) ja voidaan poistaa kohdennetusti oikeita tuloksia
koskematta. Ks. migraatio_015.sql.
"""
import json
from tietokanta.yhteys import yhteys
from tietokanta.mallit import _rivit_dikteina


# --- Luokittelun testierät ---

def aseta_testiluokitus(ajo: str, erakoko: int, tid: int, kid: int, mukana: bool | None,
                        perustelu: str, malli: str = "", tiiviste: str | None = None) -> None:
    """Kirjaa yhden kurssin testiluokituksen. Idempotentti (Ajo, TID, KID) -avaimella."""
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                """INSERT INTO Kurssiluokitus_testi
                       (Ajo, Erakoko, TID, KID, Mukana, Luokitteluperuste, Malli, Kehotetiiviste)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE Mukana = VALUES(Mukana),
                       Luokitteluperuste = VALUES(Luokitteluperuste), Malli = VALUES(Malli),
                       Erakoko = VALUES(Erakoko), Kehotetiiviste = VALUES(Kehotetiiviste)""",
                (ajo, erakoko, tid, kid, mukana, perustelu, malli, tiiviste),
            )


def hae_siirrettavat_ajot_luokittelu(tid: int, tiiviste: str) -> list[str]:
    """Testiajot (nykyisellä kehotetiivisteellä), joiden kursseja ei vielä ole
    siirretty varsinaiseen tauluun samalla tiivisteellä → siirto säästäisi tokeneita."""
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                """SELECT DISTINCT tt.Ajo
                   FROM Kurssiluokitus_testi tt
                   LEFT JOIN Kurssiluokitus k
                     ON k.TID = tt.TID AND k.KID = tt.KID AND k.Kehotetiiviste = tt.Kehotetiiviste
                   WHERE tt.TID = %s AND tt.Kehotetiiviste = %s AND k.KLID IS NULL
                   ORDER BY tt.Ajo""",
                (tid, tiiviste),
            )
            return [r[0] for r in kursori.fetchall()]


def hae_testiajot_luokittelu(tid: int) -> list[dict]:
    """Tutkimuksen luokittelun testiajot ryhmiteltynä (uusin ensin)."""
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                """SELECT Ajo, MIN(Erakoko) AS Erakoko, COUNT(*) AS Rivit,
                          SUM(Mukana = 1) AS Mukana, MIN(Malli) AS Malli, MAX(Luotu) AS Luotu
                   FROM Kurssiluokitus_testi WHERE TID = %s
                   GROUP BY Ajo ORDER BY Ajo DESC""",
                (tid,),
            )
            return _rivit_dikteina(kursori)


def poista_testiajo_luokittelu(ajo: str) -> int:
    """Poistaa yhden luokittelun testiajon. Palauttaa poistettujen rivien määrän."""
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute("DELETE FROM Kurssiluokitus_testi WHERE Ajo = %s", (ajo,))
            return kursori.rowcount


def siirra_testiajo_luokittelu(ajo: str) -> int:
    """Siirtää testiajon luokitukset varsinaiseen Kurssiluokitus-tauluun (upsert).
    Säilyttää Kehotetiivisteen, joten siirretyt tunnistetaan ajantasaisiksi.
    Palauttaa siirrettyjen kurssien määrän."""
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute("SELECT COUNT(*) FROM Kurssiluokitus_testi WHERE Ajo = %s", (ajo,))
            maara = kursori.fetchone()[0]
            kursori.execute(
                """INSERT INTO Kurssiluokitus (TID, KID, Mukana, Luokitteluperuste, Malli, Kehotetiiviste)
                   SELECT TID, KID, Mukana, Luokitteluperuste, Malli, Kehotetiiviste
                   FROM Kurssiluokitus_testi WHERE Ajo = %s
                   ON DUPLICATE KEY UPDATE Mukana = VALUES(Mukana),
                       Luokitteluperuste = VALUES(Luokitteluperuste), Malli = VALUES(Malli),
                       Kehotetiiviste = VALUES(Kehotetiiviste)""",
                (ajo,),
            )
            return maara


# --- Arvioinnin testierät ---

def aseta_testivastaus(ajo: str, erakoko: int, tid: int, kysid: int, kid: int, vastaus: str,
                       malli: str = "", pisteet: float | None = None, luokka: str | None = None,
                       lista: list | None = None, tiiviste: str | None = None) -> None:
    """Kirjaa yhden (kysymys, kurssi) -testivastauksen. Idempotentti (Ajo, KysID, KID) -avaimella."""
    lista_json = json.dumps(lista, ensure_ascii=False) if lista is not None else None
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                """INSERT INTO Vastaukset_testi
                       (Ajo, Erakoko, TID, KysID, KID, Vastaus, Malli, Pisteet, Luokka, Lista, Kehotetiiviste)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE Vastaus = VALUES(Vastaus), Malli = VALUES(Malli),
                       Erakoko = VALUES(Erakoko), Pisteet = VALUES(Pisteet), Luokka = VALUES(Luokka),
                       Lista = VALUES(Lista), Kehotetiiviste = VALUES(Kehotetiiviste)""",
                (ajo, erakoko, tid, kysid, kid, vastaus, malli, pisteet, luokka, lista_json, tiiviste),
            )


def hae_siirrettavat_ajot_arviointi(tid: int, tiivisteet: list[str]) -> list[str]:
    """Testiajot, joiden vastauksia (nykyisillä kysymystiivisteillä) ei vielä ole
    siirretty varsinaiseen Vastaukset-tauluun → siirto säästäisi tokeneita."""
    if not tiivisteet:
        return []
    paikat = ",".join(["%s"] * len(tiivisteet))
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                f"""SELECT DISTINCT vt.Ajo
                    FROM Vastaukset_testi vt
                    LEFT JOIN Vastaukset v
                      ON v.KysID = vt.KysID AND v.KID = vt.KID AND v.Kehotetiiviste = vt.Kehotetiiviste
                    WHERE vt.TID = %s AND vt.Kehotetiiviste IN ({paikat}) AND v.VasID IS NULL
                    ORDER BY vt.Ajo""",
                (tid, *tiivisteet),
            )
            return [r[0] for r in kursori.fetchall()]


def hae_testiajot_arviointi(tid: int) -> list[dict]:
    """Tutkimuksen arvioinnin testiajot ryhmiteltynä (uusin ensin)."""
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                """SELECT Ajo, MIN(Erakoko) AS Erakoko, COUNT(*) AS Vastauksia,
                          COUNT(DISTINCT KID) AS Kursseja, MIN(Malli) AS Malli, MAX(Luotu) AS Luotu
                   FROM Vastaukset_testi WHERE TID = %s
                   GROUP BY Ajo ORDER BY Ajo DESC""",
                (tid,),
            )
            return _rivit_dikteina(kursori)


def poista_testiajo_arviointi(ajo: str) -> int:
    """Poistaa yhden arvioinnin testiajon. Palauttaa poistettujen rivien määrän."""
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute("DELETE FROM Vastaukset_testi WHERE Ajo = %s", (ajo,))
            return kursori.rowcount


def siirra_testiajo_arviointi(ajo: str) -> int:
    """Siirtää testiajon vastaukset varsinaiseen Vastaukset-tauluun (upsert).
    Säilyttää Kehotetiivisteen, joten siirretyt tunnistetaan ajantasaisiksi.
    Palauttaa siirrettyjen vastausten määrän."""
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute("SELECT COUNT(*) FROM Vastaukset_testi WHERE Ajo = %s", (ajo,))
            maara = kursori.fetchone()[0]
            kursori.execute(
                """INSERT INTO Vastaukset (KysID, KID, Vastaus, Malli, Pisteet, Luokka, Lista, Kehotetiiviste)
                   SELECT KysID, KID, Vastaus, Malli, Pisteet, Luokka, Lista, Kehotetiiviste
                   FROM Vastaukset_testi WHERE Ajo = %s
                   ON DUPLICATE KEY UPDATE Vastaus = VALUES(Vastaus), Malli = VALUES(Malli),
                       Pisteet = VALUES(Pisteet), Luokka = VALUES(Luokka),
                       Lista = VALUES(Lista), Kehotetiiviste = VALUES(Kehotetiiviste)""",
                (ajo,),
            )
            return maara
