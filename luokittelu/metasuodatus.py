"""Meta-suodatus: kirjoittaa Kurssiluokitus-rivit korkeakoulu-, lukuvuosi-,
taso- ja oppiainerajauksilla."""
from tietokanta import mallit

_ERA = 500  # riviä per tietokantakierros


def _sisaltaa_jonkin(arvo: str | None, rajaus: str | None) -> bool:
    """Tyhjä rajaus = kaikki käy; muuten jokin pilkulla erotetuista osajonoista
    löytyy arvosta (kirjainkoosta riippumatta)."""
    if not rajaus:
        return True
    arvo = (arvo or "").lower()
    return any(t.strip().lower() in arvo for t in rajaus.split(",") if t.strip())


def _taso_ok(kurssi: dict, tasorajaus: str | None) -> bool:
    return _sisaltaa_jonkin(kurssi.get("Taso"), tasorajaus)


def _oppiaine_ok(kurssi: dict, oppiainerajaus: str | None) -> bool:
    return _sisaltaa_jonkin(kurssi.get("Oppiaine"), oppiainerajaus)


def aja(tutkimus: dict, edistyminen_cb=None, kohde: str = "uudet") -> tuple[int, int]:
    """Käy kurssit läpi; kirjoittaa luokittelut Kurssiluokitus-tauluun.

    Huomioidaan vain tutkimukseen valittujen korkeakoulujen kurssit. Lukuvuosi ja
    vähintään yksi korkeakoulu ovat pakollisia — muuten nostetaan ValueError.

    kohde valitsee mitkä in-scope-kurssit (uudelleen)luokitellaan:
      "uudet"      — vain vielä luokittelemattomat (oletus)
      "kaikki"     — kaikki, korvaa myös LLM-päätökset
      "hylatyt"    — vain meta-hylätyt (esim. kun oppiaine lisätty rajaukseen)
      "hyvaksytyt" — vain meta-läpäisseet (esim. kun oppiaine poistettu rajauksesta)
    Palauttaa (läpäisseet, käsitelty).
    """
    tid = tutkimus["TID"]
    tasorajaus = tutkimus.get("Tasorajaus")
    oppiainerajaus = tutkimus.get("Oppiainerajaus")
    # Lukuvuosi ja korkeakoulut ovat kova rajaus (SQL:ssä): väärän vuoden tai
    # korkeakoulun kurssit eivät ole tutkimuksen ehdokkaita lainkaan (ei luokitella).
    # Meta-hylkäys tehdään vain tason ja oppiaineen mukaan, koska ne voivat olla
    # virheellisiä ja vaativat tarkistusta.
    kurssit = mallit.hae_meta_ehdokkaat(tid) if tutkimus.get("Lukuvuosi") else None
    if kurssit is None:
        raise ValueError(
            "Tutkimukselle on määriteltävä lukuvuosi ja vähintään yksi korkeakoulu "
            "ennen meta-suodatusta."
        )
    kasiteltavat = [k for k in kurssit
                    if _kuuluu_kohteeseen(k if k["Luokiteltu"] else None, kohde)]

    # Päätökset kirjoitetaan erissä (_ERA riviä / kierros) rivikohtaisen kutsun sijaan.
    lapaisseet = 0
    for alku in range(0, len(kasiteltavat), _ERA):
        rivit = []
        for kurssi in kasiteltavat[alku:alku + _ERA]:
            taso_ok = _taso_ok(kurssi, tasorajaus)
            oa_ok = _oppiaine_ok(kurssi, oppiainerajaus)
            if taso_ok and oa_ok:
                lapaisseet += 1
                rivit.append((kurssi["KID"], None, "meta: odottaa LLM-seulontaa"))
            else:
                syyt = []
                if not taso_ok:
                    syyt.append(f"taso '{kurssi.get('Taso')}' ∉ '{tasorajaus}'")
                if not oa_ok:
                    syyt.append(f"oppiaine '{kurssi.get('Oppiaine')}' ≉ '{oppiainerajaus}'")
                rivit.append((kurssi["KID"], False, "meta: " + "; ".join(syyt)))
        mallit.aseta_luokitukset(tid, rivit)
        if edistyminen_cb:
            edistyminen_cb(alku + len(rivit), len(kasiteltavat), lapaisseet)

    return lapaisseet, len(kasiteltavat)


def _kuuluu_kohteeseen(luokitus: dict | None, kohde: str) -> bool:
    """Kuuluuko in-scope-kurssi valittuun uudelleenluokittelukohteeseen?"""
    if kohde == "kaikki":
        return True
    if kohde == "uudet":
        return luokitus is None
    if luokitus is None:
        return False
    mukana = luokitus.get("Mukana")
    on_meta = (luokitus.get("Luokitteluperuste") or "").startswith("meta:")
    if kohde == "hyvaksytyt":
        return mukana is None  # meta-läpäisseet (odottaa LLM-seulontaa)
    if kohde == "hylatyt":
        return mukana in (0, False) and on_meta  # meta-hylätyt (ei LLM-hylätyt)
    return False
