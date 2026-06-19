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


# --- Korkeakoulu ---

def lisaa_korkeakoulu(koulu_nimi: str, ops_osoite: str, ops_tyyppi: str,
                      api_osoite: str | None = None) -> int:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                "INSERT INTO Korkeakoulu (KouluNimi, OpsOsoite, ApiOsoite, OpsTyyppi) "
                "VALUES (%s, %s, %s, %s)",
                (koulu_nimi, ops_osoite, api_osoite, ops_tyyppi),
            )
            return kursori.lastrowid


def hae_korkeakoulut() -> list[dict]:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute("SELECT * FROM Korkeakoulu ORDER BY KouluNimi")
            return _rivit_dikteina(kursori)


def paivita_korkeakoulu(kkid: int, koulu_nimi: str, ops_osoite: str, ops_tyyppi: str,
                        api_osoite: str | None = None) -> None:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                "UPDATE Korkeakoulu SET KouluNimi = %s, OpsOsoite = %s, ApiOsoite = %s, "
                "OpsTyyppi = %s WHERE KKID = %s",
                (koulu_nimi, ops_osoite, api_osoite, ops_tyyppi, kkid),
            )


def poista_korkeakoulu(kkid: int) -> None:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute("DELETE FROM Korkeakoulu WHERE KKID = %s", (kkid,))


# --- Kurssi ---

def tallenna_kurssi(kkid: int, lahde_id: str, koodi: str, kurssi_nimi: str,
                    taso: str | None, oppiaine: str, opintopisteet: str | None,
                    opetusvuosi: str, ops_kuvaus: str) -> int:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                """INSERT INTO Kurssi
                       (KKID, LahdeId, Koodi, KurssiNimi, Taso, Oppiaine, Opintopisteet, Opetusvuosi, OpsKuvaus)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE
                       Koodi = VALUES(Koodi), KurssiNimi = VALUES(KurssiNimi),
                       Taso = VALUES(Taso), Oppiaine = VALUES(Oppiaine),
                       Opintopisteet = VALUES(Opintopisteet), OpsKuvaus = VALUES(OpsKuvaus)""",
                (kkid, lahde_id, koodi, kurssi_nimi, taso, oppiaine, opintopisteet, opetusvuosi, ops_kuvaus),
            )
            return kursori.lastrowid


# Listanäkymän kentät — EI raskasta OpsKuvaus-blobia (koko aineistossa ~248 MB,
# joka muuten luettaisiin turhaan jokaiseen listahakuun).
_KURSSI_LISTA_SARAKKEET = (
    "KID, KKID, LahdeId, Koodi, KurssiNimi, Taso, Oppiaine, Opintopisteet, Opetusvuosi"
)


def hae_kurssit(kkid: int | None = None, lukuvuosi: str | None = None) -> list[dict]:
    """Listanäkymän kurssit. lukuvuosi rajaa kurssit, joiden OPS-kausi kattaa
    annetun lukuvuoden (esim. "2026-2027"; OPS "2024-2027" kattaa sen)."""
    with yhteys() as yht:
        with yht.cursor() as kursori:
            if kkid is not None:
                kursori.execute(
                    f"SELECT {_KURSSI_LISTA_SARAKKEET} FROM Kurssi WHERE KKID = %s ORDER BY KurssiNimi",
                    (kkid,),
                )
            else:
                kursori.execute(
                    f"SELECT {_KURSSI_LISTA_SARAKKEET} FROM Kurssi ORDER BY KurssiNimi"
                )
            rivit = _rivit_dikteina(kursori)
    if lukuvuosi:
        rivit = [r for r in rivit if _kattaa_turvallinen(r.get("Opetusvuosi"), lukuvuosi)]
    return rivit


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
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                f"SELECT Taso FROM Kurssi WHERE {' AND '.join(ehdot)} "
                f"GROUP BY Taso ORDER BY COUNT(*) DESC",
                tuple(params),
            )
            return [r[0] for r in kursori.fetchall()]


