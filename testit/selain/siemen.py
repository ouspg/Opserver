"""Selaintestien deterministinen synteettinen data (ei oikeaa dataa, ei verkkoa).

Tutkimus `esr_kyber` (lukuvuosi 2026-2027) kolmessa korkeakoulussa. KURSSEJA kurssia
korkeakoulua kohden; joka KID % 10:
  0–1 → mukana (Kurssiluokitus.Mukana=1 + arviointivastaukset kaikkiin kysymyksiin)
  2–6 → hylätty (Mukana=0)
  7–9 → odottaa (ei luokitusta)
Joka viidennellä kurssilla on myös vanhempi versio (2025-2027, kattaa tutkimuksen lukuvuoden
ja luokitellaan samoin) → Kurssit-sivun vuosivalitsin.
Hylättyjä on > 4 sivua (100/sivu) → sivutus; mukana-listassa yli sivu.
Raportin lukujen poikkeustapaukset: ks. _raportin_poikkeamat."""
import json
import random

KOULUT = [("Oulun Yliopisto", "https://opas.peppi.oulu.fi", "Peppi"),
          ("Jyväskylän yliopisto", "https://sisu.jyu.fi", "Sisu"),
          ("Helsingin yliopisto", "https://sisu.helsinki.fi", "Sisu")]
KURSSEJA = 300
SLUG = "esr_kyber"
TASOT = ["Yleisopinnot", "Perusopinnot", "Aineopinnot", "Syventävät opinnot"]
OPPIAINEET = ["Tietotekniikka", "Tietojenkäsittelytiede", "Sähkötekniikka", "Matematiikka", "Kauppatiede"]
ALKUSANAT = ["Tietoturva", "Kyberturvallisuus", "Ohjelmointi", "Älykkäät järjestelmät", "Ääni ja signaalit",
             "Öljyteollisuuden automaatio", "Verkkotekniikka", "Kryptografia", "Tietokannat", "Algoritmit",
             "Käyttöjärjestelmät", "Ohjelmistotuotanto", "Etiikka ja tekoäly", "Riskienhallinta", "Pilvipalvelut"]
LOPPUSANAT = ["perusteet", "jatkokurssi", "projekti", "seminaari", "harjoitustyö", "syventävä kurssi"]
SANAT = ("opiskelija oppii tunnistamaan analysoimaan suojaamaan järjestelmiä verkkoja hyökkäyksiä "
         "uhkia riskejä menetelmiä työkaluja harjoituksia projekteja käytäntöjä").split()

KYSYMYKSET = [
    ("Mitä kyberturvallisuuden osaamisalueita kurssi kattaa?", "lista", None),
    ("Joustavuus: voiko kurssin suorittaa ajasta ja paikasta riippumatta?", "luokittelu",
     {"luokat": [{"nimi": "Täysin", "kuvaus": "Kokonaan etänä"},
                 {"nimi": "Osittain", "kuvaus": "Osa läsnäoloa"},
                 {"nimi": "Ei lainkaan", "kuvaus": "Läsnäolo"}]}),
    ("Soveltuvuus: soveltuuko kurssi ilman teknisiä esitietoja?", "luokittelu",
     {"luokat": [{"nimi": "Soveltuu kaikille", "kuvaus": "Ei esitietoja"},
                 {"nimi": "Edellyttää osaamista", "kuvaus": "Esitietoja"}]}),
    ("Työelämälähtöisyys: sisältääkö kurssi käytännön harjoituksia?", "asteikko",
     {"minimi": 1, "maksimi": 5, "pisteet": [{"arvo": 1, "kuvaus": "Teoreettinen"},
                                             {"arvo": 5, "kuvaus": "Käytännönläheinen"}]}),
    ("Mitä muuta kurssista on syytä huomata?", "vapaa_teksti", None),
]


def _lause(r, n):
    return " ".join(r.choice(SANAT) for _ in range(n)).capitalize() + "."


