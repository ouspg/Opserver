"""Kurssien luokittelu (meta + LLM), luokitusnäkymät, tutkimuksen suppilo ja HITL-korjaukset."""
from tietokanta.yhteys import yhteys
from tietokanta._yhteiset import (
    LUOKITUS_PAIVITYS, _TILA_EHTO, _hae_kaikki, _kurssi_suodatin_sql, _kysely, _lisaa_rivit,
    _rajaus, _rivit_dikteina, _suorita, _tutkimus_kurssi_scope, _vuosi_kattaa_sql,
)


# --- Luokittelun apufunktiot ---

def _luokittelemattomat_ehto(tid: int, tiiviste: str | None) -> tuple[str, tuple]:
    """Jaettu FROM+JOIN+WHERE + parametrit luokittelemattomille kursseille.

    Aina mukana: kurssit joilla ei ole luokitusriviä tai Mukana IS NULL
    (meta-suodatuksen läpäisseet, jotka odottavat LLM:ää). Jos tiiviste annetaan:
    lisäksi aiemmin LLM-luokitellut kurssit, joiden tallennettu Kehotetiiviste
    eroaa nykyisestä (kehote muuttunut), pois lukien ihmisen HITL-korjaamat.

    Ehdokkaat rajataan tutkimuksen lukuvuoteen ja korkeakouluihin samoin kuin
    meta-suodatuksessa — muuten rajauksen ulkopuoliset kurssit (väärä vuosi /
    korkeakoulu) joutuisivat LLM-ajoon, koska niillä ei ole meta-riviä.
    """
    scope_where, sp = _tutkimus_kurssi_scope(tid)
    scope_sql = f" AND {scope_where}"
    if tiiviste is None:
        ehto = f"""
            FROM Kurssi k
            LEFT JOIN Kurssiluokitus kl ON k.KID = kl.KID AND kl.TID = %s
            WHERE (kl.KID IS NULL OR kl.Mukana IS NULL){scope_sql}
        """
        return ehto, (tid, *sp)
    ehto = f"""
        FROM Kurssi k
        LEFT JOIN Kurssiluokitus kl ON k.KID = kl.KID AND kl.TID = %s
        WHERE (kl.KID IS NULL
           OR kl.Mukana IS NULL
           OR (kl.Kehotetiiviste IS NOT NULL
               AND NOT (kl.Kehotetiiviste <=> %s)
               AND NOT EXISTS (SELECT 1 FROM HitlKorjaus h
                               WHERE h.TID = %s AND h.KID = k.KID))){scope_sql}
    """
    return ehto, (tid, tiiviste, tid, *sp)


# Kurssin kentät ilman OpsKuvausta: ainoa raskas kenttä (mediumtext, ka. 6,3 kB
# / rivi, omassa taulussaan) haetaan erä kerrallaan (hae_kurssit_idlla).
_KEVYET_SARAKKEET = ("KID", "KKID", "LahdeId", "Koodi", "KurssiNimi",
                     "Taso", "Oppiaine", "Opintopisteet", "Opetusvuosi")


def hae_luokittelemattomat_kevyet(tid: int, tiiviste: str | None = None) -> list[dict]:
    """LLM-seulontaa odottavat kurssit ilman OpsKuvausta. Ehto: _luokittelemattomat_ehto.

    Koko ehdokasjoukko OpsKuvauksineen on kymmeniä megatavuja (mitattu: 7 696
    riviä / 51 MB kehotetiivisteen muuttuessa), ja sen nouto kerralla jumitti
    LLM-näytön ennen ensimmäistäkään LLM-kutsua. Kevyt lista kaikista (~1 MB)
    riittää erien muodostamiseen ja edistymislaskentaan; LLM-kutsuun tarvittava
    kuvausteksti haetaan erä kerrallaan (hae_kurssit).

    ORDER BY KID (ei KurssiNimi): järjestys vaikuttaa vain erien ryhmittelyyn,
    eikä nimen mukaiselle lajittelulle ole indeksiä → filesort koko joukolle.
    """
    ehto, params = _luokittelemattomat_ehto(tid, tiiviste)
    sarakkeet = ", ".join(f"k.{s}" for s in _KEVYET_SARAKKEET)
    return _hae_kaikki(f"SELECT {sarakkeet} {ehto} ORDER BY k.KID", params)


