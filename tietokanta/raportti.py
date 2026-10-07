"""Raporttiosiot, raportin tuoreus ja raportin tilastot."""
from tietokanta.yhteys import yhteys
from tietokanta._yhteiset import (
    _hae_arvo, _hae_kaikki, _hae_yksi, _kattaa_turvallinen, _rajaus, _rivit_dikteina, _suorita,
    luokitus_suppilo_sql, meta_hylkays_sql,
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


# HITL-korjausten suunta ja kumottu vaihe kunkin kurssin VIIMEISIMMÄSTÄ korjauksesta
# (MAX(HID)), jotta edestakaisin korjattu kurssi ei tuplaannu ja lopputila kertoo
# ihmisen lopullisen kannan. UusiTila = suunta (1 = lisätty, 0 = poistettu).
# Meta = kumottiinko meta-suodatuksen päätös (Luokitteluperuste säilyy korjauksessa).
# Muutos = poikkeaako lopputila alkuperäisestä automaattisesta päätöksestä:
# meta-hylkäyksen alkutila on 0, muuten alkutila on ENSIMMÄISEN korjauksen
# vastakohta (korjaus kääntää aina silloisen tilan; HITL-kursseja ei ajeta LLM:llä
# uudelleen). Muutos = 0 → käännetty takaisin alkutilaan, ei nettomuutosta.
_HITL_SUUNTA_SQL = f"""
    SELECT k.KKID, uusin.UusiTila, uusin.Meta, uusin.Juurisyy, uusin.Muutos, COUNT(*)
    FROM (
        SELECT v.KID, hk.UusiTila, hk.Juurisyy, {meta_hylkays_sql()} AS Meta,
               hk.UusiTila <> IF({meta_hylkays_sql()}, 0, 1 - eka.UusiTila) AS Muutos
        FROM (SELECT KID, MIN(HID) AS MinHID, MAX(HID) AS MaxHID
              FROM HitlKorjaus WHERE TID = %s GROUP BY KID) v
        JOIN HitlKorjaus hk ON hk.HID = v.MaxHID
        JOIN HitlKorjaus eka ON eka.HID = v.MinHID
        LEFT JOIN Kurssiluokitus kl ON kl.TID = %s AND kl.KID = v.KID
    ) uusin
    JOIN Kurssi k ON k.KID = uusin.KID
    GROUP BY k.KKID, uusin.UusiTila, uusin.Meta, uusin.Juurisyy, uusin.Muutos
"""
_SUUNNAT = {1: "Lisatty", 0: "Poistettu"}
_SYYT = {"riittamaton_opas": ("Opas", "RiittamatonOpas"), "llm_virhe": ("LlmVirhe", "LlmVirhe"),
         None: ("Tuntematon", "TuntematonSyy")}


def _tyhjat_hitl_suunnat() -> dict:
    """HITL-kentät nollina: {Lisatty,Poistettu}×{Meta,LLM,Opas,LlmVirhe,Tuntematon},
    Palautettu, HitlKursseja ja nettomuutosten juurisyyt (RiittamatonOpas, LlmVirhe,
    TuntematonSyy)."""
    kentat = {f"{suunta}{osa}": 0 for suunta in _SUUNNAT.values()
              for osa in ("Meta", "LLM", "Opas", "LlmVirhe", "Tuntematon")}
    return {**kentat, "Palautettu": 0, "HitlKursseja": 0,
            "RiittamatonOpas": 0, "LlmVirhe": 0, "TuntematonSyy": 0}


def _kokoa_hitl_suunnat(ryhmat) -> dict[int, dict]:
    """_HITL_SUUNTA_SQL:n ryhmät → {KKID: HITL-kentät}. Tuntematon juurisyykoodi
    lasketaan merkitsemättömäksi."""
    tulos: dict[int, dict] = {}
    for kkid, uusi_tila, meta, juurisyy, muutos, lkm in ryhmat:
        r = tulos.setdefault(kkid, _tyhjat_hitl_suunnat())
        lkm = int(lkm)
        r["HitlKursseja"] += lkm
        if not int(muutos):
            r["Palautettu"] += lkm
            continue
        suunta = _SUUNNAT[int(uusi_tila)]
        syy, yhteensa = _SYYT.get(juurisyy, _SYYT[None])
        r[f"{suunta}{'Meta' if int(meta) else 'LLM'}"] += lkm
        r[f"{suunta}{syy}"] += lkm
        r[yhteensa] += lkm
    return tulos


def hae_tilastot_yliopistoittain(tid: int) -> list[dict]:
    """Per-yliopisto-tilastot raporttia varten: suppilo + HITL-korjaukset.

    Rajattu tutkimukseen valittuihin korkeakouluihin ja niihin kursseihin,
    joiden OPS-kausi kattaa tutkimuksen lukuvuoden. Tyhjä valinta/lukuvuosi
    (vanha tutkimus) → ei rajausta kyseisen ulottuvuuden osalta.

    Suppilo (luokitus_suppilo_sql + johdetut): KurssiYhteensa → OdottaaMeta (ei
    luokitusriviä) | MetaHylkaama (meta-suodatuksen alkuperäinen hylkäys) | LLMlle
    (meta läpäissyt) = OdottaaLLM + LLMKasitelty. Lopputila HITL:n jälkeen:
    Mukana, Hylatty (= MetaHylatty + LLMHylatty). HITL-kentät: ks. _HITL_SUUNTA_SQL;
    MukanaTarkistettu = mukana-kurssit, jotka ihminen on hyväksynyt tai korjannut
    (hylättyjen läpikäynnistä ei ole kirjausta).
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
                       {luokitus_suppilo_sql()},
                       COALESCE(SUM(kl.Mukana = 1 AND (kl.KayttajaNimi IS NOT NULL OR hk.KID IS NOT NULL)), 0)
                           AS MukanaTarkistettu
                FROM Korkeakoulu ko
                LEFT JOIN Kurssi k ON k.KKID = ko.KKID {vuosi_ehto}
                LEFT JOIN Kurssiluokitus kl ON kl.KID = k.KID AND kl.TID = %s
                LEFT JOIN (SELECT DISTINCT KID FROM HitlKorjaus WHERE TID = %s) hk ON hk.KID = k.KID
                {kk_ehto}
                GROUP BY ko.KKID, ko.KouluNimi
                ORDER BY ko.KouluNimi
            """, (*kaudet, tid, tid, *kkid_lista))
            rivit = _rivit_dikteina(kursori)
            # HitlLkm = korjaustapahtumien määrä per yliopisto.
            kursori.execute("""
                SELECT k.KKID, COUNT(DISTINCT hk.HID) AS HitlLkm
                FROM HitlKorjaus hk
                JOIN Kurssi k ON hk.KID = k.KID
                WHERE hk.TID = %s
                GROUP BY k.KKID
            """, (tid,))
            hitl = {r[0]: r[1] for r in kursori.fetchall()}
            kursori.execute(_HITL_SUUNTA_SQL, (tid, tid))
            suunnat = _kokoa_hitl_suunnat(kursori.fetchall())

            for r in rivit:
                for avain in ("KurssiYhteensa", "Mukana", "OdottaaLLM", "MetaHylatty",
                              "LLMHylatty", "Luokiteltu", "MetaHylkaama", "MukanaTarkistettu"):
                    r[avain] = int(r[avain] or 0)
                r["OdottaaMeta"] = r["KurssiYhteensa"] - r["Luokiteltu"]
                r["LLMlle"] = r["Luokiteltu"] - r["MetaHylkaama"]
                r["LLMKasitelty"] = r["LLMlle"] - r["OdottaaLLM"]
                r["Hylatty"] = r["MetaHylatty"] + r["LLMHylatty"]
                r["HitlLkm"] = int(hitl.get(r["KKID"], 0))
                r.update(suunnat.get(r["KKID"]) or _tyhjat_hitl_suunnat())
            return rivit
