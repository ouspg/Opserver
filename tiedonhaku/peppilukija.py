"""Peppi-järjestelmän opinto-oppaan lukija (esim. Oulun yliopisto).

Rajapinnan rakenne dokumentoitu tiedostossa tiedonhaku/PEPPI.md.
"""
import json
import re

import requests

from tietokanta import mallit
from tiedonhaku.opslukija import OpsLukija

# Kurssikuvauksen "Taso"-osion teksti -> Kurssi-taulun Taso-enum.
TASO_KARTTA = {
    "yleisopinnot": "yleis",
    "perusopinnot": "perus",
    "aineopinnot": "aine",
    "syventävät opinnot": "syventävä",
}

# contentList-osiot, jotka kootaan kurssikuvaukseksi LLM:ää varten.
KUVAUS_OSIOT = [
    "Osaamistavoitteet",
    "Sisältö",
    "Suoritustavat",
    "Toteutustavat",
    "Esitietovaatimukset",
    "Lisätiedot",
]


def _fi(monikielinen: dict | None) -> str:
    if not monikielinen:
        return ""
    return (monikielinen.get("valueFi") or monikielinen.get("valueEn") or "").strip()


_VALIDI_TASOT = set(TASO_KARTTA.values())


def paattele_taso(taso_teksti: str) -> str | None:
    taso = TASO_KARTTA.get((taso_teksti or "").strip().lower())
    return taso if taso in _VALIDI_TASOT else None


def _turvallinen_float(arvo) -> float | None:
    if arvo is None:
        return None
    try:
        return float(arvo)
    except (ValueError, TypeError):
        return None


def _kokoa_kuvaus(sisalto: dict) -> str:
    osat = []
    for otsikko in KUVAUS_OSIOT:
        teksti = (sisalto.get(otsikko) or "").strip()
        if teksti:
            osat.append(f"{otsikko}:\n{teksti}")
    return "\n\n".join(osat)


def _hae_bundle_js(ops_osoite: str) -> str:
    """Hakee Peppi-frontendin JS-bundlen tekstinä (sisältää kausikonfiguraation)."""
    pohja = ops_osoite.rstrip("/")
    html = requests.get(pohja, timeout=30).text
    osuma = re.search(r'src="(main\.[a-f0-9]+\.js)"', html)
    if not osuma:
        raise ValueError(f"Ei löydy main.js URL:ia sivulta {pohja}")
    return requests.get(f"{pohja}/{osuma.group(1)}", timeout=60).text


def _kaudet_taulukosta(js: str) -> list[str] | None:
    """Lukee bundlessa julistetun eksplisiittisen kausitaulukon (["YYYY-YYYY", ...]).

    Tämä on frontendin pudotusvalikon lähde ja koodaa jokaisen kauden oman
    jaksonsa, joten 1-/2-/3-/sekapituiset kaudet luetaan sellaisinaan ilman
    pituuden oletusta. Palauttaa None jos taulukkoa ei ole bundlessa.
    """
    taulukot = re.findall(r'\[\s*(?:"\d{4}-\d{2,4}"\s*,\s*)+"\d{4}-\d{2,4}"\s*\]', js)
    if not taulukot:
        return None
    paras = max(taulukot, key=lambda t: len(re.findall(r"\d{4}-\d{2,4}", t)))
    return list(dict.fromkeys(re.findall(r"\d{4}-\d{2,4}", paras)))


def _kaudet_laskettuna(js: str) -> list[str]:
    """Laskee kaudet konfiguraatioarvoista kun eksplisiittistä taulukkoa ei ole.

    firstSchoolYear .. currentPeriodStartYear, askel = curriculumPeriod (oletus 1,
    jos arvoa ei ole). Sietää sekä kaksoispiste- että yhtäsuuruus-syntaksia.
    """
    def lue(avain: str, oletus: int | None = None) -> int:
        o = re.search(rf"{avain}\s*[:=]\s*(\d+)", js)
        if o:
            return int(o.group(1))
        if oletus is not None:
            return oletus
        raise ValueError(f"Ei löydy arvoa '{avain}' JS-bundlesta")
    return generoi_kaudet(lue("firstSchoolYear"), lue("currentPeriodStartYear"),
                          lue("curriculumPeriod", 1))


def lue_kaudet_bundlesta(js: str) -> list[str]:
    """Kausilista bundlesta: ensisijaisesti eksplisiittinen taulukko, muuten laskettu."""
    return _kaudet_taulukosta(js) or _kaudet_laskettuna(js)


def generoi_kaudet(ensimmainen: int, viimeinen: int, pituus: int) -> list[str]:
    """Generoi kausilistat config-arvoista (testattavissa ilman verkkoa)."""
    kaudet = []
    vuosi = ensimmainen
    while vuosi <= viimeinen:
        kaudet.append(f"{vuosi}-{vuosi + pituus}")
        vuosi += pituus
    return kaudet


