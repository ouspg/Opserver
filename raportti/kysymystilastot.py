"""Arviointikysymysten vastausjakaumat — jaettu tilastorajapinnan (WebUI) ja raportin
arvioinnit-osion kehotteen kesken, jotta molemmat näyttävät samat luvut.

Joukko = nykyiset mukana-kurssit (hae_vastaukset(vain_mukana=True)). Lisäksi lasketaan
"ei pääteltävissä" -vastaukset (luokka, jonka nimi tai kuvaus kertoo, ettei opinto-
oppaasta voi päätellä; listassa pelkkä "-") opinto-oppaiden riittämättömyyden mittariksi."""
import re

from arviointi.luokat import kanoninen_luokka
from tietokanta import mallit

# Luokan nimi tai kuvaus, joka tarkoittaa "opinto-oppaasta ei voi päätellä" (esim.
# "ei voi päätellä", "Ei pysty määrittelemään", "EOS", "hankala arvioida").
_EI_PAATELTAVISSA = re.compile(
    r"\b(eos|ei\s+(voi|voida|pysty)\w*|hankala\s+(sanoa|arvioida)|ei\s+pääteltävissä|ei\s+tietoa)\b",
    re.IGNORECASE)
_LISTA_EI_TIETOA = {"", "-", "–", "—"}


def ei_paateltavissa_luokat(kysymys: dict) -> list[str]:
    """Luokittelukysymyksen "ei pääteltävissä" -luokat: nimi tai kuvaus täsmää."""
    luokat = (kysymys.get("LuokitteluMaarittely") or {}).get("luokat", [])
    return [l["nimi"] for l in luokat if isinstance(l, dict) and l.get("nimi")
            and _EI_PAATELTAVISSA.search(f"{l['nimi']} {l.get('kuvaus') or ''}")]


def _vastaukset_kysymyksittain(kysymykset: list[dict], vastaukset: list[dict]) -> dict[int, list[dict]]:
    """hae_vastaukset palauttaa saman (kurssi, kysymys) -parin HITL-rivin ennen LLM-riviä
    → ensimmäinen voittaa, eikä ihmisen korjaama pari tule tilastoon kahdesti."""
    tulos: dict[int, list[dict]] = {k["KysID"]: [] for k in kysymykset}
    nahdyt: set[tuple[int, int]] = set()
    for v in vastaukset:
        kysid = v["KysID"]
        if kysid in tulos and (v["KID"], kysid) not in nahdyt:
            nahdyt.add((v["KID"], kysid))
            tulos[kysid].append(v)
    return tulos


def _laske_kysymys(k: dict, vastaukset: list[dict]) -> dict:
    luokittelu = k.get("Luokittelu", "vapaa_teksti")
    kohta: dict = {"kysid": k["KysID"], "kysymys": k["Kysymys"], "luokittelu": luokittelu}
    if luokittelu == "luokittelu":
        jakauma: dict[str, int] = {}
        for v in vastaukset:
            luokka = kanoninen_luokka(k, v.get("Luokka") or "")
            if luokka:
                jakauma[luokka] = jakauma.get(luokka, 0) + 1
        kohta["jakauma"] = jakauma
        kohta["yhteensa"] = sum(jakauma.values())
        kohta["ei_paateltavissa_luokat"] = ei_paateltavissa_luokat(k)
        kohta["ei_paateltavissa"] = sum(jakauma.get(l, 0) for l in kohta["ei_paateltavissa_luokat"])
    elif luokittelu == "asteikko":
        pisteet = [v["Pisteet"] for v in vastaukset if v.get("Pisteet") is not None]
        jakauma_num: dict[str, int] = {}
        for p in pisteet:
            avain = str(int(round(p)))
            jakauma_num[avain] = jakauma_num.get(avain, 0) + 1
        kohta["yhteensa"] = len(pisteet)
        kohta["jakauma"] = jakauma_num
        kohta["keskiarvo"] = round(sum(pisteet) / len(pisteet), 2) if pisteet else None
        kohta["minimi"] = min(pisteet) if pisteet else None
        kohta["maksimi"] = max(pisteet) if pisteet else None
    elif luokittelu == "lista":
        jakauma_lista: dict[str, int] = {}
        vastattuja = ei_tietoa = 0
        for v in vastaukset:
            kohdat = v.get("Lista") or []
            if kohdat:
                vastattuja += 1
                ei_tietoa += all(str(x).strip() in _LISTA_EI_TIETOA for x in kohdat)
            for kohde in kohdat:
                jakauma_lista[kohde] = jakauma_lista.get(kohde, 0) + 1
        kohta["jakauma"] = dict(sorted(jakauma_lista.items(), key=lambda p: -p[1]))
        kohta["yhteensa"] = vastattuja
        kohta["ei_paateltavissa"] = ei_tietoa
    else:  # vapaa_teksti
        kohta["yhteensa"] = sum(1 for v in vastaukset if v.get("Vastaus"))
    return kohta


