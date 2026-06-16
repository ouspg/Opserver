"""Tutkimuksen tarkentavien kysymysten hallinta."""
from tietokanta import mallit
from cliui.apurit import piirra_otsikko, nayta_viesti, lue_teksti, valitse_listasta

_KATKAISU = 50
_TYYPIT = ["vapaa_teksti", "luokittelu", "asteikko", "lista"]
_TYYPPI_LYHENNE = {"vapaa_teksti": "TXT", "luokittelu": "LUO", "asteikko": "AST", "lista": "LIS"}


def _lyhenna(teksti: str) -> str:
    return teksti[:_KATKAISU] + "…" if len(teksti) > _KATKAISU else teksti


def nayta(stdscr, tutkimus: dict) -> None:
    """Hallinnoi yhden tutkimuksen tarkentavia kysymyksiä."""
    otsikko_pohja = f"Kysymykset — {tutkimus['LuokittelunNimi']}"
    while True:
        kysymykset = mallit.hae_kysymykset(tutkimus["TID"])
        vaihtoehdot = ["[+] Lisää uusi kysymys"] + [
            f"{i}. [{_TYYPPI_LYHENNE.get(k.get('Luokittelu','vapaa_teksti'),'TXT')}] {_lyhenna(k['Kysymys'])}"
            for i, k in enumerate(kysymykset, 1)
        ]
        valinta = valitse_listasta(stdscr, otsikko_pohja, vaihtoehdot)
        if valinta is None:
            return
        if valinta == 0:
            _lisaa(stdscr, tutkimus["TID"])
        else:
            _muokkaa_tai_poista(stdscr, kysymykset[valinta - 1])


def _lisaa(stdscr, tid: int) -> None:
    piirra_otsikko(stdscr, "Lisää kysymys")
    teksti = lue_teksti(stdscr, "Kysymys", 3)
    if not teksti:
        nayta_viesti(stdscr, "Peruutettu (kysymys ei voi olla tyhjä).")
        return
    tyyppi = _valitse_tyyppi(stdscr)
    if tyyppi is None:
        nayta_viesti(stdscr, "Peruutettu.")
        return
    maarittely = None
    if tyyppi != "vapaa_teksti":
        maarittely = _muokkaa_maarittely(stdscr, tyyppi, None)
        if maarittely is None:
            nayta_viesti(stdscr, "Peruutettu.")
            return
    mallit.lisaa_kysymys(tid, teksti, tyyppi, maarittely)
    nayta_viesti(stdscr, "Kysymys lisätty.")


def _muokkaa_tai_poista(stdscr, kysymys: dict) -> None:
    valinta = valitse_listasta(
        stdscr,
        _lyhenna(kysymys["Kysymys"]),
        ["Muokkaa teksti", "Muokkaa tyyppi ja määritelmä", "Poista"],
    )
    if valinta is None:
        return
    if valinta == 0:
        _muokkaa_teksti(stdscr, kysymys)
    elif valinta == 1:
        _muokkaa_tyyppi(stdscr, kysymys)
    else:
        _poista(stdscr, kysymys)


def _varoita_ja_vahvista(stdscr, kysid: int, toiminto: str) -> bool:
    """Palauttaa True jos käyttäjä hyväksyy olemassa olevien arvioiden poiston."""
    lkm = mallit.hae_vastausten_lkm(kysid)
    if lkm == 0:
        return True
    piirra_otsikko(stdscr, "VAROITUS")
    stdscr.addstr(3, 0, f"Tällä kysymyksellä on {lkm} olemassa olevaa arviota.")
    stdscr.addstr(4, 0, f"{toiminto} poistaa ne kaikki.")
    vahvistus = lue_teksti(stdscr, "Jatketaanko? (kyllä/ei)", 6)
    return vahvistus.strip().lower() in ("kyllä", "k", "kylla")


