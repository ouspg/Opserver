"""Sisu-järjestelmän opinto-oppaan lukija (esim. Jyväskylän yliopisto).

Käyttää KORI-rajapintaa:
  /kori/api/curriculum-periods  → kausilistat
  /kori/api/organisations       → organisaatiot nimillä
  /kori/api/course-unit-search  → kurssihaku per org (vaatii orgId-parametrin)
  /kori/api/course-units/by-group-id → erähaku täydet tiedot
"""
import json
import re

import requests

from tietokanta import mallit
from tiedonhaku.opslukija import OpsLukija

TASO_KARTTA = {
    "urn:code:study-level:basic-studies": "perus",
    "urn:code:study-level:intermediate-studies": "aine",
    "urn:code:study-level:advanced-studies": "syventävä",
    "urn:code:study-level:other-studies": "yleis",
}

ERAKOKO = 30  # groupId:tä per /by-group-id-kutsu


def _muunna_taso(study_level_urn: str | None) -> str | None:
    return TASO_KARTTA.get(study_level_urn or "")


def _fi(monikielinen: dict | None) -> str:
    if not monikielinen:
        return ""
    return (monikielinen.get("fi") or monikielinen.get("en") or "").strip()


def _riisu_html(teksti: str | None) -> str:
    if not teksti:
        return ""
    return re.sub(r"<[^>]+>", " ", teksti).strip()


