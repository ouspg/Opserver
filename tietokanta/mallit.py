import json
from tietokanta.yhteys import yhteys, uudelleenyrita
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


# --- Korkeakoulu ---

def lisaa_korkeakoulu(koulu_nimi: str, ops_osoite: str, ops_tyyppi: str,
                      api_osoite: str | None = None) -> int:
    return _suorita(
        "INSERT INTO Korkeakoulu (KouluNimi, OpsOsoite, ApiOsoite, OpsTyyppi) "
        "VALUES (%s, %s, %s, %s)",
        (koulu_nimi, ops_osoite, api_osoite, ops_tyyppi),
    )


def hae_korkeakoulut() -> list[dict]:
    return _hae_kaikki("SELECT * FROM Korkeakoulu ORDER BY KouluNimi")


def paivita_korkeakoulu(kkid: int, koulu_nimi: str, ops_osoite: str, ops_tyyppi: str,
                        api_osoite: str | None = None) -> None:
    _suorita(
        "UPDATE Korkeakoulu SET KouluNimi = %s, OpsOsoite = %s, ApiOsoite = %s, "
        "OpsTyyppi = %s WHERE KKID = %s",
        (koulu_nimi, ops_osoite, api_osoite, ops_tyyppi, kkid),
    )


def poista_korkeakoulu(kkid: int) -> None:
    _suorita("DELETE FROM Korkeakoulu WHERE KKID = %s", (kkid,))


# --- Kurssi ---

# OpsKuvaus on omassa taulussaan (KurssiKuvaus, migraatio 025): ainoa raskas kenttä
# (mediumtext, ka. 6,3 kB) mahtui riville, jolloin Kurssi oli ~250 MB ja jokainen
# sen läpikäyvä kysely (tilamäärät, odottaa/hylätty-listat) luki kuvaukset levyltä
# (tuotannossa 9–22 s). Kuvaus liitetään vain sitä tarvitseviin hakuihin.
_KUVAUS_JOIN = "LEFT JOIN KurssiKuvaus ku ON ku.KID = k.KID"

# ponytail: uudelleenyritys vain kurssihaun pitkän ajon kutsuissa — muut kutsut
# ovat kertaluontoisia ja kaatuvat siististi. Lisää dekoraattori jos ne kaatuilevat.
@uudelleenyrita
def tallenna_kurssi(kkid: int, lahde_id: str, koodi: str, kurssi_nimi: str,
                    taso: str | None, oppiaine: str, opintopisteet: str | None,
                    opetusvuosi: str, ops_kuvaus: str) -> int:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            # LAST_INSERT_ID(KID): lastrowid = KID myös päivityshaarassa (kuvausta varten).
            kursori.execute(
                """INSERT INTO Kurssi
                       (KKID, LahdeId, Koodi, KurssiNimi, Taso, Oppiaine, Opintopisteet, Opetusvuosi)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE KID = LAST_INSERT_ID(KID),
                       Koodi = VALUES(Koodi), KurssiNimi = VALUES(KurssiNimi),
                       Taso = VALUES(Taso), Oppiaine = VALUES(Oppiaine),
                       Opintopisteet = VALUES(Opintopisteet)""",
                (kkid, lahde_id, koodi, kurssi_nimi, taso, oppiaine, opintopisteet, opetusvuosi),
            )
            kid = kursori.lastrowid
            kursori.execute(
                """INSERT INTO KurssiKuvaus (KID, OpsKuvaus) VALUES (%s, %s)
                   ON DUPLICATE KEY UPDATE OpsKuvaus = VALUES(OpsKuvaus)""",
                (kid, ops_kuvaus),
            )
            return kid


# Listanäkymän kentät (OpsKuvaus on omassa taulussaan, ks. _KUVAUS_JOIN).
_KURSSI_LISTA_SARAKKEET = (
    "KID, KKID, LahdeId, Koodi, KurssiNimi, Taso, Oppiaine, Opintopisteet, Opetusvuosi"
)


