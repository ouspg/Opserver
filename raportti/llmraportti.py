"""LLM-raporttigenerointi: koostaa raporttiosiot tietokannasta ja täydentää LLM:llä."""
import json
import os
from tietokanta import mallit
from llm import kutsu, tiiviste

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
    kommentit = mallit.hae_arviokommentit_kaikki(tid)

    tilasto_osa = json.dumps(sorted(
        [r["KKID"], r["KurssiYhteensa"], r["LLMKasitelty"], r["Mukana"], r["Hylatty"],
         r.get("HitlLkm", 0), r.get("HitlKursseja", 0), r.get("RiittamatonOpas", 0),
         r.get("LlmVirhe", 0), r.get("TuntematonSyy", 0)]
        for r in tilastot), ensure_ascii=False)
    kysymys_osa = json.dumps(sorted(
        [k["KysID"], k.get("Kysymys") or "", k.get("Luokittelu") or "vapaa_teksti",
         json.dumps(k.get("LuokitteluMaarittely"), sort_keys=True, ensure_ascii=False)]
        for k in kysymykset), ensure_ascii=False)
    vastaus_osa = json.dumps(sorted(
        [kid, kysid, v.get("tiiviste") or "", bool(v.get("vastattu"))]
        for (kid, kysid), v in vastaus_tila.items()), ensure_ascii=False)
    kommentti_osa = json.dumps(sorted(
        [c["KID"], c["KysID"], c.get("Kommentti") or ""] for c in kommentit), ensure_ascii=False)
    kehote_osa = json.dumps([
        tutkimus.get("Luokittelukehote") or "", tutkimus.get("Arviointikehote") or "",
        tutkimus.get("Raportointikehote") or "", tutkimus.get("Tasorajaus") or "",
        tutkimus.get("Oppiainerajaus") or "",
    ], ensure_ascii=False)
    return tiiviste.laske(tilasto_osa, kysymys_osa, vastaus_osa, kommentti_osa, kehote_osa)


def koosta_tilanne(tutkimus: dict) -> dict:
    """Kokoaa raportin tuoreustiedot status-näkymiä varten (CLIUI + WebUI).
    Curses- ja HTTP-riippumaton — palauttaa raakadatan, kumpikin UI muotoilee.

    Palauttaa {"generoitu": False} jos raporttia ei ole; muuten osioiden tila +
    aikaleimat, tuoreus (tiivistevertailu: ajan_tasalla / vanhentunut / tuntematon)
    ja generoinnin jälkeen tehtyjen HITL-korjausten ja kommenttien määrän.
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

    tallennettu = next((r["Laskentatiiviste"] for r in tila_rivit if r["Laskentatiiviste"]), None)
    if tallennettu is None:
        tuoreus = "tuntematon"
    else:
        tuoreus = "ajan_tasalla" if raporttitiiviste(tutkimus) == tallennettu else "vanhentunut"

    return {
        "generoitu": True,
        "osiot": osiot,
        "puuttuu": [o["avain"] for o in osiot if not o["on"]],
        "generoitu_aika": generoitu_aika,
        "viimeksi_muokattu": max(aikaleimat),
        "tuoreus": tuoreus,
        "hitl_jalkeen": mallit.laske_hitl_korjaukset_jalkeen(tid, generoitu_aika),
        "kommentit_jalkeen": mallit.laske_arviokommentit_jalkeen(tid, generoitu_aika),
    }


def _lue_jarjestelmakehote() -> str:
    polku = os.path.join(os.path.dirname(__file__), "..", "kehotteet", "raporttijarjestelma.txt")
    with open(polku, encoding="utf-8") as f:
        return f.read().strip()


def _tilasto_taulukko(rivit: list[dict]) -> str:
    otsikko = f"{'Yliopisto':<40} {'Kursseja':>10} {'LLM käsitelty':>15} {'Mukana':>8} {'Hylätty':>9} {'HITL':>6}"
    viiva = "-" * len(otsikko)
    rivit_txt = [otsikko, viiva]
    for r in rivit:
        rivit_txt.append(
            f"{r['KouluNimi']:<40} {r['KurssiYhteensa']:>10} {r['LLMKasitelty']:>15}"
            f" {r['Mukana']:>8} {r['Hylatty']:>9} {r['HitlLkm']:>6}"
        )
    return "\n".join(rivit_txt)


def hitl_mittarit(tilastot: list[dict]) -> dict:
    """Kaksi raporttimittaria HITL-korjauksista (CLAUDE.md, vaihe 4):

    1. Käsin muutettujen osuus = muutetut kurssit / LLM-luokitellut kurssit.
    2. Juurisyyjakauma = korjauksista montako % johtui riittämättömästä
       oppaasta (data-ongelma) vs. LLM:n virheestä (kehote-ongelma).
    """
    llm_kasitelty = sum(r["LLMKasitelty"] for r in tilastot)
    muutettu = sum(r["HitlKursseja"] for r in tilastot)
    opas = sum(r["RiittamatonOpas"] for r in tilastot)
    llm_virhe = sum(r["LlmVirhe"] for r in tilastot)
    tuntematon = sum(r["TuntematonSyy"] for r in tilastot)
    osuus = lambda osa, koko: 100 * osa / koko if koko else 0.0
    return {
        "llm_kasitelty": llm_kasitelty, "muutettu": muutettu,
        "muutettu_pros": osuus(muutettu, llm_kasitelty),
        "opas": opas, "opas_pros": osuus(opas, muutettu),
        "llm_virhe": llm_virhe, "llm_virhe_pros": osuus(llm_virhe, muutettu),
        "tuntematon": tuntematon, "tuntematon_pros": osuus(tuntematon, muutettu),
    }


def _hitl_yhteenveto_teksti(m: dict) -> str:
    """Muotoilee HITL-mittarit raporttikehotteeseen sopivaksi tekstilohkoksi."""
    opas_nimi = mallit.JUURISYYT["riittamaton_opas"]
    llm_nimi = mallit.JUURISYYT["llm_virhe"]
    return (
        f"Ihmisen käsin muuttamia luokittelupäätöksiä: {m['muutettu']} / "
        f"{m['llm_kasitelty']} LLM-luokiteltua kurssia ({m['muutettu_pros']:.1f} %).\n"
        f"Korjausten juurisyyt (osuus käsin muutetuista kursseista):\n"
        f"- {opas_nimi} (tieto ei ollut oppaassa, data-ongelma): "
        f"{m['opas']} kpl ({m['opas_pros']:.1f} %)\n"
        f"- {llm_nimi} (kehotetta parannettava): "
        f"{m['llm_virhe']} kpl ({m['llm_virhe_pros']:.1f} %)\n"
        f"- Juurisyy merkitsemättä: {m['tuntematon']} kpl ({m['tuntematon_pros']:.1f} %)"
    )


def _rakenna_johdanto_viesti(tutkimus: dict, tilastot: list[dict]) -> str:
    mukana_yht = sum(r["Mukana"] for r in tilastot)
    kurssit_yht = sum(r["KurssiYhteensa"] for r in tilastot)
    yliopistojen_lkm = len([r for r in tilastot if r["KurssiYhteensa"] > 0])
    raportointikehote = tutkimus.get("Raportointikehote") or ""
    return f"""Kirjoita tutkimusraportin johdanto-osio seuraavien tietojen pohjalta.

