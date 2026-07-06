"""LLM-luokittelu: lähettää meta-suodatuksen läpäisseet kurssit LLM:lle."""
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from tietokanta import mallit
from llm import kutsu, tiiviste, kehoteet, kurssimuoto, asetukset

_OLETUS_ERAKOKO = 20  # kursseja per LLM-kutsu; .env:n LUOKITTELU_ERAKOKO ohittaa
_OLETUS_RINNAKKAISUUS = 5  # rinnakkaisia LLM-kutsuja; .env:n LLM_RINNAKKAISUUS ohittaa


def erakoko() -> int:
    """Kursseja per LLM-kutsu (.env: LUOKITTELU_ERAKOKO)."""
    return asetukset.lue_int("LUOKITTELU_ERAKOKO", _OLETUS_ERAKOKO)


def rinnakkaisuus() -> int:
    """Rinnakkaisten LLM-kutsujen määrä (.env: LLM_RINNAKKAISUUS). Vähintään 1."""
    return max(1, asetukset.lue_int("LLM_RINNAKKAISUUS", _OLETUS_RINNAKKAISUUS))


def _lue_jarjestelma_kehote() -> str:
    return kehoteet.lue("luokittelu_jarjestelma.txt")


def _erittele_json(teksti: str) -> list[dict]:
    """Erottaa JSON-taulukon LLM:n vastauksesta; sietokykyinen ylimääräisille merkeille."""
    teksti = teksti.strip()
    alku = teksti.find("[")
    loppu = teksti.rfind("]")
    if alku == -1 or loppu == -1:
        raise ValueError(f"Ei JSON-taulukkoa vastauksessa: {teksti[:200]}")
    return json.loads(teksti[alku : loppu + 1])


def _luokittele_erä(erä: list[dict], luokittelukehote: str, jarjestelma: str) -> list[dict]:
    """Lähettää yhden erän LLM:lle ja palauttaa jäsennetyn vastauksen."""
    kurssit_json = json.dumps(
        [kurssimuoto.kurssi_json_promptiin(k) for k in erä],
        ensure_ascii=False,
        indent=2,
    )
    vakaa_prefix = f"{luokittelukehote}\n\nArvioi seuraavat kurssit:\n"
    viesti = f"{vakaa_prefix}{kurssit_json}"
    vastaus = kutsu.kysy(viesti, jarjestelma, vakaa_prefix=vakaa_prefix)
    try:
        return _erittele_json(vastaus)
    except (ValueError, json.JSONDecodeError):
        # Yksi uusintayritys
        vastaus2 = kutsu.kysy(viesti + "\n\nPalauta PELKKÄ JSON-taulukko.", jarjestelma, vakaa_prefix=vakaa_prefix)
        return _erittele_json(vastaus2)


def laske_tiiviste(tutkimus: dict) -> str:
    """Nykyisen luokittelukehotteen tiiviste (kehote + järjestelmäkehote)."""
    return tiiviste.luokittelu(tutkimus["Luokittelukehote"], _lue_jarjestelma_kehote())