def hae_kurssit(kkid: int | None = None, lukuvuosi: str | None = None) -> list[dict]:
    """Listanäkymän kurssit. lukuvuosi rajaa kurssit, joiden OPS-kausi kattaa
    annetun lukuvuoden (esim. "2026-2027"; OPS "2024-2027" kattaa sen) — SQL:ssä
    (idx_kkid_vuosi), ei koko luetteloa Pythoniin."""
    ehdot, params = [], []
    if kkid is not None:
        ehdot.append("KKID = %s")
        params.append(kkid)
    if lukuvuosi:
        try:
            vuosi_sql, vuosi_params = _vuosi_kattaa_sql("Opetusvuosi", lukuvuosi)
        except ValueError:
            return []
        ehdot.append(vuosi_sql)
        params.extend(vuosi_params)
    where = f" WHERE {' AND '.join(ehdot)}" if ehdot else ""
    return _hae_kaikki(f"SELECT {_KURSSI_LISTA_SARAKKEET} FROM Kurssi{where} ORDER BY KurssiNimi", params)


def _kattaa_turvallinen(ops_kausi: str | None, lukuvuosi: str) -> bool:
    """lv.kattaa, mutta virheellinen/puuttuva kausi rajataan pois (ei kaadu)."""
    if not ops_kausi:
        return False
    try:
        return lv.kattaa(ops_kausi, lukuvuosi)
    except ValueError:
        return False


def hae_lukuvuodet() -> list[str]:
    """Saatavilla olevat yksittäiset lukuvuodet, uusin ensin.

    Kootaan kaikkien OPS-kausien kattamista vuosista (esim. "2024-2027" kattaa
    2024-2025, 2025-2026 ja 2026-2027), jotta valinta osuu monivuotisiinkin OPS:eihin.
    """
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                "SELECT DISTINCT Opetusvuosi FROM Kurssi "
                "WHERE Opetusvuosi IS NOT NULL AND Opetusvuosi != ''"
            )
            vuodet: set[str] = set()
            for (kausi,) in kursori.fetchall():
                try:
                    vuodet.update(lv.kauden_vuodet(kausi))
                except ValueError:
                    continue
    return sorted(vuodet, reverse=True)


def hae_kurssimaarat_kouluittain() -> dict[int, list[dict]]:
    """Kurssimäärät korkeakoulu- ja opetusvuosi-kohtaisesti.

    Palauttaa {KKID: [{"Opetusvuosi": "2025-2026", "lkm": 2435}, ...]}.
    """
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute("""
                SELECT KKID, Opetusvuosi, COUNT(*)
                FROM Kurssi
                WHERE Opetusvuosi IS NOT NULL AND Opetusvuosi != ''
                GROUP BY KKID, Opetusvuosi
            """)
            tulos: dict[int, list[dict]] = {}
            for kkid, vuosi, lkm in kursori.fetchall():
                tulos.setdefault(kkid, []).append({"Opetusvuosi": vuosi, "lkm": lkm})
    return tulos


def hae_tasot(kkid: int | None = None, lukuvuosi: str | None = None) -> list[str]:
    """Aineistossa esiintyvät Taso-arvot, yleisimmät ensin.

    Valinnainen rajaus korkeakouluun (kkid) ja lukuvuoteen (OPS-kausi kattaa sen),
    jotta /kurssit-sivu voi tarjota vain senhetkisen valinnan mukaiset tasot.
    """
    ehdot = ["Taso IS NOT NULL", "Taso != ''"]
    params: list = []
    if kkid is not None:
        ehdot.append("KKID = %s")
        params.append(kkid)
    if lukuvuosi:
        vuosi_sql, vuosi_params = _vuosi_kattaa_sql("Opetusvuosi", lukuvuosi)
        ehdot.append(vuosi_sql)
        params.extend(vuosi_params)
    return _hae_sarake(
        f"SELECT Taso FROM Kurssi WHERE {' AND '.join(ehdot)} "
        f"GROUP BY Taso ORDER BY COUNT(*) DESC",
        tuple(params),
    )


@uudelleenyrita
def hae_tallennetut_lahde_idt(kkid: int, opetusvuosi: str) -> set[str]:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                "SELECT LahdeId FROM Kurssi WHERE KKID = %s AND Opetusvuosi = %s",
                (kkid, opetusvuosi),
            )
            return {str(r[0]) for r in kursori.fetchall()}


def hae_kurssi(kid: int) -> dict | None:
    return _hae_yksi(
        f"SELECT k.*, ku.OpsKuvaus FROM Kurssi k {_KUVAUS_JOIN} WHERE k.KID = %s", (kid,),
    )


