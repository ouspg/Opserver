"""Tutkimusten hallintanäkymä: listaa, lisää, muokkaa ja poista."""
import re

from tietokanta import mallit
from cliui import kysymysnaytto
from cliui.apurit import piirra_otsikko, nayta_viesti, lue_teksti, valitse_listasta, valitse_monivalinta

_SLUG_KAAVA = re.compile(r'^[a-z0-9][a-z0-9_-]*$')


def _valitse_tasot(stdscr, oletus: str = "") -> str:
    tasot = mallit.hae_tasot()
    if not tasot:
        return oletus
    valitut = [t for t in oletus.split(",") if t.strip() in tasot] if oletus else []
    tulos = valitse_monivalinta(stdscr, "Valitse sallitut tasot (tyhjä = kaikki)", tasot, valitut)
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
            ["Lisää tutkimus", "Muokkaa tutkimusta", "Poista tutkimus",
             "Listaa tutkimukset", "Hallinnoi kysymyksiä"],
        )
        if valinta is None:
            return
        if valinta == 0:
            _lisaa(stdscr)
        elif valinta == 1:
            _muokkaa(stdscr)
        elif valinta == 2:
            _poista(stdscr)
        elif valinta == 3:
            _listaa(stdscr)
        elif valinta == 4:
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
    luokittelukehote = lue_teksti(stdscr, "Valintakehote", 5)
    if not luokittelukehote:
        nayta_viesti(stdscr, "Peruutettu (valintakehote pakollinen).")
        return
    arviointikehote = lue_teksti(stdscr, "Arviointikehote", 6)
    if not arviointikehote:
        nayta_viesti(stdscr, "Peruutettu (arviointikehote pakollinen).")
        return
    oppiainerajaus = lue_teksti(stdscr, "Oppiainerajaus, pilkulla eroteltu (tyhjä = kaikki)", 7)
    tasorajaus = _valitse_tasot(stdscr)
    mallit.lisaa_tutkimus(nimi, slug, luokittelukehote, tasorajaus, oppiainerajaus, arviointikehote)
    piirra_otsikko(stdscr, "Lisää tutkimus")
    nayta_viesti(stdscr, f"Lisätty: {nimi} ({slug})")


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
    luokittelukehote = lue_teksti(stdscr, "Valintakehote", 5, tutkimus["Luokittelukehote"])
    arviointikehote = lue_teksti(stdscr, "Arviointikehote", 6, tutkimus["Arviointikehote"])
    oppiainerajaus = lue_teksti(stdscr, "Oppiainerajaus, pilkulla eroteltu (tyhjä = kaikki)", 7, tutkimus["Oppiainerajaus"] or "")
    tasorajaus = _valitse_tasot(stdscr, tutkimus["Tasorajaus"] or "")
    mallit.paivita_tutkimus(tutkimus["TID"], nimi, slug, luokittelukehote, tasorajaus, oppiainerajaus, arviointikehote)
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
    for i, t in enumerate(tutkimukset):
        rajaus = f"{t['Tasorajaus'] or '—'} / {t['Oppiainerajaus'] or '—'}"
        stdscr.addstr(3 + i, 0, f"{t['LuokittelunNimi']} ({t['Slug']}) · {rajaus}")
    nayta_viesti(stdscr, "")
