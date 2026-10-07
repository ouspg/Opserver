"""LLM-raporttigenerointi: koostaa raporttiosiot tietokannasta ja täydentää LLM:llä."""
import json
from tietokanta import mallit
from llm import kutsu, tiiviste, kehotteet
from raportti.mittarit import (
    hitl_mittarit, hitl_yhteenveto_teksti, suppilo, suppilo_teksti, tilasto_taulukko,
)

OSIOT = ["johdanto", "kurssit", "arvioinnit"]


def raporttitiiviste(tutkimus: dict, tilastot: list[dict] | None = None,
                     kysymykset: list[dict] | None = None) -> str:
    """SHA-256-tiiviste lähdeaineistosta, josta raportti koottiin — raportin
    tuoreustarkistukseen. Muuttuu, jos jokin raporttiin vaikuttava tieto muuttuu:
    per-yliopisto-tilastot (luokitukset + HITL), kysymykset, arviointien tila,
    kommentit tai tutkimuksen kehotteet/rajaukset. Tilastot kattavat myös
    aikaleimattomat taulut (Kurssiluokitus), joten seulonnan uudelleenajo näkyy.

    tilastot/kysymykset: annettuna vältetään uudelleenhaku (aja() jakaa nämä)."""
    tid = tutkimus["TID"]
    if tilastot is None:
        tilastot = mallit.hae_tilastot_yliopistoittain(tid)
    if kysymykset is None:
        kysymykset = mallit.hae_kysymykset(tid)
    vastaus_tila = mallit.hae_vastaus_tiivisteet(tid)
    hitl_vastaukset = mallit.hae_hitl_vastaukset(tid)

    tilasto_osa = json.dumps(sorted(
        [r["KKID"], r["KurssiYhteensa"], r["LLMKasitelty"], r["Mukana"], r["Hylatty"],
         r.get("OdottaaMeta", 0), r.get("MetaHylkaama", 0), r.get("LLMlle", 0),
         r.get("OdottaaLLM", 0), r.get("LLMHylatty", 0), r.get("HitlLkm", 0), r.get("HitlKursseja", 0), r.get("RiittamatonOpas", 0),
         r.get("LlmVirhe", 0), r.get("TuntematonSyy", 0)]
        for r in tilastot), ensure_ascii=False)
    kysymys_osa = json.dumps(sorted(
        [k["KysID"], k.get("Kysymys") or "", k.get("Luokittelu") or "vapaa_teksti",
         json.dumps(k.get("LuokitteluMaarittely"), sort_keys=True, ensure_ascii=False)]
        for k in kysymykset), ensure_ascii=False)
    vastaus_osa = json.dumps(sorted(
        [kid, kysid, v.get("tiiviste") or "", bool(v.get("vastattu"))]
        for (kid, kysid), v in vastaus_tila.items()), ensure_ascii=False)
    # Ihmisen korjaukset mukaan signatuuriin: korjaus muuttaa raportin sisällön
    # samoin kuin uusi LLM-vastaus, joten raportti on sen jälkeen vanhentunut.
    korjaus_osa = json.dumps(sorted(
        [c["KID"], c["KysID"], c.get("Vastaus") or "", c.get("Luokka") or "",
         c.get("Pisteet"), c.get("KayttajaNimi") or ""] for c in hitl_vastaukset),
        ensure_ascii=False, default=str)
    kehote_osa = json.dumps([
        tutkimus.get("Luokittelukehote") or "", tutkimus.get("Arviointikehote") or "",
        tutkimus.get("Raportointikehote") or "", tutkimus.get("Tasorajaus") or "",
        tutkimus.get("Oppiainerajaus") or "",
    ], ensure_ascii=False)
    return tiiviste.laske(tilasto_osa, kysymys_osa, vastaus_osa, korjaus_osa, kehote_osa)


def _tuoreus(generointi_sig: str | None, tuoreustieto: dict | None) -> tuple[str, object]:
    """Ratkaisee tuoreuden tallennetuista signatuureista — EI laske tiivistettä
    (raskas laskenta on erillään, paivita_tuoreus). Palauttaa (tila, tarkistettu):
      - generointi_sig None → raportti generoitu ennen tuoreusseurantaa → tuntematon
      - tuoreustietoa ei vielä laskettu → tuntematon (taustatarkistus tulossa)
      - muuten vertailu tallennettuun tuoreussignatuuriin → ajan_tasalla/vanhentunut
    """
    if generointi_sig is None:
        return "tuntematon", None
    if not tuoreustieto or not tuoreustieto.get("Signatuuri"):
        return "tuntematon", None
    tila = "ajan_tasalla" if tuoreustieto["Signatuuri"] == generointi_sig else "vanhentunut"
    return tila, tuoreustieto.get("Tarkistettu")


