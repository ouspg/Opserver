"""Tietokantamallien yhteiset apufunktiot: kyselyrungot, monirivinen INSERT, JSON-sarakkeet
sekä kurssien lukuvuosi- ja tutkimusrajauksen SQL-fragmentit."""
import json
from tietokanta.yhteys import yhteys
from luokittelu import lukuvuosi as lv


def _rivit_dikteina(kursori) -> list[dict]:
    sarakkeet = [s[0] for s in kursori.description]
    return [dict(zip(sarakkeet, rivi)) for rivi in kursori.fetchall()]


def _rivi_diktina(kursori) -> dict | None:
    if kursori.description is None:
        return None
    sarakkeet = [s[0] for s in kursori.description]
    rivi = kursori.fetchone()
    return dict(zip(sarakkeet, rivi)) if rivi else None


def _json(arvo) -> str | None:
    """Python-arvo JSON-sarakkeeseen (None → NULL)."""
    return json.dumps(arvo, ensure_ascii=False) if arvo is not None else None


def _pura_json(rivit: list[dict], kentta: str) -> list[dict]:
    """JSON-sarake takaisin Python-arvoksi (connector palauttaa sen merkkijonona)."""
    for r in rivit:
        if r.get(kentta) and isinstance(r[kentta], str):
            r[kentta] = json.loads(r[kentta])
    return rivit


# Yhden lauseen kyselyt: oma yhteys poolista (commit/rollback yhteys():ssä).
# Useamman lauseen transaktiot kirjoitetaan auki with yhteys() -lohkoon.

def _kysely(sql: str, params, tulos):
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(sql, params)
            return tulos(kursori)


def _hae_kaikki(sql: str, params=()) -> list[dict]:
    return _kysely(sql, params, _rivit_dikteina)


def _hae_yksi(sql: str, params=()) -> dict | None:
    return _kysely(sql, params, _rivi_diktina)


def _hae_arvo(sql: str, params=()):
    """Ensimmäisen rivin ensimmäinen sarake (COUNT(*) ym.)."""
    return _kysely(sql, params, lambda k: k.fetchone()[0])


def _hae_sarake(sql: str, params=()) -> list:
    return _kysely(sql, params, lambda k: [r[0] for r in k.fetchall()])


def _suorita(sql: str, params=(), *, rivimaara: bool = False) -> int:
    """Kirjoittava lause. Palauttaa lastrowid:n (rivimaara=True: rowcount)."""
    return _kysely(sql, params, lambda k: k.rowcount if rivimaara else k.lastrowid)


def _lisaa_rivit(kursori, alku: str, rivit: list[tuple], loppu: str = "", koko: int = 500) -> None:
    """Monirivinen INSERT paloittain: yksi kierros per `koko` riviä rivikohtaisen
    kutsun sijaan (etäkanta: kierros = satoja ms). Rakennetaan itse, koska
    connectorin executemany-uudelleenkirjoitus ei luotettavasti tunnista
    ON DUPLICATE KEY UPDATE ... VALUES(x) -lauseita."""
    if not rivit:
        return
    paikat = "(" + ",".join(["%s"] * len(rivit[0])) + ")"
    for i in range(0, len(rivit), koko):
        osa = rivit[i:i + koko]
        kursori.execute(f"{alku} VALUES {','.join([paikat] * len(osa))} {loppu}",
                        [arvo for rivi in osa for arvo in rivi])


# --- Kurssi ---

# OpsKuvaus on omassa taulussaan (KurssiKuvaus, migraatio 025): ainoa raskas kenttä
# (mediumtext, ka. 6,3 kB) mahtui riville, jolloin Kurssi oli ~250 MB ja jokainen
# sen läpikäyvä kysely (tilamäärät, odottaa/hylätty-listat) luki kuvaukset levyltä
# (tuotannossa 9–22 s). Kuvaus liitetään vain sitä tarvitseviin hakuihin.
_KUVAUS_JOIN = "LEFT JOIN KurssiKuvaus ku ON ku.KID = k.KID"


def _kattaa_turvallinen(ops_kausi: str | None, lukuvuosi: str) -> bool:
    """lv.kattaa, mutta virheellinen/puuttuva kausi rajataan pois (ei kaadu)."""
    if not ops_kausi:
        return False
    try:
        return lv.kattaa(ops_kausi, lukuvuosi)
    except ValueError:
        return False


