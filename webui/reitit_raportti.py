"""Raportti: osiot, tilastot ja tuoreus (raskas tuoreuslaskenta taustasäikeessä)."""
import os
import threading
from datetime import datetime
from fastapi import APIRouter, HTTPException

from tietokanta import mallit
from tietokanta.valimuisti import ttl_valimuisti
from raportti import kysymystilastot, llmraportti, mittarit
from webui.riippuvuudet import TutkimusSlugista
from webui.reitit_katalogi import _VALIMUISTI_TTL


reititin = APIRouter()


# Raskas tuoreuslaskenta (raporttitiiviste) ajetaan taustalla — ei estä pollausta.
# Rajoitetaan uudelleenlaskenta korkeintaan yhteen per tutkimus kerrallaan JA
# harvennetaan aikavälillä, ettei jatkuva 15 s pollaus laukaise laskentaa alati.
_TUOREUS_PAIVITYS_VALI = float(os.environ.get("WEBUI_TUOREUS_VALI_S", "300"))
_tuoreus_lukko = threading.Lock()
_tuoreus_kaynnissa: set[int] = set()


def _kaynnista_taustatuoreus(tutkimus: dict) -> None:
    """Käynnistää raportin tuoreuslaskennan taustasäikeessä, jos tallennettu tuoreus
    puuttuu tai on vanhempi kuin _TUOREUS_PAIVITYS_VALI. Ei blokkaa pyyntöä; tulos
    näkyy seuraavalla pollauksella (tilanne näyttää 'tarkistettu'-aikaleiman)."""
    tid = tutkimus["TID"]
    tuoreus = mallit.hae_raportti_tuoreus(tid)
    tarkistettu = tuoreus.get("Tarkistettu") if tuoreus else None
    if tarkistettu and (datetime.now() - tarkistettu).total_seconds() < _TUOREUS_PAIVITYS_VALI:
        return
    with _tuoreus_lukko:
        if tid in _tuoreus_kaynnissa:
            return
        _tuoreus_kaynnissa.add(tid)

    def aja():
        try:
            llmraportti.paivita_tuoreus(tutkimus)
        except Exception:
            pass  # parhaan yrityksen mukaan; pollaus ei riipu taustapäivityksestä
        finally:
            with _tuoreus_lukko:
                _tuoreus_kaynnissa.discard(tid)

    threading.Thread(target=aja, daemon=True).start()


@ttl_valimuisti(_VALIMUISTI_TTL)
def _raportti_tilanne_valimuistissa(slug: str):
    """Raportin tuoreus (koosta_tilanne) — KEVYT: lukee viimeksi lasketun
    tuoreustuloksen tallennettuna (raskas tiivistelaskenta ajetaan taustalla).
    Välimuistitettu, koska WebUI:n raporttinäkymä päivittyy 15 s välein.
    Välimuistin ohittuessa (≤ TTL) laukaistaan taustatuoreuden päivitys (harvennettu
    _TUOREUS_PAIVITYS_VALI:llä). None jos tutkimusta ei ole."""
    tutkimus = mallit.hae_tutkimus_slugilla(slug)
    if tutkimus is None:
        return None
    tilanne = llmraportti.koosta_tilanne(tutkimus)
    if tilanne.get("generoitu"):
        _kaynnista_taustatuoreus(tutkimus)
    return tilanne


@reititin.get("/api/tutkimukset/{slug}/raportti")
def api_raportti(tutkimus: TutkimusSlugista) -> dict:
    osiot = mallit.hae_raportti_osiot(tutkimus["TID"])
    return {"tid": tutkimus["TID"], "osiot": osiot}


@reititin.get("/api/tutkimukset/{slug}/raportti/tilastot")
def api_raportti_tilastot(tutkimus: TutkimusSlugista) -> dict:
    """Palauttaa per-kysymys-tilastot rakenteellisille arvioinneille ilman LLM-kutsua.
    Vain nykyiset mukana-kurssit (sama joukko kuin raportin "lopullinen mukana-lista")."""
    tid = tutkimus["TID"]
    # HITL-laatumittarit (CLAUDE.md vaihe 4): käsin-muutos-% + juurisyyjakauma.
    # Rakenteellinen, auktoritatiivinen luku — ei LLM-generoitua proosaa.
    tilastot = mallit.hae_tilastot_yliopistoittain(tid)
    return {"kysymykset": kysymystilastot.hae(tid), "hitl": mittarit.hitl_mittarit(tilastot),
            "suppilo": mittarit.suppilo(tilastot)}


@reititin.get("/api/tutkimukset/{slug}/raportti/tilanne")
def api_raportti_tilanne(slug: str) -> dict:
    """Raportin tuoreus: milloin generoitu, ajan tasalla / vanhentunut ja
    montako HITL-korjausta/kommenttia tehty generoinnin jälkeen."""
    tilanne = _raportti_tilanne_valimuistissa(slug)
    if tilanne is None:
        raise HTTPException(status_code=404, detail="Tutkimusta ei löydy")
    return tilanne