def laske_luokittelutyo(tid: int, tiiviste: str) -> tuple[int, int]:
    """(uudet, vanhentuneet): vielä LLM-luokittelemattomat ja vanhentuneen kehotteen
    tulokset yhdellä COUNT-kyselyllä (ei rivinoutoa, ei kahta kierrosta)."""
    ehto, params = _luokittelemattomat_ehto(tid, tiiviste)
    kaikki, uudet = _kysely(f"SELECT COUNT(*), COALESCE(SUM(kl.KID IS NULL OR kl.Mukana IS NULL), 0) {ehto}",
                            params, lambda k: k.fetchone())
    return int(uudet), int(kaikki) - int(uudet)


def hae_meta_ehdokkaat(tid: int) -> list[dict] | None:
    """Tutkimuksen rajauksen (korkeakoulut + lukuvuosi) kurssit meta-suodatusta varten,
    nykyinen luokitus liitettynä (Luokiteltu, Mukana, Luokitteluperuste). Vain
    suodatuksen tarvitsemat sarakkeet. None jos rajaus puuttuu."""
    with yhteys() as yht:
        with yht.cursor() as kursori:
            lukuvuosi, korkeakoulut = _rajaus(kursori, tid)
    if not lukuvuosi or not korkeakoulut:
        return None
    where, params = _tutkimus_kurssi_scope(tid)
    return _hae_kaikki(
        f"""SELECT k.KID, k.Taso, k.Oppiaine, kl.KID IS NOT NULL AS Luokiteltu,
                   kl.Mukana, kl.Luokitteluperuste
            FROM Kurssi k
            LEFT JOIN Kurssiluokitus kl ON kl.KID = k.KID AND kl.TID = %s
            WHERE {where}""",
        (tid, *params),
    )


def hae_tutkimuksen_tilamaarat(tid: int, kkid: int | None = None, taso: str | None = None,
                               hakusana: str | None = None) -> dict:
    """Tutkimuksen kurssimäärät tiloittain (mukana/odottaa/hylätty), rajattuna
    korkeakouluihin ja lukuvuoteen. Valinnainen yliopisto/taso/hakusana-suodatus
    (samat kuin listauksessa, jotta välilehtien luvut vastaavat näkymää)."""
    maarat = {"mukana": 0, "odottaa": 0, "hylätty": 0}
    where, params = _tutkimus_kurssi_scope(tid)
    suod_sql, suod_params = _kurssi_suodatin_sql(kkid, taso, hakusana)
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                f"SELECT kl.Mukana, COUNT(*) FROM Kurssi k "
                f"LEFT JOIN Kurssiluokitus kl ON k.KID = kl.KID AND kl.TID = %s "
                f"WHERE {where}{suod_sql} GROUP BY kl.Mukana",
                (tid, *params, *suod_params),
            )
            for mukana, n in kursori.fetchall():
                if mukana is None:
                    maarat["odottaa"] = n
                elif mukana == 1:
                    maarat["mukana"] = n
                else:
                    maarat["hylätty"] = n
    return maarat


# Sallitut järjestyssarakkeet (WebUI ▲▼-napit) — valkolista suojaa SQL-injektiolta.
_LUOKITUS_JARJESTYS = {
    "nimi": "k.KurssiNimi", "koodi": "k.Koodi", "taso": "k.Taso",
    "oppiaine": "k.Oppiaine", "op": "k.Opintopisteet",
}


