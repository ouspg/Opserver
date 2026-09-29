"""Korkeakoulut ja kurssit (opinto-oppaiden hakutulokset)."""
from tietokanta.yhteys import yhteys, uudelleenyrita
from luokittelu import lukuvuosi as lv
from tietokanta._yhteiset import (
    _KUVAUS_JOIN, _hae_kaikki, _hae_sarake, _hae_yksi, _lisaa_rivit, _suorita,
    _vuosi_kattaa_sql,
)


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

# ponytail: uudelleenyritys vain kurssihaun pitkän ajon kutsuissa — muut kutsut
# ovat kertaluontoisia ja kaatuvat siististi. Lisää dekoraattori jos ne kaatuilevat.
@uudelleenyrita
def tallenna_kurssit(kkid: int, opetusvuosi: str, kurssit: list[dict]) -> None:
    """Tallentaa erän kursseja (upsert) kuvauksineen kolmella kierroksella.
    kurssit: {lahde_id, koodi, kurssi_nimi, taso, oppiaine, opintopisteet, ops_kuvaus}."""
    if not kurssit:
        return
    with yhteys() as yht:
        with yht.cursor() as kursori:
            _lisaa_rivit(
                kursori,
                "INSERT INTO Kurssi (KKID, LahdeId, Koodi, KurssiNimi, Taso, Oppiaine, Opintopisteet, Opetusvuosi)",
                [(kkid, k["lahde_id"], k["koodi"], k["kurssi_nimi"], k["taso"], k["oppiaine"],
                  k["opintopisteet"], opetusvuosi) for k in kurssit],
                """ON DUPLICATE KEY UPDATE Koodi = VALUES(Koodi), KurssiNimi = VALUES(KurssiNimi),
                       Taso = VALUES(Taso), Oppiaine = VALUES(Oppiaine),
                       Opintopisteet = VALUES(Opintopisteet)""",
            )
            lahde_idt = list({k["lahde_id"] for k in kurssit})
            kursori.execute(
                f"""SELECT LahdeId, KID FROM Kurssi WHERE KKID = %s AND Opetusvuosi = %s
                    AND LahdeId IN ({",".join(["%s"] * len(lahde_idt))})""",
                (kkid, opetusvuosi, *lahde_idt),
            )
            kidit = dict(kursori.fetchall())
            # Kuvaukset ovat isoja (JSON, kymmeniä kt) → pienemmät palat.
            _lisaa_rivit(
                kursori, "INSERT INTO KurssiKuvaus (KID, OpsKuvaus)",
                [(kidit[k["lahde_id"]], k["ops_kuvaus"]) for k in kurssit],
                "ON DUPLICATE KEY UPDATE OpsKuvaus = VALUES(OpsKuvaus)", koko=50,
            )


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
