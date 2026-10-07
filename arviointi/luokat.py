"""Luokittelukysymysten luokkien kanoninen muoto (LuokitteluMaarittely.luokat[].nimi).

Malli palauttaa luokan joskus eri kirjainkoolla tai reunavälilyönnein ('ei lainkaan '),
jolloin sama luokka näkyi tilastoissa kahtena. Jaettu putken (pura_vastaus), vanhojen
rivien korjauksen (korjaus.korjaa_luokat) ja raportin tilastojen kesken."""


def sallitut_luokat(kysymys: dict) -> list[str]:
    """Kysymyksen sallitut luokkanimet määrittelyn järjestyksessä."""
    maarittely = kysymys.get("LuokitteluMaarittely") or {}
    return [l["nimi"] for l in maarittely.get("luokat", []) if isinstance(l, dict) and l.get("nimi")]


def kanoninen_luokka(kysymys: dict, arvo):
    """Sallittu luokkanimi, joka vastaa arvoa kirjainkoosta ja reunavälilyönneistä
    riippumatta. Tuntematon arvo palautetaan sellaisenaan (dataa ei hävitetä)."""
    if not isinstance(arvo, str):
        return arvo
    avain = arvo.strip().casefold()
    return next((nimi for nimi in sallitut_luokat(kysymys) if nimi.strip().casefold() == avain), arvo)
