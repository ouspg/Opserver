"""Arvioinnit ja HITL-B: arviointivastauksen hyväksyntä ja korjaus."""
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from tietokanta import mallit
from llm import tiiviste, kehotteet
from webui.riippuvuudet import HyvaksyntaPyynto, TutkimusSlugista, _tarkista_juurisyy, _vaadi_nimi


reititin = APIRouter()


@reititin.get("/api/tutkimukset/{slug}/arvioinnit")
def api_tutkimus_arvioinnit(tutkimus: TutkimusSlugista, sivu: int = 0, koko: Optional[int] = None) -> dict:
    """koko annettu → vain sivun kurssit (WebUI lataa osissa) + yhteensa kaikista."""
    tid = tutkimus["TID"]
    kysymykset = mallit.hae_kysymykset(tid)
    if koko is None:
        kurssit = mallit.hae_valitut_kurssit(tid, kuvaukset=False)
        yhteensa = len(kurssit)
    else:
        kurssit = mallit.hae_valitut_kurssit(tid, raja=koko, siirto=sivu * koko, kuvaukset=False)
        yhteensa = mallit.laske_valitut_kurssit(tid)
    # ponytail: vastaukset haetaan koko tutkimukselle joka sivulla (~1600 lyhyttä riviä,
    # ms-luokkaa); rajaa KID-listalla jos vastausmäärä kasvaa kertaluokkia.
    vastaukset_lista = mallit.hae_vastaukset(tid)   # LLM- ja ihmisen rivit samassa haussa

    # Nykyiset kysymystiivisteet: tunnistavat vastaukset jotka on generoitu
    # vanhentuneeseen kysymykseen/kehotteeseen (ennen seuraavaa LLM-ajoa).
    jarjestelma = kehotteet.lue("arviointijarjestelma.txt")
    nyky_tiiviste = tiiviste.kysymystiivisteet(
        tutkimus.get("Arviointikehote") or "", jarjestelma, kysymykset
    )

    vastaus_kartta: dict[int, dict[int, dict]] = {}
    hitl_lista = []
    for v in vastaukset_lista:
        if v.get("Malli") is None:
            hitl_lista.append(v)  # ihmisen korjaus → korjaus_kartta
            continue
        kid = v["KID"]
        if kid not in vastaus_kartta:
            vastaus_kartta[kid] = {}
        on_vastaus = (bool((v.get("Vastaus") or "").strip()) or v.get("Luokka") is not None
                      or v.get("Pisteet") is not None or v.get("Lista") is not None)
        vastaus_kartta[kid][v["KysID"]] = {
            "vastaus": v.get("Vastaus") or "",
            "luokka": v.get("Luokka"),
            "pisteet": v.get("Pisteet"),
            "lista": v.get("Lista"),
            "vanhentunut": on_vastaus and v.get("Kehotetiiviste") != nyky_tiiviste.get(v["KysID"]),
            "hyvaksyja": v.get("HyvaksyjaNimi"),  # ei sähköpostia: WebUI on julkinen
        }

    # Ihmisen korjaukset omaan karttaansa: WebUI näyttää korjatun arvon ja kertoo
    # kuka sen teki, mutta tekoälyn alkuperäinen vastaus jää näkyviin vertailuun.
    # hae_vastaukset järjestää ihmisen rivit uusin ensin (KID, KysID) -parin
    # sisällä → ensimmäinen osuma voittaa.
    korjaus_kartta: dict[int, dict[int, dict]] = {}
    for h in hitl_lista:
        per_kysymys = korjaus_kartta.setdefault(h["KID"], {})
        if h["KysID"] in per_kysymys:
            continue
        per_kysymys[h["KysID"]] = {
            "vastaus": h.get("Vastaus") or "",
            "luokka": h.get("Luokka"),
            "pisteet": h.get("Pisteet"),
            "lista": h.get("Lista"),
            "nimi": h.get("KayttajaNimi") or "",
            "juurisyy": h.get("Juurisyy"),
            "aikaleima": str(h.get("Aikaleima") or ""),
        }

    kys_idt = [k["KysID"] for k in kysymykset]
    tyhjä_vastaus = {"vastaus": "", "luokka": None, "pisteet": None, "lista": None,
                     "vanhentunut": False, "hyvaksyja": None}
    return {
        "yhteensa": yhteensa,
        "kysymykset": [
            {
                "KysID": k["KysID"],
                "Kysymys": k["Kysymys"],
                "Luokittelu": k.get("Luokittelu", "vapaa_teksti"),
                "LuokitteluMaarittely": k.get("LuokitteluMaarittely"),
            }
            for k in kysymykset
        ],
        "kurssit": [
            {
                "KID": k["KID"],
                "KKID": k.get("KKID"),
                "LahdeId": k.get("LahdeId") or "",
                "KurssiNimi": k["KurssiNimi"],
                "Koodi": k.get("Koodi") or "",
                "Opetusvuosi": k.get("Opetusvuosi") or "",
                "Taso": k.get("Taso") or "",
                "Oppiaine": k.get("Oppiaine") or "",
                "Opintopisteet": k.get("Opintopisteet"),
                "vastaukset": [vastaus_kartta.get(k["KID"], {}).get(kys_id, tyhjä_vastaus) for kys_id in kys_idt],
                "korjaukset": {kys_id: korjaus_kartta.get(k["KID"], {}).get(kys_id)
                               for kys_id in kys_idt},
            }
            for k in kurssit
        ],
    }


