"""Peppi-järjestelmän opinto-oppaan lukija (esim. Oulun yliopisto).

Rajapinnan rakenne dokumentoitu tiedostossa tiedonhaku/PEPPI.md.
"""
import json
import re

import requests

from tietokanta import mallit
from tiedonhaku.opslukija import OpsLukija

BACKEND = "https://opasbe.peppi.oulu.fi/api"

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


def paattele_taso(taso_teksti: str) -> str | None:
    return TASO_KARTTA.get(taso_teksti.strip().lower())


def _kokoa_kuvaus(sisalto: dict) -> str:
    osat = []
    for otsikko in KUVAUS_OSIOT:
        teksti = (sisalto.get(otsikko) or "").strip()
        if teksti:
            osat.append(f"{otsikko}:\n{teksti}")
    return "\n\n".join(osat)


def _lue_kausiconfig_js_bundlesta(ops_osoite: str) -> tuple[int, int, int]:
    """Lukee kausikonfiguraation Peppi-etusivun JS-bundlesta.

    Palauttaa (ensimmainen_vuosi, viimeinen_vuosi, kauden_pituus).
    Peppi renderöi kausilistan pelkästään näistä kolmesta arvosta —
    erillistä API-endpointtia ei ole.
    """
    pohja = ops_osoite.rstrip("/")
    html = requests.get(pohja, timeout=30).text
    osuma = re.search(r'src="(main\.[a-f0-9]+\.js)"', html)
    if not osuma:
        raise ValueError(f"Ei löydy main.js URL:ia sivulta {pohja}")
    js_url = f"{pohja}/{osuma.group(1)}"
    js = requests.get(js_url, timeout=60).text

    def etsi_int(kaava: str) -> int:
        o = re.search(kaava, js)
        if not o:
            raise ValueError(f"Ei löydy kaavaa '{kaava}' JS-bundlesta")
        return int(o.group(1))

    ensimmainen = etsi_int(r'firstSchoolYear:(\d{4})')
    viimeinen = etsi_int(r'currentPeriodStartYear:(\d{4})')
    pituus = etsi_int(r'curriculumPeriod:(\d+)')
    return ensimmainen, viimeinen, pituus


def generoi_kaudet(ensimmainen: int, viimeinen: int, pituus: int) -> list[str]:
    """Generoi kausilistat config-arvoista (testattavissa ilman verkkoa)."""
    kaudet = []
    vuosi = ensimmainen
    while vuosi <= viimeinen:
        kaudet.append(f"{vuosi}-{vuosi + pituus}")
        vuosi += pituus
    return kaudet


class PeppiLukija(OpsLukija):

    def hae_kurssi(self, kurssi_id: str, kausi: str = "2025-2026") -> dict:
        """Hakee ja jäsentää yhden kurssin Peppi-rajapinnasta."""
        url = f"{BACKEND}/course/{kurssi_id}?period={kausi}"
        return self._jasenna_kurssi(self._hae_json(url))

    def hae_saatavilla_kaudet(self) -> list[str]:
        """Lukee saatavilla olevat OPS-kaudet suoraan Peppi-etusivun JS-bundlesta.

        Peppi laskee kausilistan kolmesta JS-konfiguraatioarvosta:
        firstSchoolYear, currentPeriodStartYear, curriculumPeriod.
        """
        ops_osoite = self.korkeakoulu["OpsOsoite"]
        ensimmainen, viimeinen, pituus = _lue_kausiconfig_js_bundlesta(ops_osoite)
        return generoi_kaudet(ensimmainen, viimeinen, pituus)

    def hae_kurssit(self, kausi: str, edistyminen_cb=None) -> int:
        """Käy läpi koko opinto-oppaan ja tallentaa kaikki kurssit tietokantaan.

        Palauttaa tallennettujen kurssien määrän. Idempotentti: uudelleenajo
        päivittää olemassa olevat rivit (ON DUPLICATE KEY UPDATE).
        """
        ohjelma_idt = self._hae_ohjelma_idt(kausi)
        kurssi_idt = self._keraa_kurssi_idt_ohjelmista(ohjelma_idt, kausi)
        yhteensa = len(kurssi_idt)
        tallennettu = 0
        for kurssi_id in kurssi_idt:
            kurssi_json = self._hae_json(f"{BACKEND}/course/{kurssi_id}?period={kausi}")
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
                edistyminen_cb(tallennettu, yhteensa)
        return tallennettu

    # --- Yksityiset apumetodit ---

    def _hae_ohjelma_idt(self, kausi: str) -> list[str]:
        nav = self._hae_json(f"{BACKEND}/navigation?period={kausi}")
        idt = []
        for kategoria in nav:
            koulutukset = self._hae_json(
                f"{BACKEND}/education/{kategoria['id']}/education-type?period={kausi}"
            )
            for koulutus in koulutukset:
                for lapsi in koulutus.get("children") or []:
                    if lapsi.get("type") == "PROGRAMME":
                        idt.append(str(lapsi["id"]))
        return list(dict.fromkeys(idt))

    def _keraa_kurssi_idt_ohjelmista(self, ohjelma_idt: list[str], kausi: str) -> list[str]:
        idt = []
        for ohjelma_id in ohjelma_idt:
            puu = self._hae_json(f"{BACKEND}/accomplishment-plan/{ohjelma_id}?period={kausi}")
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
        return {
            "kurssi_nimi": _fi(data.get("name")),
            "koodi": data.get("code"),
            "taso": paattele_taso(sisalto.get("Taso", "")),
            "oppiaine": (sisalto.get("Oppiaine") or "").strip(),
            "opintopisteet": data.get("credits"),
            "ops_kuvaus": _kokoa_kuvaus(sisalto),
            "lahde_id": data.get("id"),
        }
