"""Reittien yhteiset riippuvuudet ja validoinnit: slug → tutkimus, nimi, juurisyy."""
from typing import Annotated
from fastapi import Depends, HTTPException
from pydantic import BaseModel

from tietokanta import mallit


def _tutkimus_slugista(slug: str) -> dict:
    """Polun {slug} → tutkimusrivi, tai 404."""
    tutkimus = mallit.hae_tutkimus_slugilla(slug)
    if tutkimus is None:
        raise HTTPException(status_code=404, detail="Tutkimusta ei löydy")
    return tutkimus


TutkimusSlugista = Annotated[dict, Depends(_tutkimus_slugista)]


def _vaadi_nimi(nimi: str) -> str:
    """Korjauksen/hyväksynnän tekijä on pakollinen (400, ei pydanticin 422)."""
    if not nimi.strip():
        raise HTTPException(status_code=400, detail="Nimi puuttuu")
    return nimi.strip()


def _tarkista_juurisyy(juurisyy: str | None) -> None:
    if juurisyy is not None and juurisyy not in mallit.JUURISYYT:
        raise HTTPException(status_code=400, detail="Tuntematon juurisyy")


class HyvaksyntaPyynto(BaseModel):
    nimi: str
    sahkoposti: str = ""