Tutkimuksen nimi: {tutkimus['LuokittelunNimi']}
Raportointikehote (tutkimuksen taustaohje): {raportointikehote or '(ei annettu)'}

Yleistilastot:
- Tarkasteltuja yliopistoja: {yliopistojen_lkm}
- Kursseja tietokannassa yhteensä: {kurssit_yht}
- LLM:n mukaan ottamia kursseja: {mukana_yht}

Tasorajaus: {tutkimus.get('Tasorajaus') or '(kaikki tasot)'}
Oppiainerajaus: {tutkimus.get('Oppiainerajaus') or '(kaikki oppiaineet)'}

Kirjoita johdanto, joka esittelee tutkimuksen aiheen, tavoitteen ja laajuuden.
Mainitse tarkasteltujen yliopistojen ja kurssien määrät."""


def _rakenna_kurssit_viesti(tutkimus: dict, tilastot: list[dict]) -> str:
    mukana_yht = sum(r["Mukana"] for r in tilastot)
    kurssit_yht = sum(r["KurssiYhteensa"] for r in tilastot)
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
{_tilasto_taulukko(tilastot)}

Yhteenveto:
- Kursseja tietokannassa yhteensä: {kurssit_yht}
- LLM:n valitsemia kursseja: {mukana_yht}

Ihmistarkistuksen (HITL) laatumittarit:
{_hitl_yhteenveto_teksti(mittarit)}

Kirjoita osio, joka esittelee kurssihaun suodatusperusteet, valintakehotteen tarkoituksen
sekä kuvaa yliopistokohtaiset tulokset ja yhteenvedon. Raportoi eksplisiittisesti,
kuinka suuri osuus luokittelupäätöksistä jouduttiin muuttamaan käsin ja kuinka suuri
osuus korjauksista johtui riittämättömästä opinto-oppaasta (eli oppaan laadusta,
ei mallin virheestä)."""


def _rakenna_arvioinnit_viesti(tutkimus: dict, kysymykset: list[dict], tilastot: list[dict]) -> str:
    mukana_yht = sum(r["Mukana"] for r in tilastot)
    kommentit_lkm = len(mallit.hae_arviokommentit_kaikki(tutkimus["TID"]))
    kysymysteksti = "\n".join(f"{i+1}. {k['Kysymys']}" for i, k in enumerate(kysymykset))
    raportointikehote = tutkimus.get("Raportointikehote") or ""
    return f"""Kirjoita tutkimusraportin arvioinnit-osio seuraavien tietojen pohjalta.

Tutkimuksen nimi: {tutkimus['LuokittelunNimi']}
Raportointikehote: {raportointikehote or '(ei annettu)'}

Arviointikehote (ohje LLM:lle kurssin arvioinnissa):
{tutkimus['Arviointikehote']}

Arviointikysymykset ({len(kysymykset)} kpl):
{kysymysteksti or '(ei kysymyksiä)'}

Arvioitujen kurssien määrä: {mukana_yht}
Ihmisten tekemien kommenttien määrä: {kommentit_lkm}

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

    viestirakentajat = {
        "johdanto": lambda: _rakenna_johdanto_viesti(tutkimus, tilastot),
        "kurssit": lambda: _rakenna_kurssit_viesti(tutkimus, tilastot),
        "arvioinnit": lambda: _rakenna_arvioinnit_viesti(tutkimus, kysymykset, tilastot),
    }

    generoitu = 0
    for i, avain in enumerate(OSIOT):
        if edistyminen_cb:
            edistyminen_cb(i, len(OSIOT), avain)
        viesti = viestirakentajat[avain]()
        teksti = kutsu.kysy(viesti, jarjestelma)
        mallit.aseta_raportti_osio(tid, avain, teksti, laskentatiiviste=laskenta)
        generoitu += 1

    if edistyminen_cb:
        edistyminen_cb(len(OSIOT), len(OSIOT), "valmis")
    return generoitu