# --- Vastaukset ---

# Uusi LLM-tulos korvaa vanhan ja nollaa sen hyväksynnän; jaettu testiajon siirron kanssa.
VASTAUS_PAIVITYS = """ON DUPLICATE KEY UPDATE
    Vastaus = VALUES(Vastaus), Malli = VALUES(Malli),
    Pisteet = VALUES(Pisteet), Luokka = VALUES(Luokka),
    Lista = VALUES(Lista), Kehotetiiviste = VALUES(Kehotetiiviste),
    HyvaksyjaNimi = NULL, HyvaksyjaSahkoposti = NULL"""
LUOKITUS_PAIVITYS = """ON DUPLICATE KEY UPDATE Mukana = VALUES(Mukana),
    Luokitteluperuste = VALUES(Luokitteluperuste), Malli = VALUES(Malli),
    Kehotetiiviste = VALUES(Kehotetiiviste),
    KayttajaNimi = NULL, Sahkoposti = NULL"""


# Tila-välilehden ehto Kurssiluokitus.Mukana-arvosta.
_TILA_EHTO = {"mukana": "kl.Mukana = 1", "odottaa": "kl.Mukana IS NULL", "hylätty": "kl.Mukana = 0"}


def _kurssi_suodatin_sql(kkid: int | None, taso: str | None,
                         hakusana: str | None) -> tuple[str, list]:
    """Yhteinen suodatin (yliopisto/taso/hakusana) Kurssi-alias k:lle. Hakusana
    osuu kurssin nimeen tai koodiin (osajono, kirjainkoosta riippumaton)."""
    ehdot, params = [], []
    if kkid is not None:
        ehdot.append("k.KKID = %s")
        params.append(kkid)
    if taso:
        ehdot.append("k.Taso = %s")
        params.append(taso)
    if hakusana and hakusana.strip():
        ehdot.append("(k.KurssiNimi LIKE %s OR k.Koodi LIKE %s)")
        kuvio = f"%{hakusana.strip()}%"
        params.extend([kuvio, kuvio])
    sql = (" AND " + " AND ".join(ehdot)) if ehdot else ""
    return sql, params


def _vuosi_kattaa_sql(sarake: str, lukuvuosi: str) -> tuple[str, list]:
    """SQL-ehto + parametrit: OPS-kausi kattaa lukuvuoden.

    Vertaa Kurssi-taulun generoituihin sarakkeisiin VuosiAlku/VuosiLoppu
    (migraatio 020), jotka sisältävät saman jäsennyksen kuin tämä funktio teki
    aiemmin kyselyn sisällä. Sarake funktion sisällä esti indeksin käytön, joten
    jokainen ehdokashaku ja tilannesivun kysely luki koko Kurssi-taulun
    (mitattu: 2,4 s / 26 k riviä). Nyt idx_kkid_vuosi kelpaa.

    sarake: säilytetty taulualiasta varten ("k.Opetusvuosi" → "k.VuosiAlku").
    """
    alku, loppu = lv._parsi_vuodet(lukuvuosi)
    etuliite = f"{sarake.rsplit('.', 1)[0]}." if "." in sarake else ""
    return f"{etuliite}VuosiAlku <= %s AND {etuliite}VuosiLoppu >= %s", [alku, loppu]


# Meta-suodatuksen läpäisseen (LLM:ää odottavan) kurssin Luokitteluperuste;
# LLM-päätös korvaa sen. Muut "meta:"-alkuiset perusteet ovat meta-hylkäyksiä.
META_ODOTTAA = "meta: odottaa LLM-seulontaa"


def meta_hylkays_sql(kl: str = "kl") -> str:
    """SQL-lauseke: 1 jos luokituksen päätös on meta-suodatuksen hylkäys, muuten 0
    (myös NULL-perusteelle). Peruste säilyy HITL-korjauksessa → kertoo myös, oliko
    ihmisen kumoama päätös meta-suodatuksen."""
    p = f"{kl}.Luokitteluperuste"
    return f"COALESCE(LEFT({p}, 5) = 'meta:' AND {p} <> '{META_ODOTTAA}', 0)"