# --- Tutkimus ---

def lisaa_tutkimus(luokittelun_nimi: str, slug: str, lukuvuosi: str, luokittelukehote: str,
                   tasorajaus: str, oppiainerajaus: str, arviointikehote: str,
                   raportointikehote: str = "", verkkosivu: str = "") -> int:
    return _suorita(
        "INSERT INTO Tutkimus (LuokittelunNimi, Slug, Lukuvuosi, Verkkosivu, Luokittelukehote, Tasorajaus, Oppiainerajaus, Arviointikehote, Raportointikehote) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (luokittelun_nimi, slug, lukuvuosi, verkkosivu, luokittelukehote, tasorajaus, oppiainerajaus, arviointikehote, raportointikehote),
    )


def hae_tutkimukset() -> list[dict]:
    return _hae_kaikki("SELECT * FROM Tutkimus ORDER BY LuokittelunNimi")


def hae_tutkimukset_yhteenvedolla() -> list[dict]:
    return _hae_kaikki(
        """
        SELECT t.*, COUNT(CASE WHEN kl.Mukana = 1 THEN 1 END) AS MukanaLkm
        FROM Tutkimus t
        LEFT JOIN Kurssiluokitus kl ON t.TID = kl.TID
        GROUP BY t.TID
        ORDER BY t.LuokittelunNimi
    """,
    )


def hae_tutkimus(tid: int) -> dict | None:
    return _hae_yksi("SELECT * FROM Tutkimus WHERE TID = %s", (tid,))


def hae_tutkimus_slugilla(slug: str) -> dict | None:
    return _hae_yksi("SELECT * FROM Tutkimus WHERE Slug = %s", (slug,))


def hae_valitut_kurssit(tid: int, raja: int | None = None, siirto: int = 0,
                        kuvaukset: bool = True) -> list[dict]:
    """Mukaan otetut kurssit; raja/siirto → yksi sivu (WebUI lataa osissa).
    KID järjestyksen tasapelin ratkaisijana, jotta sivut eivät limity.
    kuvaukset=False: ilman OpsKuvausta (WebUI:n listat; LLM-arviointi tarvitsee sen)."""
    sivutus = " LIMIT %s OFFSET %s" if raja is not None else ""
    kuvaus_sql = (", ku.OpsKuvaus", _KUVAUS_JOIN) if kuvaukset else ("", "")
    return _hae_kaikki(
        f"""
        SELECT k.*{kuvaus_sql[0]}
        FROM Kurssi k {kuvaus_sql[1]}
        JOIN Kurssiluokitus kl ON k.KID = kl.KID
        WHERE kl.TID = %s AND kl.Mukana = 1
        ORDER BY k.KurssiNimi, k.KID""" + sivutus,
        (tid, raja, siirto) if sivutus else (tid,),
    )


def laske_valitut_kurssit(tid: int) -> int:
    return _hae_arvo("SELECT COUNT(*) FROM Kurssiluokitus WHERE TID = %s AND Mukana = 1", (tid,))


def paivita_tutkimus(tid: int, luokittelun_nimi: str, slug: str, lukuvuosi: str, luokittelukehote: str,
                     tasorajaus: str, oppiainerajaus: str, arviointikehote: str,
                     raportointikehote: str = "", verkkosivu: str = "") -> None:
    _suorita(
        "UPDATE Tutkimus SET LuokittelunNimi=%s, Slug=%s, Lukuvuosi=%s, Verkkosivu=%s, Luokittelukehote=%s, Tasorajaus=%s, Oppiainerajaus=%s, Arviointikehote=%s, Raportointikehote=%s WHERE TID=%s",
        (luokittelun_nimi, slug, lukuvuosi, verkkosivu, luokittelukehote, tasorajaus, oppiainerajaus, arviointikehote, raportointikehote, tid),
    )


def poista_tutkimus(tid: int) -> None:
    _suorita("DELETE FROM Tutkimus WHERE TID = %s", (tid,))


