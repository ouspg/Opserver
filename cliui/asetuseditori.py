"""Jaettu .env-asetusten muokkain LLM-luokittelun ja -arvioinnin valikoille."""
import os
from llm import asetukset
from cliui.apurit import piirra_otsikko, nayta_viesti, valitse_listasta, lue_teksti


def _nykyinen(maaritys: dict) -> str:
    return os.environ.get(maaritys["avain"], str(maaritys["oletus"]))


def muokkaa_asetuksia(stdscr, otsikko: str, maaritykset: list[dict]) -> None:
    """Selaa ja muokkaa .env-arvoja. Kukin määritys: {avain, kuvaus, tyyppi('int'/'float'), oletus}."""
    while True:
        rivit = [f"{m['kuvaus']}: {_nykyinen(m)}   [{m['avain']}]" for m in maaritykset]
        rivit.append("Takaisin")
        valinta = valitse_listasta(stdscr, otsikko, rivit)
        if valinta is None or valinta == len(maaritykset):
            return

        m = maaritykset[valinta]
        piirra_otsikko(stdscr, otsikko)
        uusi = lue_teksti(stdscr, f"{m['kuvaus']} ({m['tyyppi']})", 3, _nykyinen(m)).strip()
        try:
            int(uusi) if m["tyyppi"] == "int" else float(uusi)
        except ValueError:
            nayta_viesti(stdscr, f"Kelvoton {m['tyyppi']}-arvo: {uusi!r}")
            continue
        asetukset.aseta_arvo(m["avain"], uusi)
        nayta_viesti(stdscr, f"Asetettu {m['avain']} = {uusi}")


# Jaetut LLM-kutsun asetukset (näkyvät molemmissa valikoissa)
_JAETUT = [
    {"avain": "LLM_MAX_TOKENIT", "kuvaus": "Max output -tokenit", "tyyppi": "int", "oletus": 4096},
    {"avain": "LLM_TAHDISTUS_FREE_S", "kuvaus": "Tahdistusväli, free-malli (s)", "tyyppi": "float", "oletus": 3.5},
    {"avain": "LLM_TAHDISTUS_MAKSU_S", "kuvaus": "Tahdistusväli, maksullinen malli (s)", "tyyppi": "float", "oletus": 0.5},
]

LUOKITTELU_ASETUKSET = [
    {"avain": "LUOKITTELU_ERAKOKO", "kuvaus": "Eräkoko (kursseja per LLM-kutsu)", "tyyppi": "int", "oletus": 20},
    {"avain": "LLM_RINNAKKAISUUS", "kuvaus": "Rinnakkaisia LLM-kutsuja", "tyyppi": "int", "oletus": 5},
    *_JAETUT,
]

ARVIOINTI_ASETUKSET = [
    {"avain": "ARVIOINTI_ERAKOKO", "kuvaus": "Eräkoko (kursseja per LLM-kutsu)", "tyyppi": "int", "oletus": 5},
    *_JAETUT,
]
