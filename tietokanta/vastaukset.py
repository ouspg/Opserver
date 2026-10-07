"""LLM-arviointien vastaukset ja ihmisten korjaukset niihin (HITL-B)."""
from tietokanta.yhteys import yhteys
from tietokanta._yhteiset import (
    VASTAUS_PAIVITYS, _hae_arvo, _hae_kaikki, _json, _lisaa_rivit, _pura_json, _rivit_dikteina,
    _suorita, _tutkimus_kurssi_scope,
)


def aseta_vastaukset(tid: int, rivit: list[tuple]) -> None:
    """LLM:n vastaukset yhdellä monirivisellä upsertilla.
    rivit: (kysid, kid, vastaus, malli, pisteet, luokka, lista, tiiviste).

    KayttajaNimi jää tyhjäksi → uniikki_kys_kid_kayttaja antaa yhden LLM-rivin
    per (kysymys, kurssi), eli uudelleenajo päivittää saman rivin.
    Malli ei koskaan NULL: se erottaa LLM-rivin ihmisen korjauksesta.
    """
    with yhteys() as yht:
        with yht.cursor() as kursori:
            _lisaa_rivit(
                kursori,
                "INSERT INTO Vastaukset (TID, KysID, KID, Vastaus, Malli, Pisteet, Luokka, Lista, Kehotetiiviste)",
                [(tid, kysid, kid, vastaus, malli or "", pisteet, luokka, _json(lista), tiiviste)
                 for kysid, kid, vastaus, malli, pisteet, luokka, lista, tiiviste in rivit],
                VASTAUS_PAIVITYS,
            )


def hyvaksy_vastaus(tid: int, kid: int, kysid: int, nimi: str, sahkoposti: str | None) -> None:
    """Ihminen hyväksyy (peukuttaa) LLM:n arviointivastauksen (migraatio_024).

    Vain visuaalinen merkintä LLM-riville; HyvaksyjaNimi IS NULL = ei hyväksytty.
    Oma sarake eikä KayttajaNimi, koska se kuuluu uniikkiavaimeen ja erottaa
    LLM-rivin ('') ihmisten korjauksista.
    """
    _suorita(
        """UPDATE Vastaukset SET HyvaksyjaNimi = %s, HyvaksyjaSahkoposti = %s
           WHERE TID = %s AND KID = %s AND KysID = %s AND Malli IS NOT NULL""",
        (nimi, sahkoposti or None, tid, kid, kysid),
    )


def hae_raakana_tallennetut_vastaukset(tid: int) -> list[dict]:
    """Vastaukset, joiden teksti on jäänyt raa'aksi JSON-objektiksi ('{...}').

    Syntyi kun malli palautti kysymyskohtaisen vastauksen JSON-merkkijonona:
    jäsentämätön teksti päätyi Vastaus-kenttään ja Luokka/Pisteet/Lista jäivät
    tyhjiksi. Data on tallessa, joten rivit voi korjata jäsentämällä uudelleen
    (arviointi.korjaus) — uutta LLM-ajoa ei tarvita.
    """
    return _hae_kaikki(
        """SELECT v.VasID, v.KysID, v.KID, v.Vastaus, v.Malli, v.Kehotetiiviste
           FROM Vastaukset v
           JOIN Kysymykset ky ON ky.KysID = v.KysID
           WHERE ky.TID = %s AND v.Malli IS NOT NULL AND v.Vastaus LIKE '{%%'""",
        (tid,),
    )


def hae_vastaus_tiivisteet(tid: int) -> dict[tuple[int, int], dict]:
    """Palauttaa tutkimuksen vastausten tilan: {(KID, KysID): {tiiviste, vastattu, hitl, lista}}.

    vastattu = True jos vastauksessa on ei-tyhjä teksti, luokka tai pisteet.
    Käytetään tunnistamaan mitkä (kurssi, kysymys) -parit tarvitsevat
    (uudelleen)arvioinnin kehotteen/kysymyksen muututtua.

    hitl = True jos ihminen on korjannut vastauksen. Silloin LLM ei aja sitä
    uudelleen edes kehotteen muuttuessa — sama sääntö kuin luokittelupuolella
    (_luokittelemattomat_ehto sulkee HitlKorjaus-kurssit pois). Ihmisen työtä ei
    ylikirjoiteta, ja riittämättömän opinto-oppaan täydennys säilyy.

    lista = Lista-sarakkeen MD5 (raportin tuoreus: lista-arvojen yhdistäminen
    muuttaa vain sitä, ks. raportti.listanormalisointi).
    """
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute("""
                SELECT v.KID, v.KysID, v.Kehotetiiviste, (v.Malli IS NULL) AS Hitl,
                       ((v.Vastaus IS NOT NULL AND v.Vastaus <> '')
                        OR v.Luokka IS NOT NULL OR v.Pisteet IS NOT NULL
                        OR v.Lista IS NOT NULL) AS Vastattu,
                       MD5(v.Lista) AS ListaTiiviste
                FROM Vastaukset v
                WHERE v.TID = %s
                ORDER BY (v.Malli IS NULL)
            """, (tid,))
            # ORDER BY: LLM-rivit ensin, ihmisen korjaus kirjoittaa niiden yli →
            # samalla (KID, KysID) -parilla HITL-tila voittaa.
            return {
                (r["KID"], r["KysID"]): {
                    "tiiviste": r["Kehotetiiviste"],
                    "vastattu": bool(r["Vastattu"]),
                    "hitl": bool(r["Hitl"]),
                    "lista": r.get("ListaTiiviste"),
                }
                for r in _rivit_dikteina(kursori)
            }


