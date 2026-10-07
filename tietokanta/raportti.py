"""Raporttiosiot, raportin tuoreus ja raportin tilastot."""
from tietokanta.yhteys import yhteys
from tietokanta._yhteiset import (
    _hae_arvo, _hae_kaikki, _hae_yksi, _kattaa_turvallinen, _rajaus, _rivit_dikteina, _suorita,
    luokitus_suppilo_sql,
)


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


def laske_hitl_vastaukset(tid: int, jalkeen=None) -> int:
    """Ihmisen korjaamien vastausten määrä (COUNT, ei rivinoutoa); jalkeen annettuna
    vain sen jälkeen tehdyt/muokatut."""
    aika_sql, params = (" AND Aikaleima > %s", (tid, jalkeen)) if jalkeen is not None else ("", (tid,))
    return int(_hae_arvo(
        f"SELECT COUNT(*) FROM Vastaukset WHERE TID = %s AND Malli IS NULL{aika_sql}", params,
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
    """Per-yliopisto-tilastot raporttia varten: suppilo + HITL-korjaukset.

    Rajattu tutkimukseen valittuihin korkeakouluihin ja niihin kursseihin,
    joiden OPS-kausi kattaa tutkimuksen lukuvuoden. Tyhjä valinta/lukuvuosi
    (vanha tutkimus) → ei rajausta kyseisen ulottuvuuden osalta.

    Suppilo (luokitus_suppilo_sql + johdetut): KurssiYhteensa → OdottaaMeta (ei
    luokitusriviä) | MetaHylkaama (meta-suodatuksen alkuperäinen hylkäys) | LLMlle
    (meta läpäissyt) = OdottaaLLM + LLMKasitelty. Lopputila HITL:n jälkeen:
    Mukana, Hylatty (= MetaHylatty + LLMHylatty).
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
                SELECT ko.KKID, ko.KouluNimi, COUNT(k.KID) AS KurssiYhteensa,
                       {luokitus_suppilo_sql()}
                FROM Korkeakoulu ko
                LEFT JOIN Kurssi k ON k.KKID = ko.KKID {vuosi_ehto}
                LEFT JOIN Kurssiluokitus kl ON kl.KID = k.KID AND kl.TID = %s
                {kk_ehto}
                GROUP BY ko.KKID, ko.KouluNimi
                ORDER BY ko.KouluNimi
            """, (*kaudet, tid, *kkid_lista))
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
                for avain in ("KurssiYhteensa", "Mukana", "OdottaaLLM", "MetaHylatty",
                              "LLMHylatty", "Luokiteltu", "MetaHylkaama"):
                    r[avain] = int(r[avain] or 0)
                r["OdottaaMeta"] = r["KurssiYhteensa"] - r["Luokiteltu"]
                r["LLMlle"] = r["Luokiteltu"] - r["MetaHylkaama"]
                r["LLMKasitelty"] = r["LLMlle"] - r["OdottaaLLM"]
                r["Hylatty"] = r["MetaHylatty"] + r["LLMHylatty"]
                r["HitlLkm"] = hitl.get(r["KKID"], 0)
                kurssit, opas, llm, tuntematon = juurisyy.get(r["KKID"], (0, 0, 0, 0))
                r["HitlKursseja"] = int(kurssit or 0)
                r["RiittamatonOpas"] = int(opas or 0)
                r["LlmVirhe"] = int(llm or 0)
                r["TuntematonSyy"] = int(tuntematon or 0)
            return rivit