def hae_tallennetut_lahde_idt(kkid: int, opetusvuosi: str) -> set[str]:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                "SELECT LahdeId FROM Kurssi WHERE KKID = %s AND Opetusvuosi = %s",
                (kkid, opetusvuosi),
            )
            return {str(r[0]) for r in kursori.fetchall()}


def hae_kurssi(kid: int) -> dict | None:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute("SELECT * FROM Kurssi WHERE KID = %s", (kid,))
            return _rivi_diktina(kursori)


# --- Tutkimus ---

def lisaa_tutkimus(luokittelun_nimi: str, slug: str, lukuvuosi: str, luokittelukehote: str,
                   tasorajaus: str, oppiainerajaus: str, arviointikehote: str,
                   raportointikehote: str = "", verkkosivu: str = "") -> int:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                "INSERT INTO Tutkimus (LuokittelunNimi, Slug, Lukuvuosi, Verkkosivu, Luokittelukehote, Tasorajaus, Oppiainerajaus, Arviointikehote, Raportointikehote) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (luokittelun_nimi, slug, lukuvuosi, verkkosivu, luokittelukehote, tasorajaus, oppiainerajaus, arviointikehote, raportointikehote),
            )
            return kursori.lastrowid


def hae_tutkimukset() -> list[dict]:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute("SELECT * FROM Tutkimus ORDER BY LuokittelunNimi")
            return _rivit_dikteina(kursori)


def hae_tutkimukset_yhteenvedolla() -> list[dict]:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute("""
                SELECT t.*, COUNT(CASE WHEN kl.Mukana = 1 THEN 1 END) AS MukanaLkm
                FROM Tutkimus t
                LEFT JOIN Kurssiluokitus kl ON t.TID = kl.TID
                GROUP BY t.TID
                ORDER BY t.LuokittelunNimi
            """)
            return _rivit_dikteina(kursori)


def hae_tutkimus(tid: int) -> dict | None:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute("SELECT * FROM Tutkimus WHERE TID = %s", (tid,))
            return _rivi_diktina(kursori)


def hae_tutkimus_slugilla(slug: str) -> dict | None:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute("SELECT * FROM Tutkimus WHERE Slug = %s", (slug,))
            return _rivi_diktina(kursori)


def hae_valitut_kurssit(tid: int) -> list[dict]:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute("""
                SELECT k.*
                FROM Kurssi k
                JOIN Kurssiluokitus kl ON k.KID = kl.KID
                WHERE kl.TID = %s AND kl.Mukana = 1
                ORDER BY k.KurssiNimi
            """, (tid,))
            return _rivit_dikteina(kursori)


def paivita_tutkimus(tid: int, luokittelun_nimi: str, slug: str, lukuvuosi: str, luokittelukehote: str,
                     tasorajaus: str, oppiainerajaus: str, arviointikehote: str,
                     raportointikehote: str = "", verkkosivu: str = "") -> None:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                "UPDATE Tutkimus SET LuokittelunNimi=%s, Slug=%s, Lukuvuosi=%s, Verkkosivu=%s, Luokittelukehote=%s, Tasorajaus=%s, Oppiainerajaus=%s, Arviointikehote=%s, Raportointikehote=%s WHERE TID=%s",
                (luokittelun_nimi, slug, lukuvuosi, verkkosivu, luokittelukehote, tasorajaus, oppiainerajaus, arviointikehote, raportointikehote, tid),
            )


def poista_tutkimus(tid: int) -> None:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute("DELETE FROM Tutkimus WHERE TID = %s", (tid,))