def koosta_tilanne(tutkimus: dict) -> dict:
    """Kokoaa raportin tuoreustiedot status-näkymiä varten (CLIUI + WebUI).
    Curses- ja HTTP-riippumaton — palauttaa raakadatan, kumpikin UI muotoilee.

    Palauttaa {"generoitu": False} jos raporttia ei ole; muuten osioiden tila +
    aikaleimat, tuoreus (ajan_tasalla / vanhentunut / tuntematon), tuoreuden
    laskenta-aika (tarkistettu) ja generoinnin jälkeen tehtyjen HITL-korjausten
    ja kommenttien määrän.

    KEVYT: lukee viimeksi lasketun tuoreussignatuurin tallennettuna — ei laske
    raskasta lähdeaineiston tiivistettä (se ajetaan taustalla, paivita_tuoreus).
    """
    tid = tutkimus["TID"]
    tila_rivit = mallit.hae_raportti_tila(tid)
    if not tila_rivit:
        return {"generoitu": False}

    kartta = {r["OsioAvain"]: r for r in tila_rivit}
    osiot = [{"avain": a, "on": a in kartta,
              "aikaleima": kartta[a]["Aikaleima"] if a in kartta else None}
             for a in OSIOT]
    aikaleimat = [r["Aikaleima"] for r in tila_rivit]
    generoitu_aika = min(aikaleimat)

    generointi_sig = next((r["Laskentatiiviste"] for r in tila_rivit if r["Laskentatiiviste"]), None)
    tuoreus, tarkistettu = _tuoreus(generointi_sig, mallit.hae_raportti_tuoreus(tid))

    return {
        "generoitu": True,
        "osiot": osiot,
        "puuttuu": [o["avain"] for o in osiot if not o["on"]],
        "generoitu_aika": generoitu_aika,
        "viimeksi_muokattu": max(aikaleimat),
        "tuoreus": tuoreus,
        "tarkistettu": tarkistettu,
        "hitl_jalkeen": mallit.laske_hitl_korjaukset_jalkeen(tid, generoitu_aika),
        "arviokorjaukset_jalkeen": mallit.laske_hitl_vastaukset(tid, jalkeen=generoitu_aika),
    }


def paivita_tuoreus(tutkimus: dict) -> str:
    """Laskee lähdeaineiston tuoreussignatuurin (RASKAS: per-yliopisto-tilastot +
    kaikki vastaukset + kommentit etäkannasta) ja tallentaa sen aikaleimoineen.
    Ajetaan taustalla tai käyttäjän pyynnöstä — EI status-katselun kriittisellä
    polulla. Palauttaa lasketun signatuurin."""
    sig = raporttitiiviste(tutkimus)
    mallit.tallenna_raportti_tuoreus(tutkimus["TID"], sig)
    return sig


def _lue_jarjestelmakehote() -> str:
    return kehotteet.lue("raporttijarjestelma.txt")


def rakenna_viestit(tutkimus: dict, tilastot: list[dict], kysymykset: list[dict]) -> dict[str, str]:
    """Raportin osioiden LLM-viestit {osio: viesti} (myös ./kehoteraportti käyttää)."""
    return {
        "johdanto": _rakenna_johdanto_viesti(tutkimus, tilastot),
        "kurssit": _rakenna_kurssit_viesti(tutkimus, tilastot),
        "arvioinnit": _rakenna_arvioinnit_viesti(tutkimus, kysymykset, tilastot),
    }


def _rakenna_johdanto_viesti(tutkimus: dict, tilastot: list[dict]) -> str:
    yliopistojen_lkm = len([r for r in tilastot if r["KurssiYhteensa"] > 0])
    raportointikehote = tutkimus.get("Raportointikehote") or ""
    return f"""Kirjoita tutkimusraportin johdanto-osio seuraavien tietojen pohjalta.

Tutkimuksen nimi: {tutkimus['LuokittelunNimi']}
Raportointikehote (tutkimuksen taustaohje): {raportointikehote or '(ei annettu)'}

Yleistilastot:
- Tarkasteltuja yliopistoja: {yliopistojen_lkm}

Kurssien karsiutuminen (suppilo):
{suppilo_teksti(suppilo(tilastot))}

Tasorajaus: {tutkimus.get('Tasorajaus') or '(kaikki tasot)'}
Oppiainerajaus: {tutkimus.get('Oppiainerajaus') or '(kaikki oppiaineet)'}

Kirjoita johdanto, joka esittelee tutkimuksen aiheen, tavoitteen ja laajuuden.
Mainitse tarkasteltujen yliopistojen ja kurssien määrät."""


