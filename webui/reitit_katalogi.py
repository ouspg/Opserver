"""Kurssikatalogin ja tutkimusten reitit (staattinen referenssidata TTL-välimuistissa)."""
import os
from typing import Optional
from fastapi import APIRouter, HTTPException

from tietokanta import mallit
from tietokanta.valimuisti import ttl_valimuisti
from webui.riippuvuudet import TutkimusSlugista


reititin = APIRouter()


# --- Staattisten referenssikyselyjen TTL-välimuisti ---
# Vain demon aikana muuttumaton data (kurssikatalogi, korkeakoulut, lukuvuodet,
# tasot). EI annotointiriippuvaista dataa (luokitukset/arvioinnit) — ne pidetään
# tuoreina reaaliaikaista yhteisöllistä annotointia varten.
_VALIMUISTI_TTL = float(os.environ.get("WEBUI_VALIMUISTI_TTL", "60"))


@ttl_valimuisti(_VALIMUISTI_TTL)
def _korkeakoulut_valimuistissa() -> list[dict]:
    koulut = mallit.hae_korkeakoulut()
    maarat = mallit.hae_kurssimaarat_kouluittain()
    for k in koulut:
        k["KurssitKausittain"] = maarat.get(k["KKID"], [])
    return koulut


@ttl_valimuisti(_VALIMUISTI_TTL)
def _lukuvuodet_valimuistissa() -> list[str]:
    return mallit.hae_lukuvuodet()


@ttl_valimuisti(_VALIMUISTI_TTL)
def _tasot_valimuistissa(kkid, lukuvuosi) -> list[str]:
    return mallit.hae_tasot(kkid=kkid, lukuvuosi=lukuvuosi)


@ttl_valimuisti(_VALIMUISTI_TTL)
def _kurssit_valimuistissa(kkid, lukuvuosi) -> list[dict]:
    return mallit.hae_kurssit(kkid=kkid, lukuvuosi=lukuvuosi)


@reititin.get("/api/korkeakoulut")
def api_korkeakoulut() -> list[dict]:
    return _korkeakoulut_valimuistissa()


@reititin.get("/api/lukuvuodet")
def api_lukuvuodet() -> list[str]:
    return _lukuvuodet_valimuistissa()


@reititin.get("/api/tasot")
def api_tasot(kkid: Optional[int] = None, lukuvuosi: Optional[str] = None) -> list[str]:
    return _tasot_valimuistissa(kkid, lukuvuosi)


@reititin.get("/api/kurssit")
def api_kurssit(kkid: Optional[int] = None, lukuvuosi: Optional[str] = None,
                alku: int = 0, koko: Optional[int] = None) -> list[dict]:
    """koko annettu → vain rivit alku..alku+koko (WebUI lataa osissa; lyhyt osa = viimeinen)."""
    rivit = _kurssit_valimuistissa(kkid, lukuvuosi)
    return rivit if koko is None else rivit[alku:alku + koko]


@reititin.get("/api/kurssit/{kid}")
def api_kurssi(kid: int) -> dict:
    kurssi = mallit.hae_kurssi(kid)
    if kurssi is None:
        raise HTTPException(status_code=404, detail="Kurssia ei löydy")
    return kurssi


@reititin.get("/api/tutkimukset")
def api_tutkimukset() -> list[dict]:
    return mallit.hae_tutkimukset_yhteenvedolla()


@reititin.get("/api/tutkimukset/{slug}")
def api_tutkimus(tutkimus: TutkimusSlugista) -> dict:
    tutkimus["Kysymykset"] = mallit.hae_kysymykset(tutkimus["TID"])
    return tutkimus
