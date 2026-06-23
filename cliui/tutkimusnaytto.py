"""Tutkimusten hallintanäkymä: listaa, lisää, muokkaa ja poista."""
import os
import re

from tietokanta import mallit
from cliui import kysymysnaytto
from cliui.apurit import (piirra_otsikko, nayta_viesti, lue_teksti, valitse_listasta,
                          valitse_monivalinta, muokkaa_lomake)

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


def _tutkimus_lomake(stdscr, otsikko: str, tutkimus: dict | None = None) -> dict | None:
    """Yhteinen lomake tutkimuksen lisäykseen ja muokkaukseen (DRY). Kaikki kentät
    näkyvissä yhtä aikaa; iso tekstikenttä avautuu rivittyvänä editorina. Palauttaa
    arvot-sanakirjan tai None jos peruutettu."""
    t = tutkimus or {}
    kkid_alku = mallit.hae_tutkimuksen_korkeakoulut(t["TID"]) if tutkimus else []
    pakollinen = lambda nimi: (lambda v: None if (v or "").strip() else f"{nimi} on pakollinen.")
    kentat = [
        {"avain": "nimi", "otsikko": "Tutkimuksen nimi", "arvo": t.get("LuokittelunNimi", ""),
         "validoi": pakollinen("Nimi")},
        {"avain": "slug", "otsikko": "Slug (a-z, 0-9, - ja _)", "arvo": t.get("Slug", ""),
         "validoi": lambda v: None if v and _validoi_slug(v) else "Slug: vain a-z 0-9 - _ (pakollinen)."},
        {"avain": "lukuvuosi", "otsikko": "Lukuvuosi (esim. 2024-2025)", "arvo": t.get("Lukuvuosi") or "",
         "validoi": lambda v: None if _validoi_lukuvuosi(v) else "Lukuvuosi muodossa YYYY-YYYY (pakollinen)."},
        {"avain": "verkkosivu", "otsikko": "Verkkosivu (URL, tyhjä = ei)", "arvo": t.get("Verkkosivu") or ""},
        {"avain": "luokittelukehote", "otsikko": "Valintakehote (tyhjä = pelkkä meta-luokittelu, ei LLM:ää)",
         "arvo": t.get("Luokittelukehote", "")},
        {"avain": "arviointikehote", "otsikko": "Arviointikehote", "arvo": t.get("Arviointikehote", ""),
         "validoi": pakollinen("Arviointikehote")},
        {"avain": "raportointikehote", "otsikko": "Raportointikehote (tyhjä = ei)",
         "arvo": t.get("Raportointikehote") or ""},
        {"avain": "tasorajaus", "otsikko": "Tasorajaus", "arvo": t.get("Tasorajaus") or "",
         "muokkain": lambda s, v, a: _valitse_tasot(s, v),
         "esikatselu": lambda v: v or "(kaikki tasot)"},
        {"avain": "korkeakoulut", "otsikko": "Korkeakoulut", "arvo": kkid_alku,
         "muokkain": lambda s, v, a: _valitse_korkeakoulut(s, v),
         "esikatselu": lambda v: f"{len(v)} korkeakoulua valittu" if v else "(ei valittu)",
         "validoi": lambda v: None if v else "Valitse vähintään yksi korkeakoulu."},
        {"avain": "oppiainerajaus", "otsikko": "Oppiainerajaus", "arvo": t.get("Oppiainerajaus") or "",
         "muokkain": lambda s, v, a: _valitse_oppiaineet(s, a["korkeakoulut"], v),
         "esikatselu": lambda v: v or "(kaikki oppiaineet)"},
    ]
    return muokkaa_lomake(stdscr, otsikko, kentat)


def _lisaa(stdscr) -> None:
    arvot = _tutkimus_lomake(stdscr, "Lisää tutkimus")
    if arvot is None:
        return
    tid = mallit.lisaa_tutkimus(
        arvot["nimi"], arvot["slug"], arvot["lukuvuosi"], arvot["luokittelukehote"],
        arvot["tasorajaus"], arvot["oppiainerajaus"], arvot["arviointikehote"],
        arvot["raportointikehote"], verkkosivu=arvot["verkkosivu"])
    mallit.aseta_tutkimuksen_korkeakoulut(tid, arvot["korkeakoulut"])
    piirra_otsikko(stdscr, "Lisää tutkimus")
    nayta_viesti(stdscr, f"Lisätty: {arvot['nimi']} ({arvot['slug']})")


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
    arvot = _tutkimus_lomake(stdscr, f"Muokkaa: {tutkimus['LuokittelunNimi']}", tutkimus)
    if arvot is None:
        return
    mallit.paivita_tutkimus(
        tutkimus["TID"], arvot["nimi"], arvot["slug"], arvot["lukuvuosi"],
        arvot["luokittelukehote"], arvot["tasorajaus"], arvot["oppiainerajaus"],
        arvot["arviointikehote"], arvot["raportointikehote"], verkkosivu=arvot["verkkosivu"])
    mallit.aseta_tutkimuksen_korkeakoulut(tutkimus["TID"], arvot["korkeakoulut"])
    piirra_otsikko(stdscr, "Muokkaa tutkimusta")
    nayta_viesti(stdscr, f"Päivitetty: {arvot['nimi']}")


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