def monista_tutkimus(lahde_tid: int, uusi_nimi: str, uusi_slug: str) -> int:
    """Luo uuden tutkimuksen kopioimalla lähteen määrittelyn (kehotteet, rajaukset,
    lukuvuosi, verkkosivu, valitut korkeakoulut ja arviointikysymykset).

    Tuloksia (luokitukset, vastaukset, arvioinnit, raportti) ei kopioida — kopio on
    tuore tutkimus ajettavaksi. Nimi ja slug annetaan uusina.
    """
    lahde = hae_tutkimus(lahde_tid)
    uusi_tid = lisaa_tutkimus(
        uusi_nimi, uusi_slug, lahde["Lukuvuosi"], lahde["Luokittelukehote"],
        lahde["Tasorajaus"], lahde["Oppiainerajaus"], lahde["Arviointikehote"],
        lahde.get("Raportointikehote") or "", lahde.get("Verkkosivu") or "",
    )
    aseta_tutkimuksen_korkeakoulut(uusi_tid, hae_tutkimuksen_korkeakoulut(lahde_tid))
    for kysymys in hae_kysymykset(lahde_tid):
        lisaa_kysymys(uusi_tid, kysymys["Kysymys"], kysymys["Luokittelu"],
                      kysymys.get("LuokitteluMaarittely"))
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
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                "SELECT KKID FROM TutkimusKorkeakoulu WHERE TID = %s ORDER BY KKID", (tid,)
            )
            return [r[0] for r in kursori.fetchall()]


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
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                "INSERT INTO Kysymykset (TID, Kysymys, Luokittelu, LuokitteluMaarittely) VALUES (%s, %s, %s, %s)",
                (tid, kysymys, luokittelu, maarittely_json),
            )
            return kursori.lastrowid


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
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                "UPDATE Kysymykset SET Kysymys = %s, Luokittelu = %s, LuokitteluMaarittely = %s WHERE KysID = %s",
                (kysymys, luokittelu, maarittely_json, kysid),
            )


def poista_kysymys(kysid: int) -> None:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute("DELETE FROM Kysymykset WHERE KysID = %s", (kysid,))


# --- Vastaukset ---

def aseta_vastaus(kysid: int, kid: int, vastaus: str, malli: str = "",
                  pisteet: float | None = None, luokka: str | None = None,
                  lista: list | None = None, tiiviste: str | None = None) -> None:
    lista_json = json.dumps(lista, ensure_ascii=False) if lista is not None else None
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                """INSERT INTO Vastaukset (KysID, KID, Vastaus, Malli, Pisteet, Luokka, Lista, Kehotetiiviste)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE
                       Vastaus = VALUES(Vastaus), Malli = VALUES(Malli),
                       Pisteet = VALUES(Pisteet), Luokka = VALUES(Luokka),
                       Lista = VALUES(Lista), Kehotetiiviste = VALUES(Kehotetiiviste)""",
                (kysid, kid, vastaus, malli, pisteet, luokka, lista_json, tiiviste),
            )


def hae_vastaus_tiivisteet(tid: int) -> dict[tuple[int, int], dict]:
    """Palauttaa tutkimuksen vastausten tilan: {(KID, KysID): {tiiviste, vastattu}}.

    vastattu = True jos vastauksessa on ei-tyhjä teksti, luokka tai pisteet.
    Käytetään tunnistamaan mitkä (kurssi, kysymys) -parit tarvitsevat
    (uudelleen)arvioinnin kehotteen/kysymyksen muututtua.
    """
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute("""
                SELECT v.KID, v.KysID, v.Kehotetiiviste,
                       ((v.Vastaus IS NOT NULL AND v.Vastaus <> '')
                        OR v.Luokka IS NOT NULL OR v.Pisteet IS NOT NULL
                        OR v.Lista IS NOT NULL) AS Vastattu
                FROM Vastaukset v
                JOIN Kysymykset k ON v.KysID = k.KysID
                WHERE k.TID = %s
            """, (tid,))
            return {
                (r["KID"], r["KysID"]): {
                    "tiiviste": r["Kehotetiiviste"],
                    "vastattu": bool(r["Vastattu"]),
                }
                for r in _rivit_dikteina(kursori)
            }


def hae_vastausten_lkm(kysid: int) -> int:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute("SELECT COUNT(*) FROM Vastaukset WHERE KysID = %s", (kysid,))
            return kursori.fetchone()[0]


def poista_vastaukset_kysymykselta(kysid: int) -> None:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute("DELETE FROM Vastaukset WHERE KysID = %s", (kysid,))


