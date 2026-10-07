"""Raakana JSONina tallentuneiden arviointivastausten korjaus.

Malli palautti kysymyskohtaisen vastauksen joskus JSON-MERKKIJONONA sisäkkäisen
objektin sijaan, jolloin pura_vastaus putosi str()-haaraan: koko JSON päätyi
Vastaus-kenttään ja Luokka/Pisteet/Lista jäivät tyhjiksi. Koodikorjaus
(llmarviointi.pura_vastaus) estää uudet; tämä korjaa jo tallennetut.

Data on tallessa Vastaus-kentässä, joten korjaus on pelkkää uudelleenjäsennystä
— yhtään LLM-kutsua ei tarvita eikä mitään mene hukkaan. Jäsennys tehdään
samalla pura_vastaus-funktiolla kuin putkessa, jottei logiikkaa ole kahdessa
paikassa. Idempotentti: korjattu rivi ei enää ala '{'-merkillä.

korjaa_luokat kanonisoi samaan tapaan tallennetut luokat (kirjainkoko/välilyönnit,
arviointi.luokat) ja palauttaa tuntemattomat arvot korjattaviksi.
"""
from tietokanta import mallit
from arviointi.llmarviointi import pura_vastaus
from arviointi.luokat import kanoninen_luokka, sallitut_luokat

_ERA = 200  # korjattua riviä per tietokantakierros


def korjaa_raaka_json(tid: int, edistyminen_cb=None) -> tuple[int, int]:
    """Korjaa tutkimuksen raakana tallennetut vastaukset. Palauttaa (korjatut, ohitetut).

    Ohitetuksi jää rivi, jonka teksti ei jäsenny (katkennut JSON) tai josta ei
    irtoa perustelua — sellainen jätetään koskematta, ettei säilynyt teksti katoa.
    """
    rivit = mallit.hae_raakana_tallennetut_vastaukset(tid)
    kysymykset = {k["KysID"]: k for k in mallit.hae_kysymykset(tid)}
    korjatut = ohitetut = 0
    for alku in range(0, len(rivit), _ERA):
        osa = []
        for rivi in rivit[alku:alku + _ERA]:
            kysymys = kysymykset.get(rivi["KysID"], {})
            vastaus, pisteet, luokka, lista = pura_vastaus(kysymys, rivi["Vastaus"])
            # Jäsentymätön teksti palaa sellaisenaan → ei ole korjattavissa.
            if vastaus == rivi["Vastaus"]:
                ohitetut += 1
            else:
                osa.append((rivi["KysID"], rivi["KID"], vastaus, rivi.get("Malli") or "",
                            pisteet, luokka, lista, rivi.get("Kehotetiiviste")))
        if osa:
            mallit.aseta_vastaukset(tid, osa)
            korjatut += len(osa)
        if edistyminen_cb:
            edistyminen_cb(min(alku + _ERA, len(rivit)), len(rivit), korjatut, ohitetut)
    return korjatut, ohitetut


def korjaa_luokat(tid: int) -> tuple[int, list[dict]]:
    """Kanonisoi luokittelukysymysten Luokka-arvot (LLM- ja HITL-rivit). Palauttaa
    (korjatut, tuntemattomat): tuntematon arvo jätetään ennalleen (dataa ei hävitetä)
    ja palautetaan riveinä (VasID, KysID, KID, Luokka), jotta ihminen voi korjata sen
    (WebUI:n arviokorjaus). Idempotentti: kanoninen rivi ei enää osu hakuun."""
    kysymykset = {k["KysID"]: k for k in mallit.hae_kysymykset(tid)
                  if k.get("Luokittelu") == "luokittelu" and sallitut_luokat(k)}
    rivit = mallit.hae_epakanoniset_luokat(
        tid, {kysid: sallitut_luokat(k) for kysid, k in kysymykset.items()})
    korjattavat, tuntemattomat = [], []
    for rivi in rivit:
        uusi = kanoninen_luokka(kysymykset[rivi["KysID"]], rivi["Luokka"])
        if uusi == rivi["Luokka"]:
            tuntemattomat.append(rivi)
        else:
            korjattavat.append((uusi, rivi["VasID"]))
    if korjattavat:
        mallit.paivita_luokat(korjattavat)
    return len(korjattavat), tuntemattomat
