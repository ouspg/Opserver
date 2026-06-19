"""Meta-suodatus: kirjoittaa Kurssiluokitus-rivit korkeakoulu-, lukuvuosi-,
taso- ja oppiainerajauksilla."""
from tietokanta import mallit
from luokittelu import lukuvuosi as lv


def _taso_ok(kurssi: dict, tasorajaus: str | None) -> bool:
    if not tasorajaus:
        return True
    kurssi_taso = (kurssi.get("Taso") or "").lower()
    return any(t.strip().lower() in kurssi_taso for t in tasorajaus.split(",") if t.strip())


def _oppiaine_ok(kurssi: dict, oppiainerajaus: str | None) -> bool:
    if not oppiainerajaus:
        return True
    oppiaine = (kurssi.get("Oppiaine") or "").lower()
    return any(t.strip().lower() in oppiaine for t in oppiainerajaus.split(",") if t.strip())


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
    tutk_lukuvuosi = tutkimus.get("Lukuvuosi")
    korkeakoulut = set(mallit.hae_tutkimuksen_korkeakoulut(tid))
    if not tutk_lukuvuosi or not korkeakoulut:
        raise ValueError(
            "Tutkimukselle on määriteltävä lukuvuosi ja vähintään yksi korkeakoulu "
            "ennen meta-suodatusta."
        )

    # Lukuvuosi on kova rajaus: väärän vuoden kurssit eivät ole tutkimuksen
    # ehdokkaita lainkaan (ei luokitella). Meta-hylkäys tehdään vain tason ja
    # oppiaineen mukaan, koska ne voivat olla virheellisiä ja vaativat tarkistusta.
    kurssit = [
        k for k in mallit.hae_kurssit()
        if k["KKID"] in korkeakoulut and _kausi_kattaa(k.get("Opetusvuosi"), tutk_lukuvuosi)
    ]
    luok = {l["KID"]: l for l in mallit.hae_luokitukset(tid)}
    kasiteltavat = [k for k in kurssit if _kuuluu_kohteeseen(luok.get(k["KID"]), kohde)]

    lapaisseet = 0
    for i, kurssi in enumerate(kasiteltavat):
        taso_ok = _taso_ok(kurssi, tasorajaus)
        oa_ok = _oppiaine_ok(kurssi, oppiainerajaus)

        if taso_ok and oa_ok:
            lapaisseet += 1
            mallit.aseta_luokitus(tid, kurssi["KID"], None, "meta: odottaa LLM-seulontaa")
        else:
            syyt = []
            if not taso_ok:
                syyt.append(f"taso '{kurssi.get('Taso')}' ∉ '{tasorajaus}'")
            if not oa_ok:
                syyt.append(f"oppiaine '{kurssi.get('Oppiaine')}' ≉ '{oppiainerajaus}'")
            mallit.aseta_luokitus(tid, kurssi["KID"], False, "meta: " + "; ".join(syyt))

        if edistyminen_cb:
            edistyminen_cb(i + 1, len(kasiteltavat), lapaisseet)

    return lapaisseet, len(kasiteltavat)


def _kausi_kattaa(ops_kausi: str | None, lukuvuosi: str) -> bool:
    """lv.kattaa, mutta puuttuva/virheellinen kausi rajataan pois (ei kaadu)."""
    if not ops_kausi:
        return False
    try:
        return lv.kattaa(ops_kausi, lukuvuosi)
    except ValueError:
        return False


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