def monista_tutkimus(lahde_tid: int, uusi_nimi: str, uusi_slug: str) -> int:
    """Luo uuden tutkimuksen kopioimalla lähteen määrittelyn (kehotteet, rajaukset,
    lukuvuosi, verkkosivu, valitut korkeakoulut ja arviointikysymykset).

    Tuloksia (luokitukset, vastaukset, arvioinnit, raportti) ei kopioida — kopio on
    tuore tutkimus ajettavaksi. Nimi ja slug annetaan uusina.
    Yksi yhteys = yksi transaktio: kaatunut kopiointi ei jätä puolikasta tutkimusta.
    """
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                """INSERT INTO Tutkimus (LuokittelunNimi, Slug, Lukuvuosi, Verkkosivu, Luokittelukehote,
                       Tasorajaus, Oppiainerajaus, Arviointikehote, Raportointikehote)
                   SELECT %s, %s, Lukuvuosi, COALESCE(Verkkosivu, ''), Luokittelukehote,
                       Tasorajaus, Oppiainerajaus, Arviointikehote, COALESCE(Raportointikehote, '')
                   FROM Tutkimus WHERE TID = %s""",
                (uusi_nimi, uusi_slug, lahde_tid),
            )
            if kursori.rowcount == 0:
                raise ValueError(f"Tutkimusta {lahde_tid} ei ole")
            uusi_tid = kursori.lastrowid
            kursori.execute(
                "INSERT INTO TutkimusKorkeakoulu (TID, KKID) SELECT %s, KKID FROM TutkimusKorkeakoulu WHERE TID = %s",
                (uusi_tid, lahde_tid),
            )
            kursori.execute(
                """INSERT INTO Kysymykset (TID, Kysymys, Luokittelu, LuokitteluMaarittely)
                   SELECT %s, Kysymys, Luokittelu, LuokitteluMaarittely
                   FROM Kysymykset WHERE TID = %s ORDER BY KysID""",
                (uusi_tid, lahde_tid),
            )
            return uusi_tid


# --- Tutkimuksen korkeakoulut ---

def aseta_tutkimuksen_korkeakoulut(tid: int, kkid_lista: list[int]) -> None:
    """Korvaa tutkimukseen valitut korkeakoulut annetulla listalla."""
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute("DELETE FROM TutkimusKorkeakoulu WHERE TID = %s", (tid,))
            for kkid in kkid_lista:
                kursori.execute(
                    "INSERT INTO TutkimusKorkeakoulu (TID, KKID) VALUES (%s, %s)",
                    (tid, kkid),
                )


def hae_tutkimuksen_korkeakoulut(tid: int) -> list[int]:
    """Tutkimukseen valittujen korkeakoulujen KKID:t."""
    return _hae_sarake("SELECT KKID FROM TutkimusKorkeakoulu WHERE TID = %s ORDER BY KKID", (tid,))


def hae_oppiaineet(kkid_lista: list[int]) -> list[str]:
    """Annetuissa korkeakouluissa esiintyvät yksittäiset oppiaineet, aakkosjärjestyksessä.

    Pilkun merkitys riippuu lähdejärjestelmästä:
    - Peppissä Oppiaine-kenttä voi listata useita oppiaineita pilkulla eroteltuna
      (esim. "Hoitotiede, Terveyshallintotiede") → pilkotaan yksittäisiksi.
    - Sisussa pilkku on osa yhden vastuuorganisaation/ohjelman nimeä
      (esim. "LBS, Kauppatiede") → arvoa ei pilkota.
    """
    if not kkid_lista:
        return []
    paikat = ",".join(["%s"] * len(kkid_lista))
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                f"""SELECT DISTINCT k.Oppiaine, kk.OpsTyyppi
                    FROM Kurssi k JOIN Korkeakoulu kk ON k.KKID = kk.KKID
                    WHERE k.KKID IN ({paikat})""",
                tuple(kkid_lista),
            )
            oppiaineet: set[str] = set()
            for arvo, opstyyppi in kursori.fetchall():
                if not arvo:
                    continue
                osat = arvo.split(",") if opstyyppi == "Peppi" else [arvo]
                for osa in osat:
                    osa = osa.strip()
                    if osa:
                        oppiaineet.add(osa)
    return sorted(oppiaineet, key=str.casefold)


# --- Kysymykset ---

