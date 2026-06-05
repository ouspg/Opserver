"""Peppi-järjestelmän opinto-oppaan lukija (esim. Oulun yliopisto).

Rajapinnan rakenne dokumentoitu tiedostossa tiedonhaku/PEPPI.md.
"""
import json
import time

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

# Kandidaattikausia jotka kokeillaan automaattisessa kaudenetsinnässä.
# Muoto: (alkuvuosi, vuosia). Generoidaan dynaamisesti _kausi_kandidaatit():ssa.
_HAKU_ALKUVUOSI = 2022
_HAKU_LOPPUVUOSI = 2027


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


def _kausi_kandidaatit() -> list[str]:
    """Generoi testattavat OPS-kausimerkkijonot (esim. '2024-2025', '2022-2024')."""
    kaudet = []
    for alku in range(_HAKU_ALKUVUOSI, _HAKU_LOPPUVUOSI + 1):
        for pituus in range(1, 5):
            loppu = alku + pituus
            if loppu <= _HAKU_LOPPUVUOSI + 1:
                kaudet.append(f"{alku}-{loppu}")
    return kaudet


class PeppiLukija(OpsLukija):

    def hae_kurssi(self, kurssi_id: str, kausi: str = "2025-2026") -> dict:
        """Hakee ja jäsentää yhden kurssin Peppi-rajapinnasta."""
        url = f"{BACKEND}/course/{kurssi_id}?period={kausi}"
        return self._jasenna_kurssi(self._hae_json(url))

    def hae_saatavilla_kaudet(self) -> list[str]:
        """Palauttaa OPS-kaudet, joille löytyy dataa tässä Peppi-instanssissa.

        Kokeilee eri kausiforemaatteja navigaation ensimmäistä kategoriaa vasten.
        Ohittaa crawl-viiveen (metadata-kutsu, ei kurssisivuja).
        """
        nav = self._hae_json(f"{BACKEND}/navigation", viive=False)
        if not nav:
            return []
        ensimmainen_id = nav[0]["id"]
        saatavilla = []
        for kausi in _kausi_kandidaatit():
            time.sleep(0.2)
            data = self._hae_json(
                f"{BACKEND}/education/{ensimmainen_id}/education-type?period={kausi}",
                viive=False,
            )
            if data:
                saatavilla.append(kausi)
        return saatavilla

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
