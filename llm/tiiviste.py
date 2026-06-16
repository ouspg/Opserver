"""Kehotetiivisteet: tunnistavat millä kehotteella/kysymyksellä LLM-tulos syntyi.

Tiivisteen avulla ajossa voidaan ohittaa tulokset joiden kehote ei ole muuttunut
ja ajaa uudelleen vain muuttuneet — välttäen turhia (maksullisia) LLM-kutsuja.
"""
import hashlib
import json


def laske(*osat: str) -> str:
    """SHA-256-tiiviste annetuista tekstiosista (järjestyksellä on merkitystä)."""
    h = hashlib.sha256()
    for osa in osat:
        h.update((osa or "").encode("utf-8"))
        h.update(b"\x00")  # erotin, ettei osien raja hämärry
    return h.hexdigest()


def luokittelu(luokittelukehote: str, jarjestelma: str) -> str:
    """Luokittelutuloksen tiiviste: muuttuu kun luokittelukehote tai järjestelmäkehote muuttuu."""
    return laske(luokittelukehote, jarjestelma)


def _kysymys_kanoninen(kysymys: dict) -> str:
    """Kysymyksen vakaa esitys: teksti + tyyppi + määrittely, avaimet järjestettyinä."""
    return json.dumps(
        {
            "kysymys": kysymys.get("Kysymys") or "",
            "luokittelu": kysymys.get("Luokittelu") or "vapaa_teksti",
            "maarittely": kysymys.get("LuokitteluMaarittely"),
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def kysymys(arviointikehote: str, jarjestelma: str, kysymys_data: dict) -> str:
    """Arviointivastauksen tiiviste: muuttuu kun arviointikehote, järjestelmäkehote
    tai kyseinen kysymys muuttuu — mahdollistaa vain muuttuneen kysymyksen uudelleenajon."""
    return laske(arviointikehote, jarjestelma, _kysymys_kanoninen(kysymys_data))


def kysymystiivisteet(arviointikehote: str, jarjestelma: str, kysymykset: list[dict]) -> dict:
    """{KysID: nykyinen tiiviste} annetuille kysymyksille. Jaettu pipeline + WebUI."""
    return {k["KysID"]: kysymys(arviointikehote, jarjestelma, k) for k in kysymykset}
