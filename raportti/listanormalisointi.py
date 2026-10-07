"""Lista-tyypin arviointikysymysten arvojen normalisointi ennen raportin generointia.

Lista-vastaukset (Vastaukset.Lista) ovat vapaata tekstiä, joten sama asia esiintyy
monessa muodossa ("Luennot"/"luennot"/"Luento-opetus"). Ennen raporttia:

  0. aiemmin hyväksytyt yhdistämiset sovelletaan automaattisesti (ListaYhdistys)
  a) kirjainkokoerot: saman lower()-muodon arvot → yleisimmän muodon mukaisiksi
  b) synonyymit: LLM ehdottaa yhdistämisiä (raportti.listasynonyymit)

Ehdotukset kuitataan käyttöliittymässä (cliui.ehdotusnaytto); tämä moduuli ei
tunne cursesia. Sekä hyväksytyt että hylätyt päätökset tallennetaan per kysymys,
jotta arviointien uudelleenajon raa'at arvot normalisoituvat seuraavalla kerralla
itsestään eikä hylättyä ehdotusta näytetä uudelleen.
"""
from dataclasses import dataclass

from llm import tiiviste
from tietokanta import mallit

# ListaYhdistys.Lahde/Kohde ovat VARCHAR(255) (indeksin pituusraja) — pidempiä
# arvoja ei ehdoteta eikä tallenneta (käytännössä listan kohdat ovat lyhyitä).
MAKSIMIPITUUS = 255


@dataclass
class Ehdotus:
    """Yksi yhdistämisehdotus lahde → kohde yhden kysymyksen sisällä.
    ehdotettu = alkuperäinen ehdotettu kohde: hylkäys muistetaan sillä, vaikka
    käyttäjä olisi muokannut kohdetta ennen hylkäystä."""
    kysid: int
    kysymys_nro: int
    kysymys: str
    lahde: str
    kohde: str
    ehdotettu: str = ""
    valittu: bool = True

    def __post_init__(self):
        if not self.ehdotettu:
            self.ehdotettu = self.kohde

    def rivi(self, kysymys_pituus: int = 40) -> str:
        merkki = "[x]" if self.valittu else "[ ]"
        kysymys = self.kysymys if len(self.kysymys) <= kysymys_pituus \
            else self.kysymys[:kysymys_pituus] + "..."
        return f'{merkki} {self.lahde} --> {self.kohde} (kysymyksessä {self.kysymys_nro}, "{kysymys}")'

    @property
    def hyvaksytty(self) -> bool:
        return self.valittu and bool(self.kohde) and self.kohde != self.lahde


# --- Puhdas logiikka ---

def valitse_yleisin(muodot: dict[str, int]) -> str:
    """Yleisin muoto mainintamäärän mukaan. Tasapelissä Unicode-koodipistejärjestyksessä
    ensimmäinen (isot kirjaimet ennen pieniä: "AI" < "Ai" < "ai") → deterministinen
    syöttöjärjestyksestä riippumatta."""
    return min(muodot, key=lambda m: (-muodot[m], m))


def kirjainkokoparit(maarat: dict[str, int]) -> list[tuple[str, str]]:
    """(lahde, kohde)-parit: saman lower()-muodon arvot yleisimmän muodon mukaisiksi."""
    ryhmat: dict[str, dict[str, int]] = {}
    for arvo, lkm in maarat.items():
        ryhmat.setdefault(arvo.lower(), {})[arvo] = lkm
    parit = []
    for muodot in ryhmat.values():
        if len(muodot) < 2:
            continue
        kohde = valitse_yleisin(muodot)
        parit.extend((m, kohde) for m in sorted(muodot) if m != kohde)
    return parit


def ratkaise_ketjut(kuvaus: dict[str, str]) -> dict[str, str]:
    """Transitiivinen sulkeuma: a→b, b→c ⇒ a→c, b→c. Syklit ja itseensä
    osoittavat kuvaukset pudotetaan (ei turvallista lopullista muotoa)."""
    tulos = {}
    for lahde in kuvaus:
        nahdyt, nyky = {lahde}, kuvaus[lahde]
        while nyky in kuvaus and nyky not in nahdyt:
            nahdyt.add(nyky)
            nyky = kuvaus[nyky]
        if nyky not in nahdyt:
            tulos[lahde] = nyky
    return tulos


def uusi_lista(lista: list, kuvaus: dict[str, str]) -> list:
    """Kuvaa listan merkkijonot ja poistaa duplikaatit (ensimmäinen esiintymä säilyy)."""
    tulos, nahdyt = [], set()
    for kohta in lista:
        uusi = kuvaus.get(kohta, kohta) if isinstance(kohta, str) else kohta
        avain = (type(uusi).__name__, repr(uusi))
        if avain not in nahdyt:
            nahdyt.add(avain)
            tulos.append(uusi)
    return tulos