def hae_kurssit_luokituksilla(tid: int, tila: str | None = None,
                              sivu: int = 0, koko: int | None = None,
                              kkid: int | None = None, taso: str | None = None,
                              hakusana: str | None = None,
                              jarjesta: str | None = None,
                              suunta: str | None = None) -> list[dict]:
    """Tutkimuksen kurssit luokitustiloineen — rajattuna korkeakouluihin ja
    lukuvuoteen. Valinnainen tila-välilehti (mukana/odottaa/hylätty), sivutus
    (koko=None palauttaa kaikki), yliopisto/taso/hakusana-suodatus sekä
    sarakejärjestys (jarjesta = valkolistattu sarake, suunta = nouseva/laskeva).
    """
    where, params = _tutkimus_kurssi_scope(tid)
    tila_sql = f" AND {_TILA_EHTO[tila]}" if tila in _TILA_EHTO else ""
    suod_sql, suod_params = _kurssi_suodatin_sql(kkid, taso, hakusana)
    sarake_sql = _LUOKITUS_JARJESTYS.get(jarjesta or "", "k.KurssiNimi")
    suunta_sql = "DESC" if (suunta or "").lower() == "laskeva" else "ASC"
    jarj_sql = f" ORDER BY {sarake_sql} {suunta_sql}, k.KurssiNimi"
    raja_sql, raja_params = "", []
    if koko:
        raja_sql = " LIMIT %s OFFSET %s"
        raja_params = [koko, max(0, sivu) * koko]
    return _hae_kaikki(
        f"SELECT k.KID, k.KKID, k.LahdeId, k.KurssiNimi, k.Koodi, k.Taso, k.Oppiaine, "
        f"k.Opintopisteet, k.Opetusvuosi, kl.Mukana, kl.Luokitteluperuste, "
        f"kl.KayttajaNimi AS Hyvaksyja "
        f"FROM Kurssi k LEFT JOIN Kurssiluokitus kl ON k.KID = kl.KID AND kl.TID = %s "
        f"WHERE {where}{tila_sql}{suod_sql}{jarj_sql}{raja_sql}",
        (tid, *params, *suod_params, *raja_params),
    )


def hae_hitl_historia(tid: int, kidit: list[int]) -> list[dict]:
    """Annettujen kurssien (esim. WebUI:n sivu) HITL-korjaukset vanhimmasta uusimpaan.
    Rajaus KID:eihin: koko tutkimuksen historia kasvaa annotointisessioissa."""
    if not kidit:
        return []
    return _hae_kaikki(
        f"""SELECT KID, UusiTila, Perustelu, KayttajaNimi, Aikaleima
            FROM HitlKorjaus WHERE TID = %s AND KID IN ({",".join(["%s"] * len(kidit))})
            ORDER BY HID ASC""",
        (tid, *kidit),
    )


# --- Kurssiluokitus ---

def aseta_luokitukset(tid: int, rivit: list[tuple], malli: str = "",
                      tiiviste: str | None = None) -> None:
    """Luokitukset yhdellä monirivisellä upsertilla. rivit: (kid, mukana, perustelu)."""
    with yhteys() as yht:
        with yht.cursor() as kursori:
            _lisaa_rivit(
                kursori,
                "INSERT INTO Kurssiluokitus (TID, KID, Mukana, Luokitteluperuste, Malli, Kehotetiiviste)",
                [(tid, kid, mukana, perustelu, malli, tiiviste) for kid, mukana, perustelu in rivit],
                LUOKITUS_PAIVITYS,
            )


def hyvaksy_luokitus(tid: int, kid: int, nimi: str, sahkoposti: str | None) -> None:
    """Ihminen hyväksyy (peukuttaa) mukaan otetun kurssin luokittelupäätöksen.

    Vain visuaalinen merkintä: Mukana ei muutu. KayttajaNimi IS NULL = ei
    hyväksytty. Hylättyyn kurssiin ei osu (no-op) — hylättyjä ei hyväksytä.
    Ei rowcount-tarkistusta: mysql-connector laskee vain muuttuneet rivit, joten
    saman nimen uusi hyväksyntä näyttäisi epäonnistuneelta.
    """
    _suorita(
        """UPDATE Kurssiluokitus SET KayttajaNimi = %s, Sahkoposti = %s
           WHERE TID = %s AND KID = %s AND Mukana = 1""",
        (nimi, sahkoposti or None, tid, kid),
    )