class PeppiLukija(OpsLukija):

    def _api(self) -> str:
        """Korkeakoulun Peppi-backendin API-juuri tietokannan ApiOsoite-tiedosta."""
        api = self.korkeakoulu.get("ApiOsoite")
        if not api:
            raise ValueError(
                "Korkeakoulun ApiOsoite puuttuu — lisää tai muokkaa korkeakoulu "
                "uudelleen, jolloin API-osoite selvitetään ja tallennetaan."
            )
        return f"{api.rstrip('/')}/api"

    def hae_kurssi(self, kurssi_id: str, kausi: str = "2025-2026") -> dict:
        """Hakee ja jäsentää yhden kurssin Peppi-rajapinnasta."""
        url = f"{self._api()}/course/{kurssi_id}?period={kausi}"
        return self._jasenna_kurssi(self._hae_json(url))

    def hae_saatavilla_kaudet(self) -> list[str]:
        """Lukee saatavilla olevat OPS-kaudet Peppi-etusivun JS-bundlesta.

        Ensisijaisesti bundlessa julistettu eksplisiittinen kausitaulukko (joka
        kattaa myös sekapituiset OPS:t), muuten laskettuna konfiguraatioarvoista.
        """
        return lue_kaudet_bundlesta(_hae_bundle_js(self.korkeakoulu["OpsOsoite"]))

    def hae_kurssit(self, kausi: str, edistyminen_cb=None) -> int:
        """Käy läpi koko opinto-oppaan ja tallentaa kaikki kurssit tietokantaan.

        Palauttaa tallennettujen kurssien määrän. Idempotentti: uudelleenajo
        päivittää olemassa olevat rivit (ON DUPLICATE KEY UPDATE).
        """
        ohjelma_idt = self._hae_ohjelma_idt(kausi)
        kurssi_idt = self._keraa_kurssi_idt_ohjelmista(ohjelma_idt, kausi)
        jo_kannassa = mallit.hae_tallennetut_lahde_idt(self.korkeakoulu["KKID"], kausi)
        kurssi_idt = [kid for kid in kurssi_idt if str(kid) not in jo_kannassa]
        yhteensa = len(kurssi_idt)
        tallennettu = 0
        ohitettu = 0
        for kurssi_id in kurssi_idt:
            try:
                kurssi_json = self._hae_json(f"{self._api()}/course/{kurssi_id}?period={kausi}")
            except requests.exceptions.RequestException:
                ohitettu += 1
                continue
            kurssi = self._jasenna_kurssi(kurssi_json)
            mallit.tallenna_kurssi(
                kkid=self.korkeakoulu["KKID"],
                lahde_id=kurssi["lahde_id"],
                koodi=kurssi["koodi"],
                kurssi_nimi=kurssi["kurssi_nimi"],
                taso=kurssi["taso"],
                oppiaine=kurssi["oppiaine"],
                opintopisteet=kurssi["opintopisteet"],
                opetusvuosi=kausi,
                ops_kuvaus=json.dumps(kurssi_json, ensure_ascii=False),
            )
            tallennettu += 1
            if edistyminen_cb:
                edistyminen_cb(tallennettu, yhteensa, kurssi["kurssi_nimi"])
        return tallennettu, ohitettu

    # --- Yksityiset apumetodit ---

    def _hae_ohjelma_idt(self, kausi: str) -> list[str]:
        nav = self._hae_json(f"{self._api()}/navigation?period={kausi}")
        idt = []
        for kategoria in nav:
            koulutukset = self._hae_json(
                f"{self._api()}/education/{kategoria['id']}/education-type?period={kausi}"
            )
            for koulutus in koulutukset:
                for lapsi in koulutus.get("children") or []:
                    if lapsi.get("type") == "PROGRAMME":
                        idt.append(str(lapsi["id"]))
        return list(dict.fromkeys(idt))

    def _keraa_kurssi_idt_ohjelmista(self, ohjelma_idt: list[str], kausi: str) -> list[str]:
        idt = []
        for ohjelma_id in ohjelma_idt:
            puu = self._hae_json(f"{self._api()}/accomplishment-plan/{ohjelma_id}?period={kausi}")
            idt.extend(self._keraa_solmuista(puu, "COURSE_UNIT"))
        return list(dict.fromkeys(idt))

    def _keraa_solmuista(self, solmu, tyyppi: str) -> list[str]:
        """Kerää rekursiivisesti kaikki annetun tyypin solmujen id:t."""
        if isinstance(solmu, list):
            return [i for s in solmu for i in self._keraa_solmuista(s, tyyppi)]
        if not isinstance(solmu, dict):
            return []
        idt = []
        if solmu.get("type") == tyyppi:
            idt.append(str(solmu["id"]))
        for lapsi in solmu.get("children") or []:
            idt.extend(self._keraa_solmuista(lapsi, tyyppi))
        return idt

    def _jasenna_kurssi(self, data: dict) -> dict:
        sisalto = {
            _fi(osio.get("title")): (osio.get("content") or {}).get("valueFi", "") or ""
            for osio in data.get("contentList", [])
        }
        credits = data.get("credits")
        return {
            "kurssi_nimi": _fi(data.get("name"))[:255],
            "koodi": data.get("code"),
            "taso": (sisalto.get("Taso") or "").strip()[:30] or None,
            "oppiaine": (sisalto.get("Oppiaine") or "").strip()[:500],
            "opintopisteet": str(credits)[:30] if credits is not None else None,
            "ops_kuvaus": _kokoa_kuvaus(sisalto),
            "lahde_id": data.get("id"),
        }