def hae_vastaukset(tid: int) -> list[dict]:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute("""
                SELECT v.*
                FROM Vastaukset v
                JOIN Kysymykset k ON v.KysID = k.KysID
                WHERE k.TID = %s
                ORDER BY v.KID, v.KysID
            """, (tid,))
            rivit = _rivit_dikteina(kursori)
    for r in rivit:
        if isinstance(r.get("Lista"), str):
            r["Lista"] = json.loads(r["Lista"])
    return rivit


# --- Luokittelun apufunktiot ---

def hae_luokittelemattomat(tid: int, tiiviste: str | None = None) -> list[dict]:
    """Kurssit, jotka odottavat LLM-seulontaa.

    Aina mukana: kurssit joilla ei ole luokitusriviä tai Mukana IS NULL
    (meta-suodatuksen läpäisseet, jotka odottavat LLM:ää).

    Jos tiiviste annetaan: lisäksi aiemmin LLM-luokitellut kurssit, joiden
    tallennettu Kehotetiiviste eroaa nykyisestä (kehote on muuttunut) — pois
    lukien ihmisen HITL-korjaamat, joiden päätös säilytetään.
    """
    with yhteys() as yht:
        with yht.cursor() as kursori:
            if tiiviste is None:
                kursori.execute("""
                    SELECT k.*
                    FROM Kurssi k
                    LEFT JOIN Kurssiluokitus kl ON k.KID = kl.KID AND kl.TID = %s
                    WHERE kl.KID IS NULL OR kl.Mukana IS NULL
                    ORDER BY k.KurssiNimi
                """, (tid,))
            else:
                kursori.execute("""
                    SELECT k.*
                    FROM Kurssi k
                    LEFT JOIN Kurssiluokitus kl ON k.KID = kl.KID AND kl.TID = %s
                    WHERE kl.KID IS NULL
                       OR kl.Mukana IS NULL
                       OR (kl.Kehotetiiviste IS NOT NULL
                           AND NOT (kl.Kehotetiiviste <=> %s)
                           AND NOT EXISTS (SELECT 1 FROM HitlKorjaus h
                                           WHERE h.TID = %s AND h.KID = k.KID))
                    ORDER BY k.KurssiNimi
                """, (tid, tiiviste, tid))
            return _rivit_dikteina(kursori)


# Tila-välilehden ehto Kurssiluokitus.Mukana-arvosta.
_TILA_EHTO = {"mukana": "kl.Mukana = 1", "odottaa": "kl.Mukana IS NULL", "hylätty": "kl.Mukana = 0"}


def _vuosi_kattaa_sql(sarake: str, lukuvuosi: str) -> tuple[str, list]:
    """SQL-ehto + parametrit: OPS-kausi (sarake "YYYY-YYYY"/"YYYY-YY") kattaa
    lukuvuoden. Peilaa luokittelu/lukuvuosi.kattaa-logiikkaa, jotta vuosirajaus
    voidaan tehdä kannassa (sivutus, DISTINCT). Vuosisadan ylitys YYYY-YY:ssä
    jätetty huomiotta — ei esiinny todellisissa lyhyissä OPS-kausissa.
    """
    alku, loppu = lv._parsi_vuodet(lukuvuosi)
    alku_sql = f"CAST(SUBSTRING_INDEX({sarake}, '-', 1) AS UNSIGNED)"
    loppu_sql = (
        f"(CASE WHEN CHAR_LENGTH(SUBSTRING_INDEX({sarake}, '-', -1)) = 4 "
        f"      THEN CAST(SUBSTRING_INDEX({sarake}, '-', -1) AS UNSIGNED) "
        f"      ELSE {alku_sql} DIV 100 * 100 + CAST(SUBSTRING_INDEX({sarake}, '-', -1) AS UNSIGNED) END)"
    )
    return f"{alku_sql} <= %s AND {loppu_sql} >= %s", [alku, loppu]