def luokitus_suppilo_sql(kl: str = "kl") -> str:
    """Kurssiluokitus-rivien suppiloaggregaatit (jaettu: hae_tutkimuksen_tilanne ja
    raportin per-yliopisto-tilastot). Meta- ja LLM-päätös erotetaan
    Luokitteluperusteen "meta:"-etuliitteestä, joka säilyy HITL-korjauksessa.
    LEFT JOINilla puuttuva luokitusrivi (odottaa meta-suodatusta) ei osu mihinkään.

      Mukana       lopullinen mukana (HITL:n jälkeen)
      OdottaaLLM   meta läpäisty, LLM-päätös puuttuu
      MetaHylatty  nyt hylätty meta-suodatuksen perusteella (ks. meta_hylkays_sql)
      LLMHylatty   nyt hylätty, päätös ei meta-suodatuksen (LLM tai ihminen)
      Luokiteltu   luokitusrivejä (meta-suodatus ajettu)
      MetaHylkaama meta-suodatuksen alkuperäiset hylkäykset (myös ihmisen myöhemmin lisäämät)

    Ei %-merkkejä (LEFT(...) LIKE:n sijaan), joten sopii parametrillisiin ja
    parametrittomiin kyselyihin."""
    meta = meta_hylkays_sql(kl)
    return (f"COALESCE(SUM({kl}.Mukana = 1), 0) AS Mukana, "
            f"COALESCE(SUM({kl}.KID IS NOT NULL AND {kl}.Mukana IS NULL), 0) AS OdottaaLLM, "
            f"COALESCE(SUM({kl}.Mukana = 0 AND {meta}), 0) AS MetaHylatty, "
            f"COALESCE(SUM({kl}.Mukana = 0 AND NOT {meta}), 0) AS LLMHylatty, "
            f"COUNT({kl}.KID) AS Luokiteltu, "
            f"COALESCE(SUM({kl}.KID IS NOT NULL AND {meta}), 0) AS MetaHylkaama")


def _rajaus(kursori, tid: int) -> tuple[str | None, list[int]]:
    """Tutkimuksen (lukuvuosi, korkeakoulujen KKID:t) yhdellä kyselyllä."""
    kursori.execute(
        """SELECT t.Lukuvuosi, tk.KKID FROM Tutkimus t
           LEFT JOIN TutkimusKorkeakoulu tk ON tk.TID = t.TID
           WHERE t.TID = %s ORDER BY tk.KKID""",
        (tid,),
    )
    rivit = kursori.fetchall()
    return (rivit[0][0] if rivit else None), [r[1] for r in rivit if r[1] is not None]


def _tutkimus_kurssi_scope(tid: int) -> tuple[str, list]:
    """SQL-WHERE + parametrit jotka rajaavat Kurssi-rivit tutkimuksen korkeakouluihin
    ja lukuvuoteen (OPS-kausi kattaa lukuvuoden).

    Alikyselyinä, ei omaa kierrosta: MySQL laskee skalaarialikyselyt (perusavain-
    haku) kerran vakioiksi, joten idx_kkid_vuosi kelpaa kuten literaaleilla.
    Puuttuva lukuvuosi tai korkeakoulut → ei yhtään kurssia (kuten tilannenäkymä).
    Lukuvuosi jäsennetään kuten Kurssi.VuosiAlku/VuosiLoppu (YYYY-YYYY / YYYY-YY)."""
    alku = "CAST(SUBSTRING_INDEX(t.Lukuvuosi, '-', 1) AS UNSIGNED)"
    loppu_osa = "SUBSTRING_INDEX(t.Lukuvuosi, '-', -1)"
    loppu = (f"CASE WHEN CHAR_LENGTH({loppu_osa}) = 4 THEN CAST({loppu_osa} AS UNSIGNED) "
             f"ELSE ({alku} DIV 100) * 100 + CAST({loppu_osa} AS UNSIGNED) END")
    return (
        "k.KKID IN (SELECT tk.KKID FROM TutkimusKorkeakoulu tk WHERE tk.TID = %s)"
        f" AND k.VuosiAlku <= (SELECT {alku} FROM Tutkimus t WHERE t.TID = %s)"
        f" AND k.VuosiLoppu >= (SELECT {loppu} FROM Tutkimus t WHERE t.TID = %s)",
        [tid, tid, tid],
    )