class SisuLukija(OpsLukija):

    def __init__(self, korkeakoulu: dict):
        super().__init__(korkeakoulu)
        self._yliopisto_id: str | None = None
        self._kaudet: dict[str, str] | None = None  # {kausi_str: period_id}
        self._organisaatiot: dict[str, str] | None = None  # {org_id: nimi_fi}

    # --- Julkiset metodit ---

    def hae_saatavilla_kaudet(self) -> list[str]:
        """Palauttaa saatavilla olevat OPS-kaudet laskevassa järjestyksessä."""
        return sorted(self._lataa_kaudet().keys(), reverse=True)

    def hae_kurssit(self, kausi: str, edistyminen_cb=None, tila_cb=None) -> tuple[int, int]:
        """Hakee kaikki kurssit annetulle kaudelle ja tallentaa tietokantaan.

        tila_cb(viesti: str) — valinnainen, kutsutaan keräysvaiheessa per org.
        edistyminen_cb(n, yhteensa, nimi) — kutsutaan tallennusvaiheessa per kurssi.
        """
        yliopisto_id = self._yliopisto_org_id()
        kaudet = self._lataa_kaudet()
        if kausi not in kaudet:
            raise ValueError(f"Kausi '{kausi}' ei ole saatavilla")
        kausi_id = kaudet[kausi]
        organisaatiot = self._lataa_organisaatiot()
        pohja = self._pohja()
        kkid = self.korkeakoulu["KKID"]

        group_idt = self._keraa_group_idt(pohja, yliopisto_id, kausi_id, list(organisaatiot.keys()), tila_cb)
        jo_kannassa = mallit.hae_tallennetut_lahde_idt(kkid, kausi)

        yhteensa = len(group_idt)
        tallennettu = 0
        ohitettu = 0

        for i in range(0, len(group_idt), ERAKOKO):
            era = group_idt[i : i + ERAKOKO]
            try:
                kurssit_data = self._hae_kurssierat(pohja, yliopisto_id, era)
            except requests.exceptions.RequestException:
                ohitettu += len(era)
                continue
            for kurssi_data in kurssit_data:
                # Sisulla LahdeId = kurssin yksilöivä UUID (id-kenttä),
                # ei groupId — groupId ei toimi Sisun SPA-reitityksessä.
                uuid = kurssi_data.get("id")
                if uuid in jo_kannassa:
                    continue
                kurssi = self._jasenna_kurssi(kurssi_data, organisaatiot)
                mallit.tallenna_kurssi(
                    kkid=kkid,
                    lahde_id=uuid,
                    koodi=kurssi["koodi"],
                    kurssi_nimi=kurssi["kurssi_nimi"],
                    taso=kurssi["taso"],
                    oppiaine=kurssi["oppiaine"],
                    opintopisteet=kurssi["opintopisteet"],
                    opetusvuosi=kausi,
                    ops_kuvaus=json.dumps(kurssi_data, ensure_ascii=False),
                )
                tallennettu += 1
                if edistyminen_cb:
                    edistyminen_cb(tallennettu, yhteensa, kurssi["kurssi_nimi"])

        return tallennettu, ohitettu

    # --- Yksityiset apumetodit ---

    def _pohja(self) -> str:
        """Sisun API-origin tietokannasta (ApiOsoite); varafallback OpsOsoitteeseen."""
        return (self.korkeakoulu.get("ApiOsoite") or self.korkeakoulu["OpsOsoite"]).rstrip("/")

    def _yliopisto_org_id(self) -> str:
        if not self._yliopisto_id:
            pohja = self._pohja()
            vastaus = requests.get(f"{pohja}/student/universityConfig.js", timeout=30)
            vastaus.raise_for_status()
            osuma = re.search(r"var universityConfig\s*=\s*(\{.*?\});", vastaus.text, re.DOTALL)
            if not osuma:
                raise ValueError(f"universityOrgId ei löydy: {pohja}/student/universityConfig.js")
            config = json.loads(osuma.group(1))
            self._yliopisto_id = config["homeOrganisations"][0]["id"]
        return self._yliopisto_id

    def _lataa_kaudet(self) -> dict[str, str]:
        if self._kaudet is None:
            yliopisto_id = self._yliopisto_org_id()
            pohja = self._pohja()
            data = self._hae_json(
                f"{pohja}/kori/api/curriculum-periods?universityOrgId={yliopisto_id}"
            )
            self._kaudet = {}
            for cp in data:
                if cp.get("documentState") != "ACTIVE":
                    continue
                lyhenne = _fi(cp.get("abbreviation"))
                if re.match(r"^\d{4}-\d{2,4}$", lyhenne):  # YYYY-YYYY (JYU/LUT/TUNI) ja YYYY-YY (HY)
                    self._kaudet[lyhenne] = cp["id"]
        return self._kaudet

    def _lataa_organisaatiot(self) -> dict[str, str]:
        if self._organisaatiot is None:
            yliopisto_id = self._yliopisto_org_id()
            pohja = self._pohja()
            data = self._hae_json(
                f"{pohja}/kori/api/organisations?universityOrgId={yliopisto_id}"
            )
            self._organisaatiot = {
                org["id"]: _fi(org.get("name")) or org["id"]
                for org in data
            }
        return self._organisaatiot

    def _keraa_group_idt(
        self, pohja: str, yliopisto_id: str, kausi_id: str, org_idt: list[str], tila_cb=None
    ) -> list[str]:
        """Kerää kaikki uniikki kurssi-groupId:t paginoiden per organisaatio."""
        nahdyt: set[str] = set()
        järjestetty: list[str] = []
        n_orgs = len(org_idt)
        for org_nro, org_id in enumerate(org_idt, 1):
            start = 0
            limit = 100
            while True:
                url = (
                    f"{pohja}/kori/api/course-unit-search"
                    f"?universityOrgId={yliopisto_id}&orgId={org_id}"
                    f"&curriculumPeriodId={kausi_id}&start={start}&limit={limit}&uiLang=fi"
                )
                try:
                    data = self._hae_json(url)
                except requests.exceptions.RequestException:
                    break
                tulokset = data.get("searchResults", [])
                for r in tulokset:
                    gid = r.get("groupId")
                    if gid and gid not in nahdyt:
                        nahdyt.add(gid)
                        järjestetty.append(gid)
                if tila_cb:
                    tila_cb(f"Vaihe 1/2: kerätään kurssilistauksia... org {org_nro}/{n_orgs}, {len(järjestetty)} löydetty")
                if len(tulokset) < limit or start + limit >= data.get("total", 0):
                    break
                start += limit
        return järjestetty

    def _hae_kurssierat(
        self, pohja: str, yliopisto_id: str, group_idt: list[str]
    ) -> list[dict]:
        """Hakee erän täydet kurssitiedot yhdellä API-kutsulla."""
        params = "&".join(f"groupId={gid}" for gid in group_idt)
        url = f"{pohja}/kori/api/course-units/by-group-id?{params}&universityId={yliopisto_id}"
        return self._hae_json(url)

    def _jasenna_kurssi(self, data: dict, organisaatiot: dict[str, str]) -> dict:
        org_id = next(
            (
                o["organisationId"]
                for o in data.get("organisations", [])
                if o.get("roleUrn", "").endswith(":responsible-organisation")
            ),
            None,
        )
        credits = data.get("credits") or {}
        op = credits.get("min")
        kuvaus_osat = []
        for kentta in ("tweetText", "outcomes", "content", "prerequisites", "additional"):
            teksti = _riisu_html(_fi(data.get(kentta)))
            if teksti:
                kuvaus_osat.append(teksti)
        return {
            "lahde_id": data.get("id"),
            "koodi": data.get("code"),
            "kurssi_nimi": _fi(data.get("name"))[:255],
            "taso": _muunna_taso(data.get("studyLevel")),
            "oppiaine": (organisaatiot.get(org_id) or "")[:500],
            "opintopisteet": str(op) if op is not None else None,
            "ops_kuvaus_teksti": "\n\n".join(kuvaus_osat),
        }