def _tutkimus_kurssi_scope(tid: int) -> tuple[str | None, list]:
    """SQL-WHERE + parametrit jotka rajaavat Kurssi-rivit tutkimuksen korkeakouluihin
    ja lukuvuoteen (OPS-kausi kattaa lukuvuoden). (None, None) jos rajaus puuttuu."""
    tutkimus = hae_tutkimus(tid)
    korkeakoulut = hae_tutkimuksen_korkeakoulut(tid)
    lukuvuosi = (tutkimus or {}).get("Lukuvuosi")
    if not korkeakoulut or not lukuvuosi:
        return None, None
    paikat = ",".join(["%s"] * len(korkeakoulut))
    vuosi_sql, vuosi_params = _vuosi_kattaa_sql("k.Opetusvuosi", lukuvuosi)
    where = f"k.KKID IN ({paikat}) AND {vuosi_sql}"
    return where, [*korkeakoulut, *vuosi_params]


def hae_tutkimuksen_tilamaarat(tid: int) -> dict:
    """Tutkimuksen kurssimäärät tiloittain (mukana/odottaa/hylätty), rajattuna
    korkeakouluihin ja lukuvuoteen. Kevyt COUNT — välilehtien lukuihin."""
    maarat = {"mukana": 0, "odottaa": 0, "hylätty": 0}
    where, params = _tutkimus_kurssi_scope(tid)
    if where is None:
        return maarat
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                f"SELECT kl.Mukana, COUNT(*) FROM Kurssi k "
                f"LEFT JOIN Kurssiluokitus kl ON k.KID = kl.KID AND kl.TID = %s "
                f"WHERE {where} GROUP BY kl.Mukana",
                (tid, *params),
            )
            for mukana, n in kursori.fetchall():
                if mukana is None:
                    maarat["odottaa"] = n
                elif mukana == 1:
                    maarat["mukana"] = n
                else:
                    maarat["hylätty"] = n
    return maarat


def hae_kurssit_luokituksilla(tid: int, tila: str | None = None,
                              sivu: int = 0, koko: int | None = None) -> list[dict]:
    """Tutkimuksen kurssit luokitustiloineen — rajattuna korkeakouluihin ja
    lukuvuoteen. Valinnainen tila-välilehti (mukana/odottaa/hylätty) ja sivutus
    (koko=None palauttaa kaikki). Lukuvuosi on kova rajaus.
    """
    where, params = _tutkimus_kurssi_scope(tid)
    if where is None:
        return []
    tila_sql = f" AND {_TILA_EHTO[tila]}" if tila in _TILA_EHTO else ""
    raja_sql, raja_params = "", []
    if koko:
        raja_sql = " LIMIT %s OFFSET %s"
        raja_params = [koko, max(0, sivu) * koko]
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                f"SELECT k.KID, k.KKID, k.LahdeId, k.KurssiNimi, k.Koodi, k.Taso, k.Oppiaine, "
                f"k.Opintopisteet, k.Opetusvuosi, kl.Mukana, kl.Luokitteluperuste "
                f"FROM Kurssi k LEFT JOIN Kurssiluokitus kl ON k.KID = kl.KID AND kl.TID = %s "
                f"WHERE {where}{tila_sql} ORDER BY k.KurssiNimi{raja_sql}",
                (tid, *params, *raja_params),
            )
            return _rivit_dikteina(kursori)


def hae_hitl_historia(tid: int) -> list[dict]:
    """Kaikki HITL-korjaukset tälle tutkimukselle vanhimmasta uusimpaan."""
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                """SELECT KID, UusiTila, Perustelu, KayttajaNimi, Aikaleima
                   FROM HitlKorjaus WHERE TID = %s ORDER BY HID ASC""",
                (tid,),
            )
            return _rivit_dikteina(kursori)


# --- Kurssiluokitus ---

def aseta_luokitus(tid: int, kid: int, mukana: bool | None, perustelu: str,
                   malli: str = "", tiiviste: str | None = None) -> None:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                """INSERT INTO Kurssiluokitus (TID, KID, Mukana, Luokitteluperuste, Malli, Kehotetiiviste)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE Mukana = VALUES(Mukana),
                       Luokitteluperuste = VALUES(Luokitteluperuste), Malli = VALUES(Malli),
                       Kehotetiiviste = VALUES(Kehotetiiviste)""",
                (tid, kid, mukana, perustelu, malli, tiiviste),
            )