def aja(tutkimus: dict, edistyminen_cb=None) -> tuple[int, int, int]:
    """Luokittelee meta-suodatuksen läpäisseet kurssit LLM:llä.

    Palauttaa (mukana, hylätty, luokittelematta). Idempotentti. Ajaa passeja
    kunnes kaikki ehdokkaat on luokiteltu tai passi ei enää edisty — silloin
    loput jäävät luokittelematta (esim. erä katkeaa token-kattoon joka kerta →
    pienennä LUOKITTELU_ERAKOKO). Yksittäisen erän epäonnistuminen (katkennut/
    viallinen LLM-JSON) ei kaada ajoa: sen kurssit tulevat seuraavalla passilla.

    edistyminen_cb saa 8. argumenttina tilasto-dictin nykyisen passin
    epäonnistumisten erittelystä (menetetyt_erat, menetetyt_kurssit,
    ilman_vastausta). Jos callback palauttaa truthy-arvon, ajo keskeytyy siististi
    seuraavan valmiin erän kohdalla — jo tallennetut luokitukset säilyvät.
    """
    tid = tutkimus["TID"]
    luokittelukehote = tutkimus["Luokittelukehote"]
    jarjestelma = _lue_jarjestelma_kehote()
    tiiv = tiiviste.luokittelu(luokittelukehote, jarjestelma)

    # Tiiviste mukana → ajaa myös vanhentuneen kehotteen tulokset uudelleen,
    # mutta ei jo täsmäävän kehotteen tuloksia (säästää LLM-kuluja).
    kandidaatit = mallit.hae_luokittelemattomat(tid, tiiv)
    if not kandidaatit:
        return 0, 0, 0

    # Tyhjä valintakehote → meta-luokittelu: hyväksy kaikki meta-läpäisseet
    # kurssit suoraan ilman LLM-vaihetta. (Meta-hylätyt eivät ole ehdokkaita.)
    if not (luokittelukehote or "").strip():
        for n, k in enumerate(kandidaatit, 1):
            mallit.aseta_luokitus(tid, k["KID"], True,
                                  "Valittu meta-tietojen perusteella (ei valintakehotetta).",
                                  "", tiiviste=tiiv)
            if edistyminen_cb:
                edistyminen_cb(n, len(kandidaatit), 1, 1, n, 0, 0)  # kaikki mukaan
        return len(kandidaatit), 0, 0

    malli = kutsu.hae_malli()
    koko = erakoko()
    yhteensa = len(kandidaatit)
    mukana = 0
    hylätty = 0

    # Passi = yksi kierros yli kaikkien vielä-luokittelemattomien. Toistetaan
    # kunnes ei jää ehdokkaita tai passi ei tuottanut yhtään uutta päätöstä.
    # ponytail: kattona "ei edistystä"; systemaattisesti katkeavaa erää tämä ei
    # pelasta (sama koko → sama katkeaminen) — sen ratkaisu on pienempi eräkoko.
    keskeytetty = False
    while True:
        erat = [kandidaatit[i : i + koko] for i in range(0, len(kandidaatit), koko)]
        passin_paatokset = 0
        valmiit = 0
        # Epäonnistumisten erittely tälle passille: kokonaan menetetyt erät
        # (LLM-JSON katkesi/viallinen → koko erä ilman tulosta) vs. yksittäiset
        # kurssit, jotka LLM jätti pois muuten kelvollisesta vastauksesta.
        menetetyt_erat = 0
        menetetyt_kurssit = 0
        ilman_vastausta = 0

        # LLM-kutsut ajetaan rinnakkain (säikeissä), mutta tietokantakirjoitukset
        # tehdään pääsäikeessä erien valmistuessa — yhteyttä ei jaeta säikeiden
        # kesken. kutsu.py tahdistaa ja backoffaa säieturvallisesti yli kutsujen.
        with ThreadPoolExecutor(max_workers=rinnakkaisuus()) as suoritin:
            tulevat = {
                suoritin.submit(_luokittele_erä, erä, luokittelukehote, jarjestelma): erä
                for erä in erat
            }
            for tuleva in as_completed(tulevat):
                erä = tulevat[tuleva]
                try:
                    tulokset = tuleva.result()
                except Exception:
                    tulokset = []  # viallinen erä; kurssit jäävät seuraavalle passille
                    menetetyt_erat += 1
                    menetetyt_kurssit += len(erä)
                saadut = set()
                for tulos in tulokset:
                    kid = tulos.get("id")
                    if kid is None:
                        continue
                    saadut.add(kid)
                    on_mukana = bool(tulos.get("mukana"))
                    perustelu = tulos.get("perustelu", "")
                    mallit.aseta_luokitus(tid, kid, on_mukana, perustelu, malli, tiiviste=tiiv)
                    if on_mukana:
                        mukana += 1
                    else:
                        hylätty += 1
                    passin_paatokset += 1
                # Muuten kelvollinen erä, josta LLM jätti kursseja pois (ei menetetty erä).
                if tulokset:
                    ilman_vastausta += sum(1 for k in erä if k["KID"] not in saadut)
                valmiit += 1
                if edistyminen_cb:
                    # epäonnistunut = vielä ilman päätöstä olevat (kutistuu passeittain)
                    tilasto = {"menetetyt_erat": menetetyt_erat,
                               "menetetyt_kurssit": menetetyt_kurssit,
                               "ilman_vastausta": ilman_vastausta}
                    if edistyminen_cb(mukana + hylätty, yhteensa, valmiit, len(erat),
                                      mukana, hylätty, yhteensa - mukana - hylätty, tilasto):
                        keskeytetty = True
                if keskeytetty:
                    for t in tulevat:
                        t.cancel()  # aloittamattomat perutaan; käynnissä olevat valmistuvat, tulos hylätään
                    break

        if keskeytetty:
            break  # jo tallennetut säilyvät; loput luokitellaan seuraavalla ajolla
        if passin_paatokset == 0:
            break  # ei edistystä → loput epäonnistuvat pysyvästi (kandidaatit jää jäljelle)
        kandidaatit = mallit.hae_luokittelemattomat(tid, tiiv)
        if not kandidaatit:
            break

    return mukana, hylätty, len(kandidaatit)
