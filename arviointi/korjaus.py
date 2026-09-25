"""Raakana JSONina tallentuneiden arviointivastausten korjaus.

Malli palautti kysymyskohtaisen vastauksen joskus JSON-MERKKIJONONA sisäkkäisen
objektin sijaan, jolloin pura_vastaus putosi str()-haaraan: koko JSON päätyi
Vastaus-kenttään ja Luokka/Pisteet/Lista jäivät tyhjiksi. Koodikorjaus
(llmarviointi.pura_vastaus) estää uudet; tämä korjaa jo tallennetut.

Data on tallessa Vastaus-kentässä, joten korjaus on pelkkää uudelleenjäsennystä
— yhtään LLM-kutsua ei tarvita eikä mitään mene hukkaan. Jäsennys tehdään
samalla pura_vastaus-funktiolla kuin putkessa, jottei logiikkaa ole kahdessa
paikassa. Idempotentti: korjattu rivi ei enää ala '{'-merkillä.
"""
from tietokanta import mallit
from arviointi.llmarviointi import pura_vastaus


def korjaa_raaka_json(tid: int, edistyminen_cb=None) -> tuple[int, int]:
    """Korjaa tutkimuksen raakana tallennetut vastaukset. Palauttaa (korjatut, ohitetut).

    Ohitetuksi jää rivi, jonka teksti ei jäsenny (katkennut JSON) tai josta ei
    irtoa perustelua — sellainen jätetään koskematta, ettei säilynyt teksti katoa.
    """
    rivit = mallit.hae_raakana_tallennetut_vastaukset(tid)
    kysymykset = {k["KysID"]: k for k in mallit.hae_kysymykset(tid)}
    korjatut = ohitetut = 0
    for n, rivi in enumerate(rivit, 1):
        kysymys = kysymykset.get(rivi["KysID"], {})
        vastaus, pisteet, luokka, lista = pura_vastaus(kysymys, rivi["Vastaus"])
        # Jäsentymätön teksti palaa sellaisenaan → ei ole korjattavissa.
        if vastaus == rivi["Vastaus"]:
            ohitetut += 1
        else:
            mallit.aseta_vastaus(rivi["KysID"], rivi["KID"], vastaus,
                                 rivi.get("Malli") or "", pisteet=pisteet, luokka=luokka,
                                 lista=lista, tiiviste=rivi.get("Kehotetiiviste"))
            korjatut += 1
        if edistyminen_cb:
            edistyminen_cb(n, len(rivit), korjatut, ohitetut)
    return korjatut, ohitetut
