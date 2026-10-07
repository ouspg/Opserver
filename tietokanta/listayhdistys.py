"""Lista-arvojen yhdistäminen (migraatio_026): arvojen mainintamäärät, pysyvät
yhdistämispäätökset (ListaYhdistys) ja Vastaukset.Lista-sarakkeen uudelleenkirjoitus.

Etäkanta: mainintamäärät lasketaan kannassa (JSON_TABLE + GROUP BY) eikä listoja
vedetä verkon yli; uudelleenkirjoitus hakee vain rivit, joissa jokin lähdearvo
esiintyy (JSON_OVERLAPS), ja päivittää vain oikeasti muuttuvat rivit erissä.
JSON-merkkijonojen vertailu on binääristä (utf8mb4_bin), joten "ai" ≠ "AI"."""
import json

from tietokanta.yhteys import yhteys
from tietokanta._yhteiset import _hae_kaikki, _lisaa_rivit

_ERAKOKO = 500


def hae_lista_arvomaarat(tid: int, kysidt: list[int]) -> dict[int, dict[str, int]]:
    """{KysID: {arvo: mainintojen määrä}} tutkimuksen vastauksista (LLM + ihmiset).
    Ryhmittely binäärisellä kollaatiolla: oletus-(ai_ci) yhdistäisi "ai" ja "AI"."""
    if not kysidt:
        return {}
    paikat = ",".join(["%s"] * len(kysidt))
    rivit = _hae_kaikki(
        f"""SELECT v.KysID, j.arvo, COUNT(*) AS lkm
            FROM Vastaukset v,
                 JSON_TABLE(v.Lista, '$[*]' COLUMNS (
                     arvo VARCHAR(1000) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin PATH '$')) j
            WHERE v.TID = %s AND v.KysID IN ({paikat}) AND v.Lista IS NOT NULL
              AND j.arvo IS NOT NULL
            GROUP BY v.KysID, j.arvo""",
        (tid, *kysidt),
    )
    tulos: dict[int, dict[str, int]] = {}
    for r in rivit:
        tulos.setdefault(r["KysID"], {})[r["arvo"]] = int(r["lkm"])
    return tulos


def hae_lista_paatokset(tid: int) -> list[dict]:
    """Tallennetut päätökset. Hyväksyttyjä on enintään yksi per (KysID, Lahde)
    (paivita_listat korvaa vanhan), joten järjestys on vain vakaa esitys."""
    return _hae_kaikki(
        """SELECT KysID, Lahde, Kohde, Hyvaksytty FROM ListaYhdistys
           WHERE TID = %s ORDER BY KysID, Lahde, Kohde""",
        (tid,),
    )


def hae_llm_kasitellyt(tid: int) -> dict[int, str]:
    """{KysID: arvojoukon tiiviste}, jonka LLM on jo käsitellyt ja käyttäjä kuitannut."""
    return {r["KysID"]: r["Tiiviste"] for r in _hae_kaikki(
        "SELECT KysID, Tiiviste FROM ListaLlmKasitelty WHERE TID = %s", (tid,))}


def _muuttuvat_rivit(kursori, tid: int, kuvaukset: dict[int, dict[str, str]], muunna) -> list[tuple]:
    """(VasID, uusi lista) riveille, joissa jokin lähdearvo esiintyy ja lista muuttuu."""
    ehdot, params = [], [tid]
    for kysid, kuvaus in kuvaukset.items():
        ehdot.append("(KysID = %s AND JSON_OVERLAPS(Lista, CAST(%s AS JSON)))")
        params += [kysid, json.dumps(sorted(kuvaus), ensure_ascii=False)]
    kursori.execute(
        f"""SELECT VasID, KysID, Lista FROM Vastaukset
            WHERE TID = %s AND Lista IS NOT NULL AND ({' OR '.join(ehdot)})
            FOR UPDATE""",
        params,
    )
    muuttuvat = []
    for vasid, kysid, lista in kursori.fetchall():
        vanha = json.loads(lista) if isinstance(lista, (str, bytes)) else lista
        if not isinstance(vanha, list):
            continue
        uusi = muunna(vanha, kuvaukset[kysid])
        if uusi != vanha:
            muuttuvat.append((vasid, uusi))
    return muuttuvat


def paivita_listat(tid: int, kuvaukset: dict[int, dict[str, str]], muunna,
                   paatokset: list[tuple], kasitellyt: dict[int, str]) -> int:
    """Yksi transaktio: kirjoittaa Vastaukset.Listan uudelleen (kuvaukset, muunna(lista,
    kuvaus) → uusi lista), tallentaa päätökset (KysID, Lahde, Kohde, Hyvaksytty) ja
    LLM:n käsittelemien arvojoukkojen tiivisteet. Palauttaa muuttuneiden rivien määrän.

    Aikaleima ja Kehotetiiviste eivät muutu: normalisointi ei ole uusi vastaus eikä
    saa käynnistää uudelleenarviointia. Idempotentti (toinen ajo ei löydä muutettavaa)."""
    kuvaukset = {k: v for k, v in kuvaukset.items() if v}
    with yhteys() as yht:
        with yht.cursor() as kursori:
            muuttuvat = _muuttuvat_rivit(kursori, tid, kuvaukset, muunna) if kuvaukset else []
            for i in range(0, len(muuttuvat), _ERAKOKO):
                osa = muuttuvat[i:i + _ERAKOKO]
                tapaukset = " ".join(["WHEN %s THEN CAST(%s AS JSON)"] * len(osa))
                params = [x for vasid, uusi in osa for x in (vasid, json.dumps(uusi, ensure_ascii=False))]
                params += [vasid for vasid, _ in osa]
                kursori.execute(
                    f"""UPDATE Vastaukset SET Lista = CASE VasID {tapaukset} END
                        WHERE VasID IN ({','.join(['%s'] * len(osa))})""",
                    params,
                )
            hyvaksytyt = [(kysid, lahde) for kysid, lahde, _, hyv in paatokset if hyv]
            if hyvaksytyt:
                # Yksi hyväksytty kohde per lähde: uusi hyväksyntä korvaa vanhan.
                kursori.execute(
                    f"""DELETE FROM ListaYhdistys WHERE TID = %s AND Hyvaksytty = 1
                        AND (KysID, Lahde) IN ({','.join(['(%s, %s)'] * len(hyvaksytyt))})""",
                    [tid, *[x for pari in hyvaksytyt for x in pari]],
                )
            _lisaa_rivit(
                kursori, "INSERT INTO ListaYhdistys (TID, KysID, Lahde, Kohde, Hyvaksytty)",
                [(tid, kysid, lahde, kohde, int(hyv)) for kysid, lahde, kohde, hyv in paatokset],
                "ON DUPLICATE KEY UPDATE Hyvaksytty = VALUES(Hyvaksytty), Aikaleima = CURRENT_TIMESTAMP",
            )
            _lisaa_rivit(
                kursori, "INSERT INTO ListaLlmKasitelty (TID, KysID, Tiiviste)",
                [(tid, kysid, t) for kysid, t in kasitellyt.items()],
                "ON DUPLICATE KEY UPDATE Tiiviste = VALUES(Tiiviste), Aikaleima = CURRENT_TIMESTAMP",
            )
    return len(muuttuvat)