def tayta(kursori):
    """Täyttää tyhjän (alustus.sql) kannan. Sama data joka kerta (random.Random(1))."""
    r = random.Random(1)
    kursori.executemany("INSERT INTO Korkeakoulu (KouluNimi, OpsOsoite, OpsTyyppi) VALUES (%s, %s, %s)", KOULUT)
    kursori.execute(
        "INSERT INTO Tutkimus (TID, LuokittelunNimi, Slug, Lukuvuosi, Luokittelukehote, Tasorajaus, "
        "Arviointikehote, Raportointikehote) VALUES (1, %s, %s, '2026-2027', %s, '', %s, %s)",
        ("Kansallinen kyberturvallisuuden jatkuvan koulutuksen yhteistyöverkosto", SLUG,
         "Kartoita kyberturvallisuuden kurssit.", "Arvioi kurssin soveltuvuus.", "Kirjoita raportti."))
    kursori.executemany("INSERT INTO TutkimusKorkeakoulu (TID, KKID) VALUES (1, %s)",
                        [(i + 1,) for i in range(len(KOULUT))])
    kursori.executemany("INSERT INTO Kysymykset (TID, Kysymys, Luokittelu, LuokitteluMaarittely) VALUES (1, %s, %s, %s)",
                        [(k, t, json.dumps(m, ensure_ascii=False) if m else None) for k, t, m in KYSYMYKSET])

    kurssit, kuvaukset, luokitukset, vastaukset = [], [], [], []
    kid = 0
    for kkid in range(1, len(KOULUT) + 1):
        for i in range(KURSSEJA):
            nimi = f"{r.choice(ALKUSANAT)} {r.choice(LOPPUSANAT)} {r.randint(1, 999)}"
            perus = (kkid, f"L{kkid}_{i}", f"K{kkid}{i:03d}", nimi, r.choice(TASOT), r.choice(OPPIAINEET),
                     str(r.choice([2, 3, 5, 5, 5, 10])))
            versiot = ["2026-2027"] + (["2025-2027"] if i % 5 == 0 else [])
            for vuosi in versiot:
                kid += 1
                kurssit.append((kid, *perus, vuosi))
                kuvaukset.append((kid, " ".join(_lause(r, 12) for _ in range(4))))
                tila = kid % 10
                if tila <= 1:
                    luokitukset.append((kid, 1, "LLM: " + _lause(r, 10)))
                    vastaukset.append((1, kid, _lause(r, 6), None, None,
                                       json.dumps([r.choice(SANAT) for _ in range(3)], ensure_ascii=False)))
                    vastaukset.append((2, kid, _lause(r, 8), None, r.choice(["Täysin", "Osittain", "Ei lainkaan"]), None))
                    vastaukset.append((3, kid, _lause(r, 8), None, r.choice(["Soveltuu kaikille", "Edellyttää osaamista"]), None))
                    vastaukset.append((4, kid, _lause(r, 8), r.randint(1, 5), None, None))
                    vastaukset.append((5, kid, _lause(r, 10), None, None, None))
                elif tila <= 6:
                    luokitukset.append((kid, 0, "LLM: " + _lause(r, 10)))
    kursori.executemany("INSERT INTO Kurssi (KID, KKID, LahdeId, Koodi, KurssiNimi, Taso, Oppiaine, Opintopisteet, "
                        "Opetusvuosi) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)", kurssit)
    kursori.executemany("INSERT INTO KurssiKuvaus (KID, OpsKuvaus) VALUES (%s, %s)", kuvaukset)
    kursori.executemany("INSERT INTO Kurssiluokitus (TID, KID, Mukana, Luokitteluperuste, Malli) "
                        "VALUES (1, %s, %s, %s, 'testimalli')", luokitukset)
    kursori.executemany("INSERT INTO Vastaukset (TID, KysID, KID, Vastaus, Pisteet, Luokka, Lista, Malli) "
                        "VALUES (1, %s, %s, %s, %s, %s, %s, 'testimalli')", vastaukset)
    kursori.executemany("INSERT INTO RaporttiOsio (TID, OsioAvain, Teksti) VALUES (1, %s, %s)",
                        [("johdanto", "Johdanto: " + _lause(r, 30)), ("kurssit", "Kurssit: " + _lause(r, 30)),
                         ("arvioinnit", "Arvioinnit: " + _lause(r, 30))])
    _raportin_poikkeamat(kursori)