def lisaa_kysymys(tid: int, kysymys: str, luokittelu: str = "vapaa_teksti",
                  luokittelu_maarittely: dict | None = None) -> int:
    maarittely_json = json.dumps(luokittelu_maarittely, ensure_ascii=False) if luokittelu_maarittely else None
    return _suorita(
        "INSERT INTO Kysymykset (TID, Kysymys, Luokittelu, LuokitteluMaarittely) VALUES (%s, %s, %s, %s)",
        (tid, kysymys, luokittelu, maarittely_json),
    )


def hae_kysymykset(tid: int) -> list[dict]:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                "SELECT * FROM Kysymykset WHERE TID = %s ORDER BY KysID",
                (tid,),
            )
            rivit = _rivit_dikteina(kursori)
    for r in rivit:
        if r.get("LuokitteluMaarittely") and isinstance(r["LuokitteluMaarittely"], str):
            r["LuokitteluMaarittely"] = json.loads(r["LuokitteluMaarittely"])
    return rivit


def paivita_kysymys(kysid: int, kysymys: str, luokittelu: str = "vapaa_teksti",
                    luokittelu_maarittely: dict | None = None) -> None:
    maarittely_json = json.dumps(luokittelu_maarittely, ensure_ascii=False) if luokittelu_maarittely else None
    _suorita(
        "UPDATE Kysymykset SET Kysymys = %s, Luokittelu = %s, LuokitteluMaarittely = %s WHERE KysID = %s",
        (kysymys, luokittelu, maarittely_json, kysid),
    )


def poista_kysymys(kysid: int) -> None:
    _suorita("DELETE FROM Kysymykset WHERE KysID = %s", (kysid,))


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