def _rakenna_kurssit_viesti(tutkimus: dict, tilastot: list[dict]) -> str:
    mittarit = hitl_mittarit(tilastot)
    raportointikehote = tutkimus.get("Raportointikehote") or ""
    return f"""Kirjoita tutkimusraportin kurssit-osio seuraavien tietojen pohjalta.

Tutkimuksen nimi: {tutkimus['LuokittelunNimi']}
Raportointikehote: {raportointikehote or '(ei annettu)'}

Valintakehote (ohje LLM:lle kurssin valinnassa):
{tutkimus['Luokittelukehote']}

Suodatusperusteet:
- Tasorajaus: {tutkimus.get('Tasorajaus') or 'kaikki tasot'}
- Oppiainerajaus: {tutkimus.get('Oppiainerajaus') or 'kaikki oppiaineet'}

Yliopistokohtaiset tilastot:
{tilasto_taulukko(tilastot)}

Kurssien karsiutuminen (suppilo):
{suppilo_teksti(suppilo(tilastot))}

Ihmistarkistuksen (HITL) laatumittarit:
{hitl_yhteenveto_teksti(mittarit)}

Kirjoita osio, joka esittelee kurssihaun suodatusperusteet, valintakehotteen tarkoituksen
sekä kuvaa yliopistokohtaiset tulokset ja suppilon: erottele meta-suodatuksen
(sääntöpohjainen taso-/oppiainerajaus) hylkäämät LLM:n seulomista kursseista. Raportoi eksplisiittisesti,
kuinka suuri osuus luokittelupäätöksistä jouduttiin muuttamaan käsin ja kuinka suuri
osuus korjauksista johtui riittämättömästä opinto-oppaasta (eli oppaan laadusta,
ei mallin virheestä)."""


def _rakenna_arvioinnit_viesti(tutkimus: dict, kysymykset: list[dict], tilastot: list[dict]) -> str:
    mukana_yht = sum(r["Mukana"] for r in tilastot)
    korjaukset_lkm = mallit.laske_hitl_vastaukset(tutkimus["TID"])
    kesken = mallit.laske_arvioimattomat(tutkimus["TID"])
    kysymysteksti = "\n".join(f"{i+1}. {k['Kysymys']}" for i, k in enumerate(kysymykset))
    raportointikehote = tutkimus.get("Raportointikehote") or ""
    return f"""Kirjoita tutkimusraportin arvioinnit-osio seuraavien tietojen pohjalta.

Tutkimuksen nimi: {tutkimus['LuokittelunNimi']}
Raportointikehote: {raportointikehote or '(ei annettu)'}

Arviointikehote (ohje LLM:lle kurssin arvioinnissa):
{tutkimus['Arviointikehote']}

Arviointikysymykset ({len(kysymykset)} kpl):
{kysymysteksti or '(ei kysymyksiä)'}

Arvioitavia kursseja (lopullinen mukana-lista HITL:n jälkeen): {mukana_yht}, joista arviointi kesken: {kesken}
Vastausjakaumat (tilastot) on laskettu vain näistä kursseista.
Ihmisten korjaamien vastausten määrä: {korjaukset_lkm}

Kirjoita osio, joka esittelee arviointimenetelmän, käytetyt kysymykset ja kuvaa
arvioinnin laajuuden sekä ihmisten tekemien korjausten merkityksen."""


def aja(tutkimus: dict, edistyminen_cb=None) -> int:
    """Generoi raporttiosiot LLM:llä ja tallentaa ne tietokantaan.

    Palauttaa generoitujen osioiden määrän. Idempotentti — korvaa olemassa olevat.
    """
    tid = tutkimus["TID"]
    jarjestelma = _lue_jarjestelmakehote()
    tilastot = mallit.hae_tilastot_yliopistoittain(tid)
    kysymykset = mallit.hae_kysymykset(tid)
    # Lähdeaineiston tiiviste generoinnin hetkellä → tallennetaan jokaiseen osioon
    # tuoreustarkistusta varten (CLIUI:n "Näytä tilanne" vertaa tähän).
    laskenta = raporttitiiviste(tutkimus, tilastot, kysymykset)

    viestit = rakenna_viestit(tutkimus, tilastot, kysymykset)

    generoitu = 0
    for i, avain in enumerate(OSIOT):
        if edistyminen_cb:
            edistyminen_cb(i, len(OSIOT), avain)
        teksti = kutsu.kysy(viestit[avain], jarjestelma)
        mallit.aseta_raportti_osio(tid, avain, teksti, laskentatiiviste=laskenta)
        generoitu += 1

    # Siemennä tuoreus: juuri generoitu raportti on määritelmällisesti ajan tasalla
    # (nykysignatuuri == generoinnin signatuuri) → status näyttää sen heti oikein
    # ilman että taustatarkistuksen tarvitsee vielä ehtiä ajaa.
    mallit.tallenna_raportti_tuoreus(tid, laskenta)

    if edistyminen_cb:
        edistyminen_cb(len(OSIOT), len(OSIOT), "valmis")
    return generoitu