def _muokkaa_teksti(stdscr, kysymys: dict) -> None:
    if not _varoita_ja_vahvista(stdscr, kysymys["KysID"], "Kysymystekstin muuttaminen"):
        nayta_viesti(stdscr, "Peruutettu.")
        return
    piirra_otsikko(stdscr, "Muokkaa kysymysteksti")
    teksti = lue_teksti(stdscr, "Kysymys", 3, kysymys["Kysymys"])
    if not teksti:
        nayta_viesti(stdscr, "Peruutettu (kysymys ei voi olla tyhjä).")
        return
    mallit.poista_vastaukset_kysymykselta(kysymys["KysID"])
    mallit.paivita_kysymys(
        kysymys["KysID"], teksti,
        kysymys.get("Luokittelu", "vapaa_teksti"),
        kysymys.get("LuokitteluMaarittely"),
    )
    nayta_viesti(stdscr, "Päivitetty.")


def _muokkaa_tyyppi(stdscr, kysymys: dict) -> None:
    if not _varoita_ja_vahvista(stdscr, kysymys["KysID"], "Tyypin muuttaminen"):
        nayta_viesti(stdscr, "Peruutettu.")
        return
    tyyppi = _valitse_tyyppi(stdscr)
    if tyyppi is None:
        nayta_viesti(stdscr, "Peruutettu.")
        return
    maarittely = None
    if tyyppi != "vapaa_teksti":
        nykyinen = kysymys.get("LuokitteluMaarittely") if kysymys.get("Luokittelu") == tyyppi else None
        maarittely = _muokkaa_maarittely(stdscr, tyyppi, nykyinen)
        if maarittely is None:
            nayta_viesti(stdscr, "Peruutettu.")
            return
    mallit.poista_vastaukset_kysymykselta(kysymys["KysID"])
    mallit.paivita_kysymys(kysymys["KysID"], kysymys["Kysymys"], tyyppi, maarittely)
    nayta_viesti(stdscr, "Tyyppi päivitetty.")


def _valitse_tyyppi(stdscr) -> str | None:
    vaihtoehdot = [
        "vapaa_teksti — LLM vastaa vapaalla tekstillä",
        "luokittelu — LLM valitsee luokan + antaa perustelun",
        "asteikko — LLM antaa pistemäärän + perustelun",
        "lista — LLM luettelee erilliset kohdat + antaa perustelun",
    ]
    valinta = valitse_listasta(stdscr, "Valitse kysymystyyppi", vaihtoehdot)
    if valinta is None:
        return None
    return _TYYPIT[valinta]


def _muokkaa_maarittely(stdscr, tyyppi: str, nykyinen: dict | None) -> dict | None:
    if tyyppi == "luokittelu":
        return _muokkaa_luokittelu(stdscr, nykyinen)
    if tyyppi == "asteikko":
        return _muokkaa_asteikko(stdscr, nykyinen)
    if tyyppi == "lista":
        return _muokkaa_lista(stdscr, nykyinen)
    return None


def _muokkaa_lista(stdscr, nykyinen: dict | None) -> dict | None:
    """Valinnainen yläraja luettelon kohtien määrälle (tyhjä = ei rajaa)."""
    piirra_otsikko(stdscr, "Lista — kohtien yläraja")
    nykyinen_max = str(nykyinen.get("max_kohdat")) if nykyinen and nykyinen.get("max_kohdat") else ""
    max_str = lue_teksti(stdscr, "Kohtien yläraja (kokonaisluku, tyhjä = ei rajaa)", 3, nykyinen_max)
    if not max_str.strip():
        return {}
    try:
        return {"max_kohdat": int(max_str)}
    except ValueError:
        return {}