def _raportin_poikkeamat(kursori):
    """Raportin lukujen erikoistapaukset KID:n mukaan (ei muuta Mukana-lukuja eikä
    satunnaisjonoa, joten muiden testien data pysyy ennallaan):
      KID % 10 == 3  meta-suodatuksen hylkäämä (Luokitteluperuste 'meta: …')
      KID % 50 == 2  LLM otti, ihminen poisti (llm_virhe) → vanhat vastaukset jäävät kantaan
      KID % 50 == 11 LLM hylkäsi, ihminen lisäsi (riittamaton_opas)
      KID % 50 == 20 meta hylkäsi, ihminen lisäsi (juurisyy merkitsemättä)
      KID % 50 == 4  ihminen lisäsi ja poisti → palautettu alkutilaan (ei nettomuutosta)
      KID % 50 == 7  meta läpäisty, odottaa LLM:ää (Mukana NULL, 'meta: odottaa LLM-seulontaa')
      KID % 20 == 1  joustavuusluokka väärällä kirjainkoolla + reunavälilyönnillä
      KID == 10      joustavuusluokka tuntematon ('Ehkä')
      KID % 50 == 1  ihminen hyväksyi LLM:n mukaan-päätöksen (HITL-kattavuus)"""
    kursori.execute("UPDATE Kurssiluokitus SET Luokitteluperuste = 'meta: taso ei vastaa rajausta' "
                    "WHERE TID = 1 AND (KID % 10 = 3 OR KID % 50 = 20)")
    kursori.execute("INSERT INTO Kurssiluokitus (TID, KID, Mukana, Luokitteluperuste) "
                    "SELECT 1, KID, NULL, 'meta: odottaa LLM-seulontaa' FROM Kurssi WHERE MOD(KID, 50) = 7")
    kursori.execute("INSERT INTO Vastaukset (TID, KysID, KID, Vastaus, Pisteet, Luokka, Malli) "
                    "SELECT 1, ky.KysID, kl.KID, 'vanha arvio', IF(ky.KysID = 4, 5, NULL), "
                    "IF(ky.KysID = 2, 'Täysin', NULL), 'testimalli' FROM Kurssiluokitus kl "
                    "JOIN Kysymykset ky ON ky.TID = 1 AND ky.KysID IN (2, 4, 5) WHERE kl.TID = 1 AND kl.KID % 50 = 2")
    hitl = "INSERT INTO HitlKorjaus (TID, KID, UusiTila, Perustelu, KayttajaNimi, Sahkoposti, Juurisyy) " \
           "SELECT 1, KID, %s, 'testikorjaus', 'Testaaja', 't@example.com', %s FROM Kurssiluokitus " \
           "WHERE TID = 1 AND MOD(KID, 50) = %s"
    for tila, juurisyy, jaannos in [(0, "llm_virhe", 2), (1, "riittamaton_opas", 11), (1, None, 20),
                                    (1, "llm_virhe", 4), (0, "llm_virhe", 4)]:
        kursori.execute(hitl, (tila, juurisyy, jaannos))
    kursori.execute("UPDATE Vastaukset SET Luokka = CONCAT(' ', LOWER(Luokka), ' ') "
                    "WHERE TID = 1 AND KysID = 2 AND KID % 20 = 1")
    kursori.execute("UPDATE Vastaukset SET Luokka = 'Ehkä' WHERE TID = 1 AND KysID = 2 AND KID = 10")
    kursori.execute("UPDATE Kurssiluokitus SET KayttajaNimi = 'Hyväksyjä' WHERE TID = 1 AND KID % 50 = 1")
