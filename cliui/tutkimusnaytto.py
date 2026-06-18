"""Tutkimusten hallintanäkymä: listaa, lisää, muokkaa ja poista."""
import os
import re

from tietokanta import mallit
from cliui import kysymysnaytto
from cliui.apurit import piirra_otsikko, nayta_viesti, lue_teksti, valitse_listasta, valitse_monivalinta

_SLUG_KAAVA = re.compile(r'^[a-z0-9][a-z0-9_-]*$')
_LUKUVUOSI_KAAVA = re.compile(r'^\d{4}-\d{4}$')


def _webui_osoite() -> str:
    """WebUI:n perusosoite ilman loppukauttaviivaa (konfiguroitavissa .env:ssä)."""
    return os.getenv("WEBUI_OSOITE", "http://localhost:12121").rstrip("/")


def _validoi_lukuvuosi(lukuvuosi: str) -> bool:
    return bool(_LUKUVUOSI_KAAVA.match(lukuvuosi))


def _valitse_korkeakoulut(stdscr, oletus_kkid: list[int] | None = None) -> list[int] | None:
    """Monivalinta korkeakouluista. Palauttaa valitut KKID:t tai None jos peruutettu."""
    koulut = mallit.hae_korkeakoulut()
    if not koulut:
        return None
    nimet = [k["KouluNimi"] for k in koulut]
    nimi_kkid = {k["KouluNimi"]: k["KKID"] for k in koulut}
    oletus_joukko = set(oletus_kkid or [])
    valitut_nimet = [n for n in nimet if nimi_kkid[n] in oletus_joukko]
    tulos = valitse_monivalinta(stdscr, "Valitse mukaan otettavat korkeakoulut", nimet, valitut_nimet)
    if tulos is None:
        return None
    return [nimi_kkid[n] for n in tulos]


def _valitse_tasot(stdscr, oletus: str = "") -> str:
    tasot = mallit.hae_tasot()
    if not tasot:
        return oletus
    valitut = [t for t in oletus.split(",") if t.strip() in tasot] if oletus else []
    tulos = valitse_monivalinta(stdscr, "Valitse sallitut tasot (tyhjä = kaikki)", tasot, valitut)
    if tulos is None:
        return oletus
    return ",".join(tulos)


def _valitse_oppiaineet(stdscr, kkid_lista: list[int], oletus: str = "") -> str:
    """Monivalinta valittujen korkeakoulujen oppiaineista (aakkosjärjestyksessä).

    Palauttaa pilkulla erotellun rajauksen (tyhjä = kaikki). Jos korkeakouluissa
    ei ole oppiaineita, palautetaan oletus eikä näytetä listaa.
    """
    oppiaineet = mallit.hae_oppiaineet(kkid_lista)
    if not oppiaineet:
        nayta_viesti(stdscr, "Valituissa korkeakouluissa ei oppiaineita — rajaus jätetään tyhjäksi.")
        return ""
    valitut = [o.strip() for o in oletus.split(",") if o.strip() in oppiaineet] if oletus else []
    tulos = valitse_monivalinta(stdscr, "Valitse oppiaineet (tyhjä = kaikki)", oppiaineet, valitut)
    if tulos is None:
        return oletus
    return ",".join(tulos)


def _validoi_slug(slug: str) -> bool:
    return bool(_SLUG_KAAVA.match(slug))


def nayta(stdscr) -> None:
    while True:
        valinta = valitse_listasta(
            stdscr,
            "Tutkimusten hallinta",
            ["Lisää tutkimus", "Monista tutkimus", "Muokkaa tutkimusta", "Poista tutkimus",
             "Listaa tutkimukset", "Hallinnoi kysymyksiä"],
        )
        if valinta is None:
            return
        if valinta == 0:
            _lisaa(stdscr)
        elif valinta == 1:
            _monista(stdscr)
        elif valinta == 2:
            _muokkaa(stdscr)
        elif valinta == 3:
            _poista(stdscr)
        elif valinta == 4:
            _listaa(stdscr)
        elif valinta == 5:
            _hallinnoi_kysymyksia(stdscr)


