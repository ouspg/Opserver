"""Tutkimuksen kurssit ja luokitukset sekä HITL-A: luokituksen korjaus ja hyväksyntä."""
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

from tietokanta import mallit
from webui.riippuvuudet import HyvaksyntaPyynto, TutkimusSlugista, _tarkista_juurisyy, _vaadi_nimi


reititin = APIRouter()


@reititin.get("/api/tutkimukset/{slug}/kurssit")
def api_tutkimus_kurssit(tutkimus: TutkimusSlugista) -> list[dict]:
    return mallit.hae_valitut_kurssit(tutkimus["TID"], kuvaukset=False)


@reititin.get("/api/tutkimukset/{slug}/luokitukset/maarat")
def api_tutkimus_luokitukset_maarat(tutkimus: TutkimusSlugista, kkid: Optional[int] = None,
                                    taso: Optional[str] = None,
                                    hakusana: Optional[str] = None) -> dict:
    return mallit.hae_tutkimuksen_tilamaarat(tutkimus["TID"], kkid=kkid, taso=taso, hakusana=hakusana)


@reititin.get("/api/tutkimukset/{slug}/luokitukset")
def api_tutkimus_luokitukset(tutkimus: TutkimusSlugista, tila: Optional[str] = None,
                             sivu: int = 0, koko: int = 200,
                             kkid: Optional[int] = None, taso: Optional[str] = None,
                             hakusana: Optional[str] = None,
                             jarjesta: Optional[str] = None,
                             suunta: Optional[str] = None) -> list[dict]:
    tid = tutkimus["TID"]
    rivit = mallit.hae_kurssit_luokituksilla(tid, tila=tila, sivu=sivu, koko=koko,
                                             kkid=kkid, taso=taso, hakusana=hakusana,
                                             jarjesta=jarjesta, suunta=suunta)

    # Ryhmittele HITL-historia kursseittain (vanhimmasta uusimpaan)
    historia: dict[int, list[dict]] = {}
    for h in mallit.hae_hitl_historia(tid, [r["KID"] for r in rivit]):
        kid = h["KID"]
        if kid not in historia:
            historia[kid] = []
        historia[kid].append({
            "UusiTila": bool(h["UusiTila"]),
            "Perustelu": h["Perustelu"],
            "KayttajaNimi": h["KayttajaNimi"],
        })

    for d in rivit:
        kid = d["KID"]
        korjaukset = historia.get(kid, [])
        d["HitlKorjaukset"] = korjaukset
        # Tekoälyn alkuperäinen tila: ensimmäisen korjauksen käänteinen
        d["AiMukana"] = (not korjaukset[0]["UusiTila"]) if korjaukset else d.get("Mukana")
    return rivit


class HitlPyynto(BaseModel):
    uusi_tila: bool
    perustelu: str
    nimi: str
    sahkoposti: str
    juurisyy: str | None = None


@reititin.post("/api/tutkimukset/{slug}/kurssit/{kid}/hitl")
def api_hitl_korjaus(tutkimus: TutkimusSlugista, kid: int, pyynto: HitlPyynto) -> dict:
    _tarkista_juurisyy(pyynto.juurisyy)
    mallit.tallenna_hitl_korjaus(
        tutkimus["TID"], kid, pyynto.uusi_tila,
        pyynto.perustelu, pyynto.nimi, pyynto.sahkoposti, pyynto.juurisyy,
    )
    return {"ok": True}


@reititin.post("/api/tutkimukset/{slug}/kurssit/{kid}/hyvaksy")
def api_hyvaksy_luokitus(tutkimus: TutkimusSlugista, kid: int, pyynto: HyvaksyntaPyynto) -> dict:
    """Peukutus: LLM:n mukaan ottama kurssi merkitään ihmisen hyväksymäksi."""
    mallit.hyvaksy_luokitus(tutkimus["TID"], kid, _vaadi_nimi(pyynto.nimi), pyynto.sahkoposti.strip())
    return {"ok": True}