def hae_luokitukset(tid: int, mukana: bool | None = None) -> list[dict]:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            if mukana is None:
                kursori.execute("SELECT * FROM Kurssiluokitus WHERE TID = %s", (tid,))
            else:
                kursori.execute("SELECT * FROM Kurssiluokitus WHERE TID = %s AND Mukana = %s", (tid, mukana))
            return _rivit_dikteina(kursori)


def hae_tutkimuksen_tilanne(tid: int) -> dict:
    """Tutkimuksen suppilo (funnel): kuinka kurssit karsiutuvat vaihe vaiheelta.

    Vuosi- ja oppilaitosrajaus ovat kovia (rajaavat ehdokasjoukon); meta- ja
    LLM-luokitus jakavat in-scope-kurssit odottaviin/hylättyihin/hyväksyttyihin.
    Meta- ja LLM-hylkäys erotetaan Luokitteluperusteen "meta:"-etuliitteestä.
    """
    tutkimus = hae_tutkimus(tid)
    lukuvuosi = (tutkimus or {}).get("Lukuvuosi")
    korkeakoulut = set(hae_tutkimuksen_korkeakoulut(tid))
    kurssit = hae_kurssit()
    kursseja_yht = len(kurssit)

    vuosi_lapi = [k for k in kurssit
                  if lukuvuosi and _kattaa_turvallinen(k.get("Opetusvuosi"), lukuvuosi)]
    in_scope = [k for k in vuosi_lapi if k["KKID"] in korkeakoulut]
    in_scope_kid = {k["KID"] for k in in_scope}

    luok = {l["KID"]: l for l in hae_luokitukset(tid) if l["KID"] in in_scope_kid}
    hyl_meta = hyl_llm = odottaa_llm = hyvaksytty = 0
    for l in luok.values():
        mukana = l.get("Mukana")
        if mukana in (1, True):
            hyvaksytty += 1
        elif mukana is None:
            odottaa_llm += 1
        elif (l.get("Luokitteluperuste") or "").startswith("meta:"):
            hyl_meta += 1
        else:
            hyl_llm += 1

    return {
        "kursseja_yht": kursseja_yht,
        "vuosi_lapi": len(vuosi_lapi),
        "vuosi_hyl": kursseja_yht - len(vuosi_lapi),
        "oppilaitos_lapi": len(in_scope),
        "oppilaitos_hyl": len(vuosi_lapi) - len(in_scope),
        "odottaa_meta": len(in_scope) - len(luok),
        "hyl_meta": hyl_meta,
        "odottaa_llm": odottaa_llm,
        "hyl_llm": hyl_llm,
        "hyvaksytty": hyvaksytty,
    }


def hae_arvioimattomat(tid: int) -> list[dict]:
    """Mukaan otetut kurssit, joille ei vielä ole kaikkia ei-tyhjiä vastauksia tässä tutkimuksessa."""
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute("""
                SELECT k.*
                FROM Kurssi k
                JOIN Kurssiluokitus kl ON k.KID = kl.KID AND kl.TID = %s AND kl.Mukana = 1
                WHERE (
                    SELECT COUNT(*) FROM Vastaukset v
                    JOIN Kysymykset ky ON v.KysID = ky.KysID
                    WHERE ky.TID = %s AND v.KID = k.KID AND v.Vastaus != ''
                ) < (SELECT COUNT(*) FROM Kysymykset WHERE TID = %s)
                ORDER BY k.KurssiNimi
            """, (tid, tid, tid))
            return _rivit_dikteina(kursori)


# --- HITL-korjaukset ---