def _valitse_tutkimus(stdscr, otsikko: str) -> dict | None:
    tutkimukset = mallit.hae_tutkimukset()
    if not tutkimukset:
        piirra_otsikko(stdscr, otsikko)
        nayta_viesti(stdscr, "Ei tutkimuksia tietokannassa.")
        return None
    rivit = [f"{t['LuokittelunNimi']} ({t['Slug']})" for t in tutkimukset]
    indeksi = valitse_listasta(stdscr, otsikko, rivit)
    return tutkimukset[indeksi] if indeksi is not None else None


def _lisaa(stdscr) -> None:
    piirra_otsikko(stdscr, "Lisää tutkimus")
    nimi = lue_teksti(stdscr, "Tutkimuksen nimi", 3)
    if not nimi:
        nayta_viesti(stdscr, "Peruutettu (nimi pakollinen).")
        return
    slug = lue_teksti(stdscr, "Slug (a-z, 0-9, - ja _)", 4)
    if not slug or not _validoi_slug(slug):
        nayta_viesti(stdscr, "Peruutettu (slug pakollinen, vain: a-z 0-9 - _).")
        return
    lukuvuosi = lue_teksti(stdscr, "Lukuvuosi (esim. 2024-2025)", 5)
    if not _validoi_lukuvuosi(lukuvuosi):
        nayta_viesti(stdscr, "Peruutettu (lukuvuosi pakollinen, muoto YYYY-YYYY).")
        return
    verkkosivu = lue_teksti(stdscr, "Verkkosivu (URL, tyhjä = ei)", 6)
    luokittelukehote = lue_teksti(stdscr, "Valintakehote", 7)
    if not luokittelukehote:
        nayta_viesti(stdscr, "Peruutettu (valintakehote pakollinen).")
        return
    arviointikehote = lue_teksti(stdscr, "Arviointikehote", 8)
    if not arviointikehote:
        nayta_viesti(stdscr, "Peruutettu (arviointikehote pakollinen).")
        return
    raportointikehote = lue_teksti(stdscr, "Raportointikehote (tyhjä = ei)", 9)
    tasorajaus = _valitse_tasot(stdscr)
    korkeakoulut = _valitse_korkeakoulut(stdscr)
    if not korkeakoulut:
        nayta_viesti(stdscr, "Peruutettu (valitse vähintään yksi korkeakoulu).")
        return
    oppiainerajaus = _valitse_oppiaineet(stdscr, korkeakoulut)
    tid = mallit.lisaa_tutkimus(nimi, slug, lukuvuosi, luokittelukehote, tasorajaus, oppiainerajaus, arviointikehote, raportointikehote, verkkosivu=verkkosivu)
    mallit.aseta_tutkimuksen_korkeakoulut(tid, korkeakoulut)
    piirra_otsikko(stdscr, "Lisää tutkimus")
    nayta_viesti(stdscr, f"Lisätty: {nimi} ({slug})")


def _monista(stdscr) -> None:
    tutkimus = _valitse_tutkimus(stdscr, "Monista tutkimus — valitse lähde")
    if tutkimus is None:
        return
    piirra_otsikko(stdscr, f"Monista: {tutkimus['LuokittelunNimi']}")
    nimi = lue_teksti(stdscr, "Uuden tutkimuksen nimi", 3, f"{tutkimus['LuokittelunNimi']} (kopio)")
    if not nimi:
        nayta_viesti(stdscr, "Peruutettu (nimi pakollinen).")
        return
    slug = lue_teksti(stdscr, "Uusi slug (a-z, 0-9, - ja _)", 4)
    if not slug or not _validoi_slug(slug):
        nayta_viesti(stdscr, "Peruutettu (slug pakollinen, vain: a-z 0-9 - _).")
        return
    if mallit.hae_tutkimus_slugilla(slug):
        nayta_viesti(stdscr, f"Peruutettu (slug '{slug}' on jo käytössä).")
        return
    mallit.monista_tutkimus(tutkimus["TID"], nimi, slug)
    piirra_otsikko(stdscr, "Monista tutkimus")
    nayta_viesti(stdscr, f"Monistettu: {nimi} ({slug}). Vaihda arvot Muokkaa-toiminnolla.")