def hae_luokitukset(tid: int, mukana: bool | None = None) -> list[dict]:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            if mukana is None:
                kursori.execute("SELECT * FROM Kurssiluokitus WHERE TID = %s", (tid,))
            else:
                kursori.execute("SELECT * FROM Kurssiluokitus WHERE TID = %s AND Mukana = %s", (tid, mukana))
            return _rivit_dikteina(kursori)


def laske_luokitukset(tid: int, mukana: bool | None = None) -> int:
    """Luokitusrivien lukumäärä (COUNT(*), ei rivinoutoa). Erillinen
    hae_luokitukset:sta, jottei Luokitteluperuste-tekstejä ladata verkon yli
    pelkkää laskentaa varten (arvioinnin tilannesivu etäpalvelimella)."""
    with yhteys() as yht:
        with yht.cursor() as kursori:
            if mukana is None:
                kursori.execute("SELECT COUNT(*) FROM Kurssiluokitus WHERE TID = %s", (tid,))
            else:
                kursori.execute("SELECT COUNT(*) FROM Kurssiluokitus WHERE TID = %s AND Mukana = %s", (tid, mukana))
            return int(kursori.fetchone()[0])


def hae_tutkimuksen_tilanne(tid: int) -> dict:
    """Tutkimuksen suppilo (funnel): kuinka kurssit karsiutuvat vaihe vaiheelta.

    Vuosi- ja oppilaitosrajaus ovat kovia (rajaavat ehdokasjoukon); meta- ja
    LLM-luokitus jakavat in-scope-kurssit odottaviin/hylättyihin/hyväksyttyihin.
    Meta- ja LLM-hylkäys erotetaan Luokitteluperusteen "meta:"-etuliitteestä.
    """
    # Suppilo lasketaan SQL-aggregaateilla yhdessä yhteydessä. Aiemmin tämä veti
    # kaikki kurssit ja luokitukset Pythoniin (4 yhteyttä + ~12000 riviä) — halpaa
    # localhostilla mutta hidasta etäpalvelimella (geopalvelin1). Nyt: 1 yhteys,
    # muutama COUNT-rivi.
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute("SELECT COUNT(*) FROM Kurssi")
            kursseja_yht = int(kursori.fetchone()[0])

            lukuvuosi, korkeakoulut = _rajaus(kursori, tid)

            # Ilman lukuvuotta koko in-scope-joukko on tyhjä (kuten Python-versiossa).
            if not lukuvuosi:
                return {"kursseja_yht": kursseja_yht, "vuosi_lapi": 0,
                        "vuosi_hyl": kursseja_yht, "oppilaitos_lapi": 0,
                        "oppilaitos_hyl": 0, "odottaa_meta": 0, "hyl_meta": 0,
                        "odottaa_llm": 0, "hyl_llm": 0, "hyvaksytty": 0}

            vuosi_sql, vp = _vuosi_kattaa_sql("k.Opetusvuosi", lukuvuosi)
            kk = ",".join(["%s"] * len(korkeakoulut)) if korkeakoulut else "NULL"

            # Kurssipuoli: vuosirajaus läpäisseet + niistä valittuihin korkeakouluihin osuvat.
            kursori.execute(
                f"""SELECT COALESCE(SUM({vuosi_sql}), 0),
                           COALESCE(SUM(CASE WHEN ({vuosi_sql}) AND k.KKID IN ({kk})
                                            THEN 1 ELSE 0 END), 0)
                    FROM Kurssi k""",
                (*vp, *vp, *korkeakoulut),
            )
            vuosi_lapi, in_scope = (int(x) for x in kursori.fetchone())

            # Luokituspuoli in-scope-kursseille: mukaan / odottaa / meta-hylätty / LLM-hylätty.
            # Meta- ja LLM-hylkäys erotetaan Luokitteluperusteen "meta:"-etuliitteestä.
            # STRAIGHT_JOIN + Kurssi ensin: optimoija ajaa muuten Kurssiluokituksen
            # ensin (ref TID) ja tekee sitten ~34 k perusavainhakua Kurssiin, mikä
            # maksoi 2,06 s. Kurssi ensin lukee idx_kkid_vuosi:n kattavana skannauksena
            # ja hakee luokitusrivin eq_ref:llä → 0,67 s (mitattu geopalvelin1, sama
            # tulos 171/33716). ANALYZE TABLE ei muuttanut optimoijan valintaa.
            kursori.execute(
                f"""SELECT STRAIGHT_JOIN
                           COALESCE(SUM(kl.Mukana = 1), 0),
                           COALESCE(SUM(kl.Mukana IS NULL), 0),
                           COALESCE(SUM(kl.Mukana = 0 AND kl.Luokitteluperuste LIKE 'meta:%%'), 0),
                           COALESCE(SUM(kl.Mukana = 0 AND (kl.Luokitteluperuste NOT LIKE 'meta:%%'
                                        OR kl.Luokitteluperuste IS NULL)), 0),
                           COUNT(*)
                    FROM Kurssi k
                    JOIN Kurssiluokitus kl ON kl.KID = k.KID AND kl.TID = %s
                    WHERE ({vuosi_sql}) AND k.KKID IN ({kk})""",
                (tid, *vp, *korkeakoulut),
            )
            hyvaksytty, odottaa_llm, hyl_meta, hyl_llm, luok_maara = (
                int(x) for x in kursori.fetchone())

    return {
        "kursseja_yht": kursseja_yht,
        "vuosi_lapi": vuosi_lapi,
        "vuosi_hyl": kursseja_yht - vuosi_lapi,
        "oppilaitos_lapi": in_scope,
        "oppilaitos_hyl": vuosi_lapi - in_scope,
        "odottaa_meta": in_scope - luok_maara,
        "hyl_meta": hyl_meta,
        "odottaa_llm": odottaa_llm,
        "hyl_llm": hyl_llm,
        "hyvaksytty": hyvaksytty,
    }