def hae_vastausten_lkm(kysid: int) -> int:
    return _hae_arvo("SELECT COUNT(*) FROM Vastaukset WHERE KysID = %s", (kysid,))


def poista_vastaukset_kysymykselta(kysid: int) -> None:
    _suorita("DELETE FROM Vastaukset WHERE KysID = %s", (kysid,))


def hae_vastaukset(tid: int) -> list[dict]:
    """Tutkimuksen vastaukset: sekä LLM:n että ihmisten korjaukset.

    Rivin alkuperä: Malli IS NULL → ihmisen korjaus, muuten LLM:n vastaus
    (ks. migraatio_022). Uusin ensin saman (kysymys, kurssi) -parin sisällä,
    jotta esittäjä voi ottaa ensimmäisen osuman voittajaksi.
    """
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute("""
                SELECT v.*
                FROM Vastaukset v
                WHERE v.TID = %s
                ORDER BY v.KID, v.KysID, (v.Malli IS NULL) DESC, v.Aikaleima DESC
            """, (tid,))
            rivit = _rivit_dikteina(kursori)
    return _pura_json(rivit, "Lista")


def _arvioimattomat_ehto(tid: int) -> tuple[str, tuple]:
    """FROM+GROUP BY (ja parametrit) mukaan otetuille kursseille, joilta puuttuu
    vielä ei-tyhjiä vastauksia.

    GROUP BY -aggregaatti korreloidun per-rivi-alikyselyn sijaan: aiemmin jokaista
    mukana-kurssia kohti ajettiin oma COUNT-alikysely (O(kurssit) × etälatenssi).
    Nyt kurssit, kysymykset ja vastaukset yhdistetään kertaalleen ja verrataan
    vastattujen kysymysten määrää kysymysten kokonaismäärään.

    Palauttaa fragmentin, joka ryhmittelee k.KID:n mukaan → kutsuja kietoo sen:
    rivihaku `SELECT k.* {ehto}`, lukumäärä `SELECT COUNT(*) FROM (SELECT k.KID {ehto}) t`.
    """
    scope_where, sp = _tutkimus_kurssi_scope(tid)
    where_sql = f"WHERE {scope_where}"
    ehto = f"""
        FROM Kurssi k
        JOIN Kurssiluokitus kl ON k.KID = kl.KID AND kl.TID = %s AND kl.Mukana = 1
        LEFT JOIN Kysymykset ky ON ky.TID = %s
        LEFT JOIN Vastaukset v ON v.KID = k.KID AND v.KysID = ky.KysID AND v.Vastaus <> ''
        {where_sql}
        GROUP BY k.KID
        HAVING COUNT(DISTINCT v.KysID) < COUNT(DISTINCT ky.KysID)
    """
    return ehto, (tid, tid, *sp)


def laske_arvioimattomat(tid: int) -> int:
    """Arvioimattomien kurssien (mukana, mutta ei vielä kaikkia ei-tyhjiä vastauksia)
    lukumäärä tutkimuksen rajauksessa."""
    ehto, params = _arvioimattomat_ehto(tid)
    return int(_hae_arvo(f"SELECT COUNT(*) FROM (SELECT k.KID {ehto}) t", params))


# --- HITL-vastaukset (ihmisen korjaukset arviointeihin) ---

def tallenna_hitl_vastaus(tid: int, kid: int, kysid: int, vastaus: str,
                          nimi: str, sahkoposti: str, pisteet: float | None = None,
                          luokka: str | None = None, lista: list | None = None,
                          juurisyy: str | None = None) -> None:
    """Ihmisen korjaama vastaus samaan tauluun kuin LLM:n vastaus (migraatio_022).

    Malli ja Kehotetiiviste jäävät NULLiksi — se erottaa HITL-rivin LLM-rivistä.
    Sama korjaaja päivittää oman aiemman korjauksensa (uniikki_kys_kid_kayttaja),
    eri korjaajien rivit säilyvät erillisinä. Aikaleima päivittyy korjatessa.
    """
    lista_json = _json(lista)
    _suorita(
        """INSERT INTO Vastaukset
               (TID, KysID, KID, Vastaus, Pisteet, Luokka, Lista,
                KayttajaNimi, Sahkoposti, Juurisyy, Malli, Kehotetiiviste)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL, NULL)
           ON DUPLICATE KEY UPDATE
               Vastaus = VALUES(Vastaus), Pisteet = VALUES(Pisteet),
               Luokka = VALUES(Luokka), Lista = VALUES(Lista),
               Sahkoposti = VALUES(Sahkoposti), Juurisyy = VALUES(Juurisyy),
               Aikaleima = CURRENT_TIMESTAMP""",
        (tid, kysid, kid, vastaus, pisteet, luokka, lista_json,
         nimi, sahkoposti, juurisyy),
    )


def hae_hitl_vastaukset(tid: int) -> list[dict]:
    """Ihmisten korjaamat vastaukset tälle tutkimukselle (uusin ensin)."""
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                """SELECT KID, KysID, Vastaus, Pisteet, Luokka, Lista,
                          KayttajaNimi, Sahkoposti, Juurisyy, Aikaleima
                   FROM Vastaukset
                   WHERE TID = %s AND Malli IS NULL
                   ORDER BY Aikaleima DESC""",
                (tid,),
            )
            rivit = _rivit_dikteina(kursori)
    return _pura_json(rivit, "Lista")