def _muokkaa(stdscr) -> None:
    tutkimus = _valitse_tutkimus(stdscr, "Muokkaa tutkimusta")
    if tutkimus is None:
        return
    piirra_otsikko(stdscr, f"Muokkaa: {tutkimus['LuokittelunNimi']}")
    nimi = lue_teksti(stdscr, "Tutkimuksen nimi", 3, tutkimus["LuokittelunNimi"])
    slug = lue_teksti(stdscr, "Slug", 4, tutkimus["Slug"])
    if not slug or not _validoi_slug(slug):
        nayta_viesti(stdscr, "Peruutettu (slug virheellinen).")
        return
    lukuvuosi = lue_teksti(stdscr, "Lukuvuosi (esim. 2024-2025)", 5, tutkimus.get("Lukuvuosi") or "")
    if not _validoi_lukuvuosi(lukuvuosi):
        nayta_viesti(stdscr, "Peruutettu (lukuvuosi pakollinen, muoto YYYY-YYYY).")
        return
    verkkosivu = lue_teksti(stdscr, "Verkkosivu (URL, tyhjä = ei)", 6, tutkimus.get("Verkkosivu") or "")
    luokittelukehote = lue_teksti(stdscr, "Valintakehote", 7, tutkimus["Luokittelukehote"])
    arviointikehote = lue_teksti(stdscr, "Arviointikehote", 8, tutkimus["Arviointikehote"])
    raportointikehote = lue_teksti(stdscr, "Raportointikehote", 9, tutkimus.get("Raportointikehote") or "")
    tasorajaus = _valitse_tasot(stdscr, tutkimus["Tasorajaus"] or "")
    korkeakoulut = _valitse_korkeakoulut(stdscr, mallit.hae_tutkimuksen_korkeakoulut(tutkimus["TID"]))
    if not korkeakoulut:
        nayta_viesti(stdscr, "Peruutettu (valitse vähintään yksi korkeakoulu).")
        return
    oppiainerajaus = _valitse_oppiaineet(stdscr, korkeakoulut, tutkimus["Oppiainerajaus"] or "")
    mallit.paivita_tutkimus(tutkimus["TID"], nimi, slug, lukuvuosi, luokittelukehote, tasorajaus, oppiainerajaus, arviointikehote, raportointikehote, verkkosivu=verkkosivu)
    mallit.aseta_tutkimuksen_korkeakoulut(tutkimus["TID"], korkeakoulut)
    piirra_otsikko(stdscr, "Muokkaa tutkimusta")
    nayta_viesti(stdscr, f"Päivitetty: {nimi}")


def _poista(stdscr) -> None:
    tutkimus = _valitse_tutkimus(stdscr, "Poista tutkimus")
    if tutkimus is None:
        return
    piirra_otsikko(stdscr, "Poista tutkimus")
    vahvistus = lue_teksti(stdscr, f"Poistetaanko '{tutkimus['LuokittelunNimi']}'? (kyllä/ei)", 3)
    if vahvistus.lower() in ("kyllä", "k", "kylla"):
        mallit.poista_tutkimus(tutkimus["TID"])
        nayta_viesti(stdscr, "Poistettu.")
    else:
        nayta_viesti(stdscr, "Peruutettu.")


def _hallinnoi_kysymyksia(stdscr) -> None:
    tutkimus = _valitse_tutkimus(stdscr, "Hallinnoi kysymyksiä — valitse tutkimus")
    if tutkimus is None:
        return
    kysymysnaytto.nayta(stdscr, tutkimus)


def _listaa(stdscr) -> None:
    tutkimukset = mallit.hae_tutkimukset()
    piirra_otsikko(stdscr, "Tutkimukset")
    if not tutkimukset:
        nayta_viesti(stdscr, "Ei tutkimuksia tietokannassa.")
        return
    korkeus, leveys = stdscr.getmaxyx()
    osoite = _webui_osoite()
    rivi = 3
    for t in tutkimukset:
        lukuvuosi = t.get("Lukuvuosi") or "—"
        rivit = [
            f"{t['LuokittelunNimi']} ({t['Slug']}) · {lukuvuosi}",
            f"  WebUI: {osoite}/tutkimukset/{t['Slug']}",
        ]
        verkkosivu = (t.get("Verkkosivu") or "").strip()
        if verkkosivu:
            rivit.append(f"  Verkkosivu: {verkkosivu}")
        for teksti in rivit:
            if rivi >= korkeus - 2:  # jätä tila viestiriville
                break
            stdscr.addstr(rivi, 0, teksti[:leveys - 1])  # rajaa, ettei rivi rivity/ylivuoda
            rivi += 1
        rivi += 1  # tyhjä rivi tutkimusten väliin
        if rivi >= korkeus - 2:
            break
    nayta_viesti(stdscr, "")