def _muokkaa_luokittelu(stdscr, nykyinen: dict | None) -> dict | None:
    """Wizard: kerää luokat pilkkueroteltuna, sitten kuvaus jokaiselle."""
    piirra_otsikko(stdscr, "Luokittelu — luokkien nimet")
    nykyiset_nimet = ""
    if nykyinen:
        nykyiset_nimet = ", ".join(l["nimi"] for l in nykyinen.get("luokat", []))
    nimet_str = lue_teksti(stdscr, "Luokkien nimet (pilkuilla)", 3, nykyiset_nimet)
    if not nimet_str.strip():
        return None
    nimet = [n.strip() for n in nimet_str.split(",") if n.strip()]
    if not nimet:
        return None

    nykyiset_kuvaukset = {}
    if nykyinen:
        for l in nykyinen.get("luokat", []):
            nykyiset_kuvaukset[l["nimi"]] = l["kuvaus"]

    luokat = []
    for nimi in nimet:
        piirra_otsikko(stdscr, f"Luokittelu — kuvaus luokalle '{nimi}'")
        kuvaus = lue_teksti(stdscr, "Kuvaus", 3, nykyiset_kuvaukset.get(nimi, ""))
        luokat.append({"nimi": nimi, "kuvaus": kuvaus})

    return {"luokat": luokat}


def _muokkaa_asteikko(stdscr, nykyinen: dict | None) -> dict | None:
    """Wizard: minimi, maksimi, pakollisten päätepisteiden kuvaukset, valinnaiset välipisteet."""
    piirra_otsikko(stdscr, "Asteikko — alueen määritys")

    nykyinen_min = str(nykyinen.get("minimi", 1)) if nykyinen else "1"
    nykyinen_max = str(nykyinen.get("maksimi", 5)) if nykyinen else "5"

    min_str = lue_teksti(stdscr, "Minimi (kokonaisluku)", 3, nykyinen_min)
    max_str = lue_teksti(stdscr, "Maksimi (kokonaisluku)", 4, nykyinen_max)
    try:
        minimi = int(min_str)
        maksimi = int(max_str)
    except ValueError:
        return None
    if minimi >= maksimi:
        nayta_viesti(stdscr, "Minimi täytyy olla pienempi kuin maksimi.")
        return None

    nykyiset_kuvaukset = {}
    if nykyinen:
        for p in nykyinen.get("pisteet", []):
            nykyiset_kuvaukset[p["arvo"]] = p["kuvaus"]

    piirra_otsikko(stdscr, f"Asteikko — kuvaukset ({minimi}–{maksimi})")
    min_kuvaus = lue_teksti(stdscr, f"Pisteen {minimi} kuvaus", 3, nykyiset_kuvaukset.get(minimi, ""))
    max_kuvaus = lue_teksti(stdscr, f"Pisteen {maksimi} kuvaus", 4, nykyiset_kuvaukset.get(maksimi, ""))

    pisteet = [{"arvo": minimi, "kuvaus": min_kuvaus}, {"arvo": maksimi, "kuvaus": max_kuvaus}]

    vali_str = lue_teksti(stdscr, "Lisää välipisteitä? (pilkuilla, esim. 2,3 tai tyhjä=ei)", 5, "")
    if vali_str.strip():
        for arvo_str in vali_str.split(","):
            try:
                arvo = int(arvo_str.strip())
            except ValueError:
                continue
            if minimi < arvo < maksimi:
                piirra_otsikko(stdscr, f"Asteikko — kuvaus välipiste {arvo}")
                kuvaus = lue_teksti(stdscr, f"Pisteen {arvo} kuvaus", 3, nykyiset_kuvaukset.get(arvo, ""))
                pisteet.append({"arvo": arvo, "kuvaus": kuvaus})

    pisteet.sort(key=lambda p: p["arvo"])
    return {"minimi": minimi, "maksimi": maksimi, "pisteet": pisteet}


def _poista(stdscr, kysymys: dict) -> None:
    piirra_otsikko(stdscr, "Poista kysymys")
    stdscr.addstr(3, 0, _lyhenna(kysymys["Kysymys"]))
    vahvistus = lue_teksti(stdscr, "Poistetaanko? (kyllä/ei)", 5)
    if vahvistus.lower() in ("kyllä", "k", "kylla"):
        mallit.poista_kysymys(kysymys["KysID"])
        nayta_viesti(stdscr, "Poistettu.")
    else:
        nayta_viesti(stdscr, "Peruutettu.")