def arvojoukon_tiiviste(arvot, kehote: str) -> str:
    """LLM:n jo käsittelemän arvojoukon tunniste: sama joukko + sama kehote → ei kysytä uudelleen."""
    return tiiviste.laske(kehote, "\x1f".join(sorted(arvot)))


def tallennetut_kuvaukset(paatokset: list[dict]) -> dict[int, dict[str, str]]:
    """Hyväksytyt päätökset → {KysID: {lahde: lopullinen kohde}}. Päätökset tulevat
    aikajärjestyksessä, joten saman lähteen uudempi hyväksyntä voittaa."""
    kuvaukset: dict[int, dict[str, str]] = {}
    for p in paatokset:
        if p["Hyvaksytty"]:
            kuvaukset.setdefault(p["KysID"], {})[p["Lahde"]] = p["Kohde"]
    return {kysid: k for kysid, k in
            ((kysid, ratkaise_ketjut(k)) for kysid, k in kuvaukset.items()) if k}


def hylatyt(paatokset: list[dict]) -> set[tuple[int, str, str]]:
    return {(p["KysID"], p["Lahde"], p["Kohde"]) for p in paatokset if not p["Hyvaksytty"]}


def kelvolliset_maarat(maarat: dict[str, int]) -> dict[str, int]:
    return {a: n for a, n in maarat.items() if a and len(a) <= MAKSIMIPITUUS}


# --- Kanta + orkestrointi ---

def lista_kysymykset(tid: int) -> list[dict]:
    """Tutkimuksen lista-tyypin kysymykset; nro = järjestysnumero kaikkien
    kysymysten joukossa (sama numerointi kuin raportissa)."""
    return [{**k, "nro": i} for i, k in enumerate(mallit.hae_kysymykset(tid), 1)
            if k.get("Luokittelu") == "lista"]


def sovella_tallennetut(tid: int) -> int:
    """Soveltaa aiemmin hyväksytyt yhdistämiset (esim. arviointien uudelleenajon
    jälkeen). Palauttaa muuttuneiden vastausrivien määrän; idempotentti."""
    kuvaukset = tallennetut_kuvaukset(mallit.hae_lista_paatokset(tid))
    if not kuvaukset:
        return 0
    return mallit.paivita_listat(tid, kuvaukset, uusi_lista, [], {})


def kirjainkoko_ehdotukset(tid: int, kysymykset: list[dict]) -> list[Ehdotus]:
    """Vaihe a): kirjainkokoerojen yhdistämisehdotukset (aiemmin hylätyt pois)."""
    maarat = mallit.hae_lista_arvomaarat(tid, [k["KysID"] for k in kysymykset])
    pois = hylatyt(mallit.hae_lista_paatokset(tid))
    ehdotukset = []
    for k in kysymykset:
        for lahde, kohde in kirjainkokoparit(kelvolliset_maarat(maarat.get(k["KysID"], {}))):
            if (k["KysID"], lahde, kohde) not in pois:
                ehdotukset.append(Ehdotus(k["KysID"], k["nro"], k["Kysymys"], lahde, kohde))
    return ehdotukset


def tallenna_kuittaus(tid: int, ehdotukset: list[Ehdotus],
                      lahetetyt: dict[int, set[str]] | None = None, kehote: str = "") -> int:
    """Kirjoittaa kuitatut ehdotukset yhdessä transaktiossa: hyväksytyt muuttavat
    Vastaukset.Listaa ja tallentuvat pysyviksi, hylätyt muistetaan.

    lahetetyt (vaihe b): LLM:lle lähetetyt arvojoukot per kysymys → tallennetaan
    kuittauksen jälkeisen joukon tiiviste, jotta samaa joukkoa ei kysytä uudelleen.
    Palauttaa muuttuneiden vastausrivien määrän."""
    kuvaukset: dict[int, dict[str, str]] = {}
    paatokset = []
    for e in ehdotukset:
        if e.hyvaksytty:
            kuvaukset.setdefault(e.kysid, {})[e.lahde] = e.kohde
            paatokset.append((e.kysid, e.lahde, e.kohde, True))
        else:
            paatokset.append((e.kysid, e.lahde, e.ehdotettu, False))
    kuvaukset = {kysid: ratkaise_ketjut(k) for kysid, k in kuvaukset.items()}
    kasitellyt = {
        kysid: arvojoukon_tiiviste({kuvaukset.get(kysid, {}).get(a, a) for a in arvot}, kehote)
        for kysid, arvot in (lahetetyt or {}).items()
    }
    return mallit.paivita_listat(tid, kuvaukset, uusi_lista, paatokset, kasitellyt)
