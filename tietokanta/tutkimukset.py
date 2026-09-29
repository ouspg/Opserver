"""Tutkimukset, niiden korkeakoulut ja arviointikysymykset."""
from tietokanta.yhteys import yhteys
from tietokanta._yhteiset import (
    _KUVAUS_JOIN, _hae_arvo, _hae_kaikki, _hae_sarake, _hae_yksi, _json, _pura_json,
    _rivit_dikteina, _suorita,
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


# --- Kysymykset ---

def lisaa_kysymys(tid: int, kysymys: str, luokittelu: str = "vapaa_teksti",
                  luokittelu_maarittely: dict | None = None) -> int:
    maarittely_json = _json(luokittelu_maarittely or None)
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
    return _pura_json(rivit, "LuokitteluMaarittely")


def paivita_kysymys(kysid: int, kysymys: str, luokittelu: str = "vapaa_teksti",
                    luokittelu_maarittely: dict | None = None) -> None:
    maarittely_json = _json(luokittelu_maarittely or None)
    _suorita(
        "UPDATE Kysymykset SET Kysymys = %s, Luokittelu = %s, LuokitteluMaarittely = %s WHERE KysID = %s",
        (kysymys, luokittelu, maarittely_json, kysid),
    )


def poista_kysymys(kysid: int) -> None:
    _suorita("DELETE FROM Kysymykset WHERE KysID = %s", (kysid,))