def aseta_vastaus(kysid: int, kid: int, vastaus: str, malli: str = "",
                  pisteet: float | None = None, luokka: str | None = None,
                  lista: list | None = None, tiiviste: str | None = None) -> None:
    """LLM:n vastaus. TID johdetaan kysymyksestä, joten kutsujan ei tarvitse tietää sitä.

    KayttajaNimi jää tyhjäksi → uniikki_kys_kid_kayttaja antaa yhden LLM-rivin
    per (kysymys, kurssi) kuten ennen, eli uudelleenajo päivittää saman rivin.
    Malli ei koskaan NULL: se erottaa LLM-rivin ihmisen korjauksesta.
    """
    lista_json = json.dumps(lista, ensure_ascii=False) if lista is not None else None
    _suorita(
        """INSERT INTO Vastaukset
               (TID, KysID, KID, Vastaus, Malli, Pisteet, Luokka, Lista, Kehotetiiviste)
           SELECT k.TID, %s, %s, %s, %s, %s, %s, %s, %s
           FROM Kysymykset k WHERE k.KysID = %s
           """ + VASTAUS_PAIVITYS,
        (kysid, kid, vastaus, malli or "", pisteet, luokka, lista_json, tiiviste, kysid),
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
    """Palauttaa tutkimuksen vastausten tilan: {(KID, KysID): {tiiviste, vastattu, hitl}}.

    vastattu = True jos vastauksessa on ei-tyhjä teksti, luokka tai pisteet.
    Käytetään tunnistamaan mitkä (kurssi, kysymys) -parit tarvitsevat
    (uudelleen)arvioinnin kehotteen/kysymyksen muututtua.

    hitl = True jos ihminen on korjannut vastauksen. Silloin LLM ei aja sitä
    uudelleen edes kehotteen muuttuessa — sama sääntö kuin luokittelupuolella
    (_luokittelemattomat_ehto sulkee HitlKorjaus-kurssit pois). Ihmisen työtä ei
    ylikirjoiteta, ja riittämättömän opinto-oppaan täydennys säilyy.
    """
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute("""
                SELECT v.KID, v.KysID, v.Kehotetiiviste, (v.Malli IS NULL) AS Hitl,
                       ((v.Vastaus IS NOT NULL AND v.Vastaus <> '')
                        OR v.Luokka IS NOT NULL OR v.Pisteet IS NOT NULL
                        OR v.Lista IS NOT NULL) AS Vastattu
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
    for r in rivit:
        if isinstance(r.get("Lista"), str):
            r["Lista"] = json.loads(r["Lista"])
    return rivit


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
    scope_where, scope_params = _tutkimus_kurssi_scope(tid)
    scope_sql = f" AND {scope_where}" if scope_where else ""
    sp = scope_params or []
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


def hae_kurssit_idlla(kidit: list[int]) -> list[dict]:
    """Täydet kurssirivit (sis. OpsKuvaus LLM:lle) annetuille KID:eille.

    Vastapari hae_luokittelemattomat_kevyet:lle: yksi LLM-erä kerrallaan,
    perusavainhaku. (hae_kurssit on eri asia — UI:n listaus ilman OpsKuvausta.)
    """
    if not kidit:
        return []
    paikat = ",".join(["%s"] * len(kidit))
    return _hae_kaikki(
        f"SELECT k.*, ku.OpsKuvaus FROM Kurssi k {_KUVAUS_JOIN} "
                    f"WHERE k.KID IN ({paikat})", tuple(kidit),
    )


def laske_luokittelemattomat(tid: int, tiiviste: str | None = None) -> int:
    """LLM-seulontaa odottavien kurssien lukumäärä (COUNT(*), ei rivinoutoa).

    Erillinen hae_luokittelemattomat:sta, jottei OpsKuvaus-kenttää (~satoja MB
    koko aineistossa) ladata pelkkää laskentaa varten — tämä hidasti aiemmin
    LLM-näkymän avaamista, koska näkymä laskee sekä uudet että vanhentuneet.
    """
    ehto, params = _luokittelemattomat_ehto(tid, tiiviste)
    return _hae_arvo(f"SELECT COUNT(*) {ehto}", params)


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


def _tutkimus_kurssi_scope(tid: int) -> tuple[str | None, list]:
    """SQL-WHERE + parametrit jotka rajaavat Kurssi-rivit tutkimuksen korkeakouluihin
    ja lukuvuoteen (OPS-kausi kattaa lukuvuoden). (None, None) jos rajaus puuttuu."""
    with yhteys() as yht:
        with yht.cursor() as kursori:
            lukuvuosi, korkeakoulut = _rajaus(kursori, tid)
    if not korkeakoulut or not lukuvuosi:
        return None, None
    paikat = ",".join(["%s"] * len(korkeakoulut))
    vuosi_sql, vuosi_params = _vuosi_kattaa_sql("k.Opetusvuosi", lukuvuosi)
    where = f"k.KKID IN ({paikat}) AND {vuosi_sql}"
    return where, [*korkeakoulut, *vuosi_params]


def hae_meta_ehdokkaat(tid: int) -> list[dict] | None:
    """Tutkimuksen rajauksen (korkeakoulut + lukuvuosi) kurssit meta-suodatusta varten,
    nykyinen luokitus liitettynä (Luokiteltu, Mukana, Luokitteluperuste). Vain
    suodatuksen tarvitsemat sarakkeet. None jos rajaus puuttuu."""
    where, params = _tutkimus_kurssi_scope(tid)
    if where is None:
        return None
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
    if where is None:
        return maarat
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
    if where is None:
        return []
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

def aseta_luokitus(tid: int, kid: int, mukana: bool | None, perustelu: str,
                   malli: str = "", tiiviste: str | None = None) -> None:
    _suorita(
        """INSERT INTO Kurssiluokitus (TID, KID, Mukana, Luokitteluperuste, Malli, Kehotetiiviste)
           VALUES (%s, %s, %s, %s, %s, %s)
           """ + LUOKITUS_PAIVITYS,
        (tid, kid, mukana, perustelu, malli, tiiviste),
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
    scope_where, scope_params = _tutkimus_kurssi_scope(tid)
    where_sql = f"WHERE {scope_where}" if scope_where else ""
    sp = scope_params or []
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
    lista_json = json.dumps(lista, ensure_ascii=False) if lista is not None else None
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
    for r in rivit:
        if isinstance(r.get("Lista"), str):
            r["Lista"] = json.loads(r["Lista"])
    return rivit


# --- RaporttiOsio ---

def hae_raportti_osiot(tid: int) -> dict[str, str]:
    """Palauttaa kaikki raporttiosiot {avain: teksti} -diktinä."""
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                "SELECT OsioAvain, Teksti FROM RaporttiOsio WHERE TID = %s",
                (tid,),
            )
            return {r[0]: r[1] for r in kursori.fetchall()}


def aseta_raportti_osio(tid: int, avain: str, teksti: str,
                        laskentatiiviste: str | None = None) -> None:
    """Upsert raporttiosio. laskentatiiviste: annettuna (generointi) tallennetaan;
    None:na (WebUI-tekstimuokkaus) säilytetään aiempi arvo koskematta."""
    _suorita(
        """INSERT INTO RaporttiOsio (TID, OsioAvain, Teksti, Laskentatiiviste)
           VALUES (%s, %s, %s, %s)
           ON DUPLICATE KEY UPDATE Teksti = VALUES(Teksti),
               Laskentatiiviste = COALESCE(VALUES(Laskentatiiviste), Laskentatiiviste)""",
        (tid, avain, teksti, laskentatiiviste),
    )


def hae_raportti_osio(tid: int, avain: str) -> str:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                "SELECT Teksti FROM RaporttiOsio WHERE TID = %s AND OsioAvain = %s",
                (tid, avain),
            )
            rivi = kursori.fetchone()
            return rivi[0] if rivi else ""


def hae_raportti_tila(tid: int) -> list[dict]:
    """Per-osio metatieto raportin tilannesivulle: milloin kirjoitettu ja millä
    laskentatiivisteellä (lähdeaineiston hash generoinnin hetkellä). Ei hae
    Teksti-kenttää (voi olla iso) — vain kevyet metasarakkeet."""
    return _hae_kaikki(
        "SELECT OsioAvain, Aikaleima, Laskentatiiviste FROM RaporttiOsio WHERE TID = %s",
        (tid,),
    )


def hae_raportti_tuoreus(tid: int) -> dict | None:
    """Viimeksi laskettu raportin tuoreussignatuuri + laskenta-aika, tai None jos
    tuoreutta ei ole vielä laskettu. Kevyt luku — raskas tiivistelaskenta tehdään
    erikseen taustalla (tallenna_raportti_tuoreus)."""
    return _hae_yksi(
        "SELECT Signatuuri, Tarkistettu FROM RaporttiTuoreus WHERE TID = %s",
        (tid,),
    )


def tallenna_raportti_tuoreus(tid: int, signatuuri: str | None) -> None:
    """Upsert viimeksi laskettu tuoreussignatuuri; Tarkistettu = NOW() (taulun
    ON UPDATE / DEFAULT hoitaa aikaleiman). Kutsutaan taustalaskennasta ja
    generoinnista (jolloin signatuuri = generoinnin lähdeaineiston tiiviste)."""
    _suorita(
        """INSERT INTO RaporttiTuoreus (TID, Signatuuri) VALUES (%s, %s)
           ON DUPLICATE KEY UPDATE Signatuuri = VALUES(Signatuuri),
               Tarkistettu = CURRENT_TIMESTAMP""",
        (tid, signatuuri),
    )


def laske_hitl_korjaukset_jalkeen(tid: int, aika) -> int:
    """HITL-korjausten määrä, jotka on tehty annetun ajan jälkeen (COUNT, ei rivinoutoa)."""
    return int(_hae_arvo(
        "SELECT COUNT(*) FROM HitlKorjaus WHERE TID = %s AND Aikaleima > %s",
        (tid, aika),
    ))


def laske_hitl_vastaukset_jalkeen(tid: int, aika) -> int:
    """Ihmisen korjaamien vastausten määrä, jotka on tehty/muokattu ajan jälkeen."""
    return int(_hae_arvo(
        "SELECT COUNT(*) FROM Vastaukset "
        "WHERE TID = %s AND Malli IS NULL AND Aikaleima > %s",
        (tid, aika),
    ))


# --- Raporttitilastot ---

def _kattavat_kaudet(kursori, lukuvuosi: str | None) -> list[str]:
    """Aineiston Opetusvuosi-arvot, jotka kattavat tutkimuksen lukuvuoden.

    Tyhjä lukuvuosi (vanha tutkimus) → kaikki kaudet (ei vuosirajausta).
    """
    kursori.execute("SELECT DISTINCT Opetusvuosi FROM Kurssi")
    kaikki = [r[0] for r in kursori.fetchall()]
    if not lukuvuosi:
        return kaikki
    return [k for k in kaikki if _kattaa_turvallinen(k, lukuvuosi)]


def hae_tilastot_yliopistoittain(tid: int) -> list[dict]:
    """Per-yliopisto-tilastot raporttia varten.

    Rajattu tutkimukseen valittuihin korkeakouluihin ja niihin kursseihin,
    joiden OPS-kausi kattaa tutkimuksen lukuvuoden. Tyhjä valinta/lukuvuosi
    (vanha tutkimus) → ei rajausta kyseisen ulottuvuuden osalta.
    """
    with yhteys() as yht:
        with yht.cursor() as kursori:
            lukuvuosi, kkid_lista = _rajaus(kursori, tid)
            kaudet = _kattavat_kaudet(kursori, lukuvuosi)

            kk_ehto = f"WHERE ko.KKID IN ({','.join(['%s'] * len(kkid_lista))})" if kkid_lista else ""
            if kaudet:
                vuosi_ehto = f"AND k.Opetusvuosi IN ({','.join(['%s'] * len(kaudet))})"
            else:
                vuosi_ehto = "AND 1 = 0"  # lukuvuosi asetettu, mutta yksikään kausi ei kata sitä

            kursori.execute(f"""
                SELECT
                    ko.KKID,
                    ko.KouluNimi,
                    COUNT(DISTINCT k.KID)                                             AS KurssiYhteensa,
                    COUNT(DISTINCT CASE WHEN kl.TID = %s THEN kl.KID END)            AS LLMKasitelty,
                    COUNT(DISTINCT CASE WHEN kl.TID = %s AND kl.Mukana = 1 THEN kl.KID END) AS Mukana,
                    COUNT(DISTINCT CASE WHEN kl.TID = %s AND kl.Mukana = 0 THEN kl.KID END) AS Hylatty
                FROM Korkeakoulu ko
                LEFT JOIN Kurssi k ON k.KKID = ko.KKID {vuosi_ehto}
                LEFT JOIN Kurssiluokitus kl ON kl.KID = k.KID
                {kk_ehto}
                GROUP BY ko.KKID, ko.KouluNimi
                ORDER BY ko.KouluNimi
            """, (tid, tid, tid, *(kaudet if kaudet else []), *kkid_lista))
            rivit = _rivit_dikteina(kursori)
            # Lisää HITL-tilastot per yliopisto. HitlLkm = korjaustapahtumien määrä.
            # HitlKursseja + juurisyyjakauma lasketaan kunkin kurssin VIIMEISIMMÄSTÄ
            # korjauksesta (MAX(HID) per KID), jotta edestakaisin korjattu kurssi
            # ei tuplaannu ja lopputila kertoo ihmisen lopullisen syyn.
            kursori.execute("""
                SELECT k.KKID, COUNT(DISTINCT hk.HID) AS HitlLkm
                FROM HitlKorjaus hk
                JOIN Kurssi k ON hk.KID = k.KID
                WHERE hk.TID = %s
                GROUP BY k.KKID
            """, (tid,))
            hitl = {r[0]: r[1] for r in kursori.fetchall()}

            kursori.execute("""
                SELECT k.KKID,
                       COUNT(*)                                    AS HitlKursseja,
                       SUM(uusin.Juurisyy = 'riittamaton_opas')    AS RiittamatonOpas,
                       SUM(uusin.Juurisyy = 'llm_virhe')           AS LlmVirhe,
                       SUM(uusin.Juurisyy IS NULL)                 AS TuntematonSyy
                FROM (
                    SELECT hk.KID, hk.Juurisyy
                    FROM HitlKorjaus hk
                    JOIN (SELECT KID, MAX(HID) AS MaxHID
                          FROM HitlKorjaus WHERE TID = %s GROUP BY KID) v
                      ON hk.HID = v.MaxHID
                ) uusin
                JOIN Kurssi k ON uusin.KID = k.KID
                GROUP BY k.KKID
            """, (tid,))
            juurisyy = {r[0]: r[1:] for r in kursori.fetchall()}

            for r in rivit:
                r["HitlLkm"] = hitl.get(r["KKID"], 0)
                kurssit, opas, llm, tuntematon = juurisyy.get(r["KKID"], (0, 0, 0, 0))
                r["HitlKursseja"] = int(kurssit or 0)
                r["RiittamatonOpas"] = int(opas or 0)
                r["LlmVirhe"] = int(llm or 0)
                r["TuntematonSyy"] = int(tuntematon or 0)
            return rivit