# --- HITL-korjaukset ---

# Virhetaksonomian juurisyyt (CLAUDE.md): koodi → ihmisluettava nimi.
# Jaettu WebUI-validoinnin (palvelin.py) ja raporttitilastojen kesken.
JUURISYYT = {
    "riittamaton_opas": "Riittämätön opinto-opas",
    "llm_virhe": "LLM:n väärinymmärrys",
}


def tallenna_hitl_korjaus(tid: int, kid: int, uusi_tila: bool, perustelu: str,
                          nimi: str, sahkoposti: str, juurisyy: str | None = None) -> None:
    """Tallentaa ihmisen tekemän luokittelun ohituksen ja päivittää Kurssiluokitus.Mukana.

    juurisyy: virhetaksonomian koodi (ks. JUURISYYT) tai None, jos merkitsemättä.
    Idempotentti: WebUI lähettää pyynnön uudelleen jos vastaus katoaa, joten
    historiariviä ei lisätä jos kurssin viimeisin korjaus on täsmälleen sama.
    """
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                """INSERT INTO HitlKorjaus
                       (TID, KID, UusiTila, Perustelu, KayttajaNimi, Sahkoposti, Juurisyy)
                   SELECT %s, %s, %s, %s, %s, %s, %s FROM DUAL
                   WHERE NOT EXISTS (
                       SELECT 1 FROM (SELECT UusiTila, Perustelu, KayttajaNimi FROM HitlKorjaus
                                      WHERE TID = %s AND KID = %s ORDER BY HID DESC LIMIT 1) viimeisin
                       WHERE viimeisin.UusiTila = %s AND viimeisin.Perustelu = %s
                             AND viimeisin.KayttajaNimi = %s)""",
                (tid, kid, uusi_tila, perustelu, nimi, sahkoposti, juurisyy,
                 tid, kid, uusi_tila, perustelu, nimi),
            )
            kursori.execute(
                "UPDATE Kurssiluokitus SET Mukana = %s WHERE TID = %s AND KID = %s",
                (uusi_tila, tid, kid),
            )
