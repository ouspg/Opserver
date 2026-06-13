from tietokanta.yhteys import yhteys


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

def lisaa_korkeakoulu(koulu_nimi: str, ops_osoite: str, ops_tyyppi: str) -> int:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                "INSERT INTO Korkeakoulu (KouluNimi, OpsOsoite, OpsTyyppi) VALUES (%s, %s, %s)",
                (koulu_nimi, ops_osoite, ops_tyyppi),
            )
            return kursori.lastrowid


def hae_korkeakoulut() -> list[dict]:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute("SELECT * FROM Korkeakoulu ORDER BY KouluNimi")
            return _rivit_dikteina(kursori)


def paivita_korkeakoulu(kkid: int, koulu_nimi: str, ops_osoite: str, ops_tyyppi: str) -> None:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                "UPDATE Korkeakoulu SET KouluNimi = %s, OpsOsoite = %s, OpsTyyppi = %s WHERE KKID = %s",
                (koulu_nimi, ops_osoite, ops_tyyppi, kkid),
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


def hae_kurssit(kkid: int | None = None) -> list[dict]:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            if kkid is not None:
                kursori.execute("SELECT * FROM Kurssi WHERE KKID = %s ORDER BY KurssiNimi", (kkid,))
            else:
                kursori.execute("SELECT * FROM Kurssi ORDER BY KurssiNimi")
            return _rivit_dikteina(kursori)


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

def lisaa_tutkimus(luokittelun_nimi: str, slug: str, luokittelukehote: str,
                   tasorajaus: str, oppiainerajaus: str, arviointikehote: str) -> int:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                "INSERT INTO Tutkimus (LuokittelunNimi, Slug, Luokittelukehote, Tasorajaus, Oppiainerajaus, Arviointikehote) VALUES (%s, %s, %s, %s, %s, %s)",
                (luokittelun_nimi, slug, luokittelukehote, tasorajaus, oppiainerajaus, arviointikehote),
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


def paivita_tutkimus(tid: int, luokittelun_nimi: str, slug: str, luokittelukehote: str,
                     tasorajaus: str, oppiainerajaus: str, arviointikehote: str) -> None:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                "UPDATE Tutkimus SET LuokittelunNimi=%s, Slug=%s, Luokittelukehote=%s, Tasorajaus=%s, Oppiainerajaus=%s, Arviointikehote=%s WHERE TID=%s",
                (luokittelun_nimi, slug, luokittelukehote, tasorajaus, oppiainerajaus, arviointikehote, tid),
            )


def poista_tutkimus(tid: int) -> None:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute("DELETE FROM Tutkimus WHERE TID = %s", (tid,))


# --- Kysymykset ---

def lisaa_kysymys(tid: int, kysymys: str) -> int:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                "INSERT INTO Kysymykset (TID, Kysymys) VALUES (%s, %s)",
                (tid, kysymys),
            )
            return kursori.lastrowid


def hae_kysymykset(tid: int) -> list[dict]:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                "SELECT * FROM Kysymykset WHERE TID = %s ORDER BY KysID",
                (tid,),
            )
            return _rivit_dikteina(kursori)


def paivita_kysymys(kysid: int, kysymys: str) -> None:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                "UPDATE Kysymykset SET Kysymys = %s WHERE KysID = %s",
                (kysymys, kysid),
            )


def poista_kysymys(kysid: int) -> None:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute("DELETE FROM Kysymykset WHERE KysID = %s", (kysid,))


# --- Vastaukset ---

def aseta_vastaus(kysid: int, kid: int, vastaus: str, malli: str = "") -> None:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                """INSERT INTO Vastaukset (KysID, KID, Vastaus, Malli)
                   VALUES (%s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE Vastaus = VALUES(Vastaus), Malli = VALUES(Malli)""",
                (kysid, kid, vastaus, malli),
            )


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
            return _rivit_dikteina(kursori)


# --- Luokittelun apufunktiot ---

def hae_luokittelemattomat(tid: int) -> list[dict]:
    """Kurssit, jotka odottavat LLM-seulontaa (ei riviä tai Mukana IS NULL)."""
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute("""
                SELECT k.*
                FROM Kurssi k
                LEFT JOIN Kurssiluokitus kl ON k.KID = kl.KID AND kl.TID = %s
                WHERE kl.KID IS NULL OR kl.Mukana IS NULL
                ORDER BY k.KurssiNimi
            """, (tid,))
            return _rivit_dikteina(kursori)


def hae_kurssit_luokituksilla(tid: int) -> list[dict]:
    """Kaikki kurssit ja niiden luokitustila tässä tutkimuksessa."""
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute("""
                SELECT k.KID, k.KurssiNimi, k.Koodi, k.Taso, k.Oppiaine,
                       k.Opintopisteet, k.Opetusvuosi,
                       kl.Mukana, kl.Luokitteluperuste
                FROM Kurssi k
                LEFT JOIN Kurssiluokitus kl ON k.KID = kl.KID AND kl.TID = %s
                ORDER BY k.KurssiNimi
            """, (tid,))
            return _rivit_dikteina(kursori)


# --- Kurssiluokitus ---

def aseta_luokitus(tid: int, kid: int, mukana: bool | None, perustelu: str, malli: str = "") -> None:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                """INSERT INTO Kurssiluokitus (TID, KID, Mukana, Luokitteluperuste, Malli)
                   VALUES (%s, %s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE Mukana = VALUES(Mukana),
                       Luokitteluperuste = VALUES(Luokitteluperuste), Malli = VALUES(Malli)""",
                (tid, kid, mukana, perustelu, malli),
            )


def hae_luokitukset(tid: int, mukana: bool | None = None) -> list[dict]:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            if mukana is None:
                kursori.execute("SELECT * FROM Kurssiluokitus WHERE TID = %s", (tid,))
            else:
                kursori.execute("SELECT * FROM Kurssiluokitus WHERE TID = %s AND Mukana = %s", (tid, mukana))
            return _rivit_dikteina(kursori)


def hae_arvioimattomat(tid: int) -> list[dict]:
    """Mukaan otetut kurssit, joille ei vielä ole kaikkia vastauksia tässä tutkimuksessa."""
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute("""
                SELECT k.*
                FROM Kurssi k
                JOIN Kurssiluokitus kl ON k.KID = kl.KID AND kl.TID = %s AND kl.Mukana = 1
                WHERE (
                    SELECT COUNT(*) FROM Vastaukset v
                    JOIN Kysymykset ky ON v.KysID = ky.KysID
                    WHERE ky.TID = %s AND v.KID = k.KID
                ) < (SELECT COUNT(*) FROM Kysymykset WHERE TID = %s)
                ORDER BY k.KurssiNimi
            """, (tid, tid, tid))
            return _rivit_dikteina(kursori)


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