def tallenna_hitl_korjaus(tid: int, kid: int, uusi_tila: bool, perustelu: str,
                          nimi: str, sahkoposti: str) -> None:
    """Tallentaa ihmisen tekemän luokittelun ohituksen ja päivittää Kurssiluokitus.Mukana."""
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                """INSERT INTO HitlKorjaus (TID, KID, UusiTila, Perustelu, KayttajaNimi, Sahkoposti)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (tid, kid, uusi_tila, perustelu, nimi, sahkoposti),
            )
            kursori.execute(
                "UPDATE Kurssiluokitus SET Mukana = %s WHERE TID = %s AND KID = %s",
                (uusi_tila, tid, kid),
            )


# --- Arviokommentit ---

def hae_arviokommentit_kaikki(tid: int) -> list[dict]:
    """Kaikki ihmiskommentit tälle tutkimukselle."""
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                "SELECT KID, KysID, Kommentti FROM ArvioKommentti WHERE TID = %s",
                (tid,),
            )
            return _rivit_dikteina(kursori)


def hae_arviokommentti(tid: int, kid: int, kysid: int) -> str:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                "SELECT Kommentti FROM ArvioKommentti WHERE TID=%s AND KID=%s AND KysID=%s",
                (tid, kid, kysid),
            )
            rivi = kursori.fetchone()
            return rivi[0] if rivi else ""


def aseta_arviokommentti(tid: int, kid: int, kysid: int, kommentti: str) -> None:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                """INSERT INTO ArvioKommentti (TID, KID, KysID, Kommentti)
                   VALUES (%s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE Kommentti = VALUES(Kommentti)""",
                (tid, kid, kysid, kommentti),
            )


# --- Kurssiarviointi ---

def aseta_arviointi(tid: int, kid: int, arviointi: str, perustelu: str) -> None:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                """INSERT INTO Kurssiarviointi (TID, KID, Arviointi, Perustelu)
                   VALUES (%s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE Arviointi = VALUES(Arviointi), Perustelu = VALUES(Perustelu)""",
                (tid, kid, arviointi, perustelu),
            )


def hae_arvioinnit(tid: int) -> list[dict]:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute("SELECT * FROM Kurssiarviointi WHERE TID = %s", (tid,))
            return _rivit_dikteina(kursori)


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


def aseta_raportti_osio(tid: int, avain: str, teksti: str) -> None:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                """INSERT INTO RaporttiOsio (TID, OsioAvain, Teksti)
                   VALUES (%s, %s, %s)
                   ON DUPLICATE KEY UPDATE Teksti = VALUES(Teksti)""",
                (tid, avain, teksti),
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


# --- Raporttitilastot ---

def _kattavat_kaudet(kursori, lukuvuosi: str | None) -> list[str]:
    """Aineiston Opetusvuosi-arvot, jotka kattavat tutkimuksen lukuvuoden.

    Tyhjä lukuvuosi (vanha tutkimus) → kaikki kaudet (ei vuosirajausta).
    """
    kursori.execute("SELECT DISTINCT Opetusvuosi FROM Kurssi")
    kaikki = [r[0] for r in kursori.fetchall()]
    if not lukuvuosi:
        return kaikki
    return [k for k in kaikki if lv.kattaa(k, lukuvuosi)]


def hae_tilastot_yliopistoittain(tid: int) -> list[dict]:
    """Per-yliopisto-tilastot raporttia varten.

    Rajattu tutkimukseen valittuihin korkeakouluihin ja niihin kursseihin,
    joiden OPS-kausi kattaa tutkimuksen lukuvuoden. Tyhjä valinta/lukuvuosi
    (vanha tutkimus) → ei rajausta kyseisen ulottuvuuden osalta.
    """
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute("SELECT Lukuvuosi FROM Tutkimus WHERE TID = %s", (tid,))
            rivi = kursori.fetchone()
            lukuvuosi = rivi[0] if rivi else None
            kkid_lista = hae_tutkimuksen_korkeakoulut(tid)
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
            # Lisää HITL-lukumäärä per yliopisto
            kursori.execute("""
                SELECT k.KKID, COUNT(DISTINCT hk.HID) AS HitlLkm
                FROM HitlKorjaus hk
                JOIN Kurssi k ON hk.KID = k.KID
                WHERE hk.TID = %s
                GROUP BY k.KKID
            """, (tid,))
            hitl = {r[0]: r[1] for r in kursori.fetchall()}
            for r in rivit:
                r["HitlLkm"] = hitl.get(r["KKID"], 0)
            return rivit
