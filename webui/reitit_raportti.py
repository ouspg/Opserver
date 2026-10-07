"""Raportti: osiot, tilastot ja tuoreus (raskas tuoreuslaskenta taustasäikeessä)."""
import os
import threading
from datetime import datetime
from fastapi import APIRouter, HTTPException

from tietokanta import mallit
from tietokanta.valimuisti import ttl_valimuisti
from raportti import llmraportti, mittarit
from arviointi.luokat import kanoninen_luokka
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
    kysymykset = mallit.hae_kysymykset(tid)
    vastaukset_lista = mallit.hae_vastaukset(tid, vain_mukana=True)

    # Rakenna per-kysymys indeksi vastauksista. hae_vastaukset palauttaa saman
    # (kurssi, kysymys) -parin HITL-rivin ennen LLM-riviä → ensimmäinen voittaa,
    # eikä ihmisen korjaama pari tule tilastoon kahdesti.
    v_per_kys: dict[int, list[dict]] = {k["KysID"]: [] for k in kysymykset}
    nahdyt: set[tuple[int, int]] = set()
    for v in vastaukset_lista:
        kysid = v["KysID"]
        if kysid in v_per_kys and (v["KID"], kysid) not in nahdyt:
            nahdyt.add((v["KID"], kysid))
            v_per_kys[kysid].append(v)

    tulos_kysymykset = []
    for k in kysymykset:
        kysid = k["KysID"]
        luokittelu = k.get("Luokittelu", "vapaa_teksti")
        vastaukset = v_per_kys.get(kysid, [])
        kohta: dict = {"kysid": kysid, "kysymys": k["Kysymys"], "luokittelu": luokittelu}

        if luokittelu == "luokittelu":
            jakauma: dict[str, int] = {}
            for v in vastaukset:
                luokka = kanoninen_luokka(k, v.get("Luokka") or "")
                if luokka:
                    jakauma[luokka] = jakauma.get(luokka, 0) + 1
            kohta["jakauma"] = jakauma
            kohta["yhteensa"] = sum(jakauma.values())

        elif luokittelu == "asteikko":
            pisteet_arvot = [v["Pisteet"] for v in vastaukset if v.get("Pisteet") is not None]
            jakauma_num: dict[str, int] = {}
            for p in pisteet_arvot:
                avain = str(int(round(p)))
                jakauma_num[avain] = jakauma_num.get(avain, 0) + 1
            kohta["yhteensa"] = len(pisteet_arvot)
            kohta["jakauma"] = jakauma_num
            if pisteet_arvot:
                kohta["keskiarvo"] = round(sum(pisteet_arvot) / len(pisteet_arvot), 2)
                kohta["minimi"] = min(pisteet_arvot)
                kohta["maksimi"] = max(pisteet_arvot)
            else:
                kohta["keskiarvo"] = None
                kohta["minimi"] = None
                kohta["maksimi"] = None

        elif luokittelu == "lista":
            jakauma_lista: dict[str, int] = {}
            vastattuja = 0
            for v in vastaukset:
                kohdat = v.get("Lista") or []
                if kohdat:
                    vastattuja += 1
                for kohde in kohdat:
                    jakauma_lista[kohde] = jakauma_lista.get(kohde, 0) + 1
            kohta["jakauma"] = dict(sorted(jakauma_lista.items(), key=lambda p: -p[1]))
            kohta["yhteensa"] = vastattuja

        else:  # vapaa_teksti
            kohta["yhteensa"] = sum(1 for v in vastaukset if v.get("Vastaus"))

        tulos_kysymykset.append(kohta)

    # HITL-laatumittarit (CLAUDE.md vaihe 4): käsin-muutos-% + juurisyyjakauma.
    # Rakenteellinen, auktoritatiivinen luku — ei LLM-generoitua proosaa.
    tilastot = mallit.hae_tilastot_yliopistoittain(tid)
    return {"kysymykset": tulos_kysymykset, "hitl": mittarit.hitl_mittarit(tilastot),
            "suppilo": mittarit.suppilo(tilastot)}


@reititin.get("/api/tutkimukset/{slug}/raportti/tilanne")
def api_raportti_tilanne(slug: str) -> dict:
    """Raportin tuoreus: milloin generoitu, ajan tasalla / vanhentunut ja
    montako HITL-korjausta/kommenttia tehty generoinnin jälkeen."""
    tilanne = _raportti_tilanne_valimuistissa(slug)
    if tilanne is None:
        raise HTTPException(status_code=404, detail="Tutkimusta ei löydy")
    return tilanne
