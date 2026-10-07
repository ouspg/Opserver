"""Vaihe b) lista-arvojen normalisoinnissa: LLM ehdottaa synonyymien yhdistämistä.

Arvot lähetetään kysymyksittäin mainintamäärineen (malli valitsee kanonisen muodon
järkevästi). Satojen arvojen joukko pilkotaan aakkosjärjestyksessä enintään ERAKOKO
arvon eriin (lähekkäiset kirjoitusasut osuvat samaan erään); katkennut tai
jäsentymätön vastaus (ks. muisti LLM-JSON-luotettavuus: virhe = katkennut vastaus)
puolittaa erän ja yrittää uudelleen. Kysymys merkitään käsitellyksi vain, jos sen
kaikki erät onnistuivat — epäonnistunut kysytään uudelleen seuraavalla kerralla.
"""
import json

from llm import kutsu, kehotteet
from tietokanta import mallit
from raportti.listanormalisointi import (
    Ehdotus, MAKSIMIPITUUS, arvojoukon_tiiviste, hylatyt, kelvolliset_maarat, ratkaise_ketjut,
)

KEHOTETIEDOSTO = "listasynonyymijarjestelma.txt"
ERAKOKO = 150        # arvoa per LLM-kutsu (rajaa vastauksen pituutta → ei katkea)
_MINIMIERA = 10      # tätä pienempää erää ei enää puoliteta


def lue_kehote() -> str:
    return kehotteet.lue(KEHOTETIEDOSTO)


def jasenna_vastaus(teksti: str) -> list[tuple[str, str]]:
    """LLM:n vastaus → [(lahde, kohde)]. Sietää koodiaidat, perässä olevan roskan ja
    ohjausmerkit; yksittäiset virheelliset alkiot ohitetaan. Jäsentymätön tai
    katkennut vastaus nostaa ValueErrorin (json.JSONDecodeError on sen aliluokka)."""
    alku = teksti.find("{")
    if alku == -1:
        raise ValueError(f"Ei JSON-objektia vastauksessa: {teksti[:200]!r}")
    data, _ = json.JSONDecoder(strict=False).raw_decode(teksti[alku:])
    ryhmat = data.get("yhdistykset") if isinstance(data, dict) else None
    if not isinstance(ryhmat, list):
        raise ValueError(f"Vastauksesta puuttuu yhdistykset-lista: {teksti[:200]!r}")
    parit = []
    for ryhma in ryhmat:
        if not isinstance(ryhma, dict):
            continue
        kohde = ryhma.get("kohde")
        lahteet = ryhma.get("lahteet")
        if isinstance(lahteet, str):
            lahteet = [lahteet]
        if not isinstance(kohde, str) or not kohde.strip() or not isinstance(lahteet, list):
            continue
        parit.extend((l, kohde) for l in lahteet if isinstance(l, str) and l.strip())
    return parit


def suodata_parit(parit: list[tuple[str, str]], maarat: dict[str, int],
                  pois: set[tuple[int, str, str]], kysid: int) -> dict[str, str]:
    """Kelvolliset ehdotukset {lahde: lopullinen kohde}: lähteen on oltava aineistossa
    (muuten kohde ei muuttaisi mitään), lahde ≠ kohde, ei aiemmin hylätty; saman
    lähteen ensimmäinen ehdotus voittaa ja ketjut (a→b, b→c) ratkaistaan."""
    kuvaus: dict[str, str] = {}
    for lahde, kohde in parit:
        if (lahde in maarat and lahde != kohde and lahde not in kuvaus
                and len(kohde) <= MAKSIMIPITUUS and (kysid, lahde, kohde) not in pois):
            kuvaus[lahde] = kohde
    return ratkaise_ketjut(kuvaus)


def _viesti(kysymys: str, maarat: dict[str, int], arvot: list[str]) -> str:
    rivit = json.dumps([[a, maarat[a]] for a in arvot], ensure_ascii=False)
    return (f"Kysymys: {kysymys}\n\n"
            f"Arvot ja mainintojen määrät ({len(arvot)} kpl, muodossa [arvo, määrä]):\n{rivit}")


def kysy_erissa(kysymys: str, maarat: dict[str, int], jarjestelma: str) -> tuple[list[tuple[str, str]], int]:
    """Kysyy LLM:ltä synonyymit erissä. Palauttaa (parit, epäonnistuneiden erien määrä).
    Muut kuin jäsennysvirheet (verkko, puuttuva konfiguraatio) nousevat kutsujalle."""
    arvot = sorted(maarat, key=lambda a: (a.lower(), a))
    jono = [arvot[i:i + ERAKOKO] for i in range(0, len(arvot), ERAKOKO)]
    parit, virheet = [], 0
    while jono:
        era = jono.pop(0)
        try:
            vastaus = kutsu.kysy(_viesti(kysymys, maarat, era), jarjestelma, json_muoto=True)
            parit.extend(jasenna_vastaus(vastaus))
        except ValueError:
            if len(era) > _MINIMIERA:
                puoli = len(era) // 2
                jono[:0] = [era[:puoli], era[puoli:]]
            else:
                virheet += 1
    return parit, virheet


def synonyymiehdotukset(tid: int, kysymykset: list[dict], edistyminen=None
                        ) -> tuple[list[Ehdotus], dict[int, set[str]], list[str]]:
    """Vaihe b) koko tutkimukselle. Palauttaa (ehdotukset, lähetetyt arvojoukot
    onnistuneille kysymyksille, virheilmoitukset). Kysymys ohitetaan, jos sen nykyinen
    arvojoukko on jo kerran käsitelty samalla kehotteella (ListaLlmKasitelty)."""
    kehote = lue_kehote()
    maarat_kaikki = mallit.hae_lista_arvomaarat(tid, [k["KysID"] for k in kysymykset])
    pois = hylatyt(mallit.hae_lista_paatokset(tid))
    kasitellyt = mallit.hae_llm_kasitellyt(tid)
    ehdotukset, lahetetyt, virheet = [], {}, []
    for i, k in enumerate(kysymykset):
        kysid = k["KysID"]
        maarat = kelvolliset_maarat(maarat_kaikki.get(kysid, {}))
        if len(maarat) < 2 or kasitellyt.get(kysid) == arvojoukon_tiiviste(maarat, kehote):
            continue
        if edistyminen:
            edistyminen(i, len(kysymykset), k["Kysymys"])
        parit, epaonnistuneet = kysy_erissa(k["Kysymys"], maarat, kehote)
        if epaonnistuneet:
            virheet.append(f"Kysymys {k['nro']}: {epaonnistuneet} erää jäi jäsentymättä")
        else:
            lahetetyt[kysid] = set(maarat)
        for lahde, kohde in sorted(suodata_parit(parit, maarat, pois, kysid).items(),
                                   key=lambda p: (p[1].lower(), p[0])):
            ehdotukset.append(Ehdotus(kysid, k["nro"], k["Kysymys"], lahde, kohde))
    return ehdotukset, lahetetyt, virheet
