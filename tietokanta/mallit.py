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

def lisaa_kurssi(kkid: int, kurssi_nimi: str, taso: str, oppiaine: str, opintopisteet: float, ops_kuvaus: str) -> int:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                "INSERT INTO Kurssi (KKID, KurssiNimi, Taso, Oppiaine, Opintopisteet, OpsKuvaus) VALUES (%s, %s, %s, %s, %s, %s)",
                (kkid, kurssi_nimi, taso, oppiaine, opintopisteet, ops_kuvaus),
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


def hae_kurssi(kid: int) -> dict | None:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute("SELECT * FROM Kurssi WHERE KID = %s", (kid,))
            return _rivi_diktina(kursori)


# --- Tutkimus ---

def lisaa_tutkimus(luokittelun_nimi: str, luokittelukehote: str, tasorajaus: str, oppiainerajaus: str, arviointikehote: str) -> int:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                "INSERT INTO Tutkimus (LuokittelunNimi, Luokittelukehote, Tasorajaus, Oppiainerajaus, Arviointikehote) VALUES (%s, %s, %s, %s, %s)",
                (luokittelun_nimi, luokittelukehote, tasorajaus, oppiainerajaus, arviointikehote),
            )
            return kursori.lastrowid


def hae_tutkimukset() -> list[dict]:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute("SELECT * FROM Tutkimus ORDER BY LuokittelunNimi")
            return _rivit_dikteina(kursori)


def hae_tutkimus(tid: int) -> dict | None:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute("SELECT * FROM Tutkimus WHERE TID = %s", (tid,))
            return _rivi_diktina(kursori)


# --- Kurssiluokitus ---

def aseta_luokitus(tid: int, kid: int, mukana: bool | None, perustelu: str) -> None:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            kursori.execute(
                """INSERT INTO Kurssiluokitus (TID, KID, Mukana, Luokitteluperuste)
                   VALUES (%s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE Mukana = VALUES(Mukana), Luokitteluperuste = VALUES(Luokitteluperuste)""",
                (tid, kid, mukana, perustelu),
            )


def hae_luokitukset(tid: int, mukana: bool | None = None) -> list[dict]:
    with yhteys() as yht:
        with yht.cursor() as kursori:
            if mukana is None:
                kursori.execute("SELECT * FROM Kurssiluokitus WHERE TID = %s", (tid,))
            else:
                kursori.execute("SELECT * FROM Kurssiluokitus WHERE TID = %s AND Mukana = %s", (tid, mukana))
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