def laske(kysymykset: list[dict], vastaukset: list[dict]) -> list[dict]:
    """Per-kysymys-tilastot (jakauma, yhteensä, asteikolle ka/min/max, ei pääteltävissä)."""
    per_kys = _vastaukset_kysymyksittain(kysymykset, vastaukset)
    return [_laske_kysymys(k, per_kys.get(k["KysID"], [])) for k in kysymykset]


def hae(tid: int, kysymykset: list[dict] | None = None) -> list[dict]:
    """Tutkimuksen kysymystilastot nykyisistä mukana-kursseista (kaksi kyselyä)."""
    if kysymykset is None:
        kysymykset = mallit.hae_kysymykset(tid)
    return laske(kysymykset, mallit.hae_vastaukset(tid, vain_mukana=True))


def _pros(osa: int, koko: int) -> str:
    return f"{100 * osa / koko:.1f} %" if koko else "0.0 %"


def kehoteteksti(tilastot: list[dict], top_n: int = 10) -> str:
    """Jakaumat prosentteina raportin arvioinnit-osion kehotteeseen. Lista-kysymyksestä
    vain top_n yleisintä + "muita X eri arvoa" (luvut ovat mainintoja)."""
    lohkot = []
    for i, t in enumerate(tilastot, 1):
        n = t.get("yhteensa", 0)
        rivit = [f"K{i} ({t['luokittelu']}): {t['kysymys']}", f"  Vastanneita kursseja: {n}"]
        if t["luokittelu"] == "luokittelu":
            rivit += [f"  - {luokka}: {lkm} ({_pros(lkm, n)})" for luokka, lkm in t["jakauma"].items()]
        elif t["luokittelu"] == "asteikko":
            rivit.append(f"  Keskiarvo {t['keskiarvo']}, vaihteluväli {t['minimi']}–{t['maksimi']}")
            rivit += [f"  - {arvo}: {t['jakauma'][arvo]} ({_pros(t['jakauma'][arvo], n)})"
                      for arvo in sorted(t["jakauma"], key=int)]
        elif t["luokittelu"] == "lista":
            parit = list(t["jakauma"].items())
            rivit.append("  Luvut ovat mainintoja: yksi kurssi voi mainita useita kohtia, "
                         "joten osuudet eivät summaudu 100 %:iin.")
            rivit += [f"  - {kohde}: {lkm} mainintaa ({_pros(lkm, n)} kursseista)"
                      for kohde, lkm in parit[:top_n]]
            if len(parit) > top_n:
                rivit.append(f"  - muita {len(parit) - top_n} eri arvoa "
                             f"({sum(l for _, l in parit[top_n:])} mainintaa)")
        if "ei_paateltavissa" in t:
            nimet = ", ".join(f'"{l}"' for l in t.get("ei_paateltavissa_luokat", [])) or '"-"'
            rivit.append(f"  Ei pääteltävissä opinto-oppaasta ({nimet}): "
                         f"{t['ei_paateltavissa']} ({_pros(t['ei_paateltavissa'], n)})")
        lohkot.append("\n".join(rivit))
    return "\n\n".join(lohkot) or "(ei arviointikysymyksiä)"