@reititin.post("/api/tutkimukset/{slug}/kurssit/{kid}/kysymykset/{kysid}/hyvaksy")
def api_hyvaksy_vastaus(tutkimus: TutkimusSlugista, kid: int, kysid: int, pyynto: HyvaksyntaPyynto) -> dict:
    """Peukutus: LLM:n arviointivastaus merkitään ihmisen hyväksymäksi."""
    mallit.hyvaksy_vastaus(tutkimus["TID"], kid, kysid, _vaadi_nimi(pyynto.nimi),
                           pyynto.sahkoposti.strip())
    return {"ok": True}


class ArvioKorjausPyynto(BaseModel):
    """Ihmisen korjaus yhteen arviointivastaukseen.

    Kysymystyyppi ratkaisee mitkä kentät ovat merkityksellisiä: luokittelu → luokka,
    asteikko → pisteet, lista → lista, vapaa teksti → pelkkä vastaus. Muut jäävät
    Noneksi, kuten LLM:n vastauksissakin.
    """
    vastaus: str = ""
    luokka: str | None = None
    pisteet: float | None = None
    lista: list[str] | None = None
    nimi: str
    sahkoposti: str
    juurisyy: str | None = None


@reititin.post("/api/tutkimukset/{slug}/kurssit/{kid}/kysymykset/{kysid}/korjaus")
def api_arvio_korjaus(tutkimus: TutkimusSlugista, kid: int, kysid: int, pyynto: ArvioKorjausPyynto) -> dict:
    _tarkista_juurisyy(pyynto.juurisyy)
    nimi = _vaadi_nimi(pyynto.nimi)
    tid = tutkimus["TID"]
    kysymykset = {k["KysID"]: k for k in mallit.hae_kysymykset(tid)}
    kysymys = kysymykset.get(kysid)
    if kysymys is None:
        raise HTTPException(status_code=404, detail="Kysymystä ei löydy tästä tutkimuksesta")
    # Tyyppitarkistus: luokka on oltava kysymyksen määrittelemien joukossa, pisteet
    # asteikon sisällä. Väärä arvo rikkoisi raporttitilastot hiljaa.
    maarittely = kysymys.get("LuokitteluMaarittely") or {}  # hae_kysymykset jäsentää JSONin
    tyyppi = kysymys.get("Luokittelu") or "vapaa_teksti"
    if tyyppi == "luokittelu" and pyynto.luokka:
        sallitut = [l.get("nimi") for l in maarittely.get("luokat", [])]
        if sallitut and pyynto.luokka not in sallitut:
            raise HTTPException(status_code=400, detail=f"Tuntematon luokka: {pyynto.luokka}")
    if tyyppi == "asteikko" and pyynto.pisteet is not None:
        minimi, maksimi = maarittely.get("minimi", 1), maarittely.get("maksimi", 5)
        if not (minimi <= pyynto.pisteet <= maksimi):
            raise HTTPException(status_code=400, detail=f"Pisteet {minimi}–{maksimi} ulkopuolella")
    mallit.tallenna_hitl_vastaus(
        tid, kid, kysid, pyynto.vastaus, nimi, pyynto.sahkoposti.strip(),
        pisteet=pyynto.pisteet, luokka=pyynto.luokka, lista=pyynto.lista,
        juurisyy=pyynto.juurisyy,
    )
    return {"ok": True}
