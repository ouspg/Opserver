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


def aja(tutkimus: dict, edistyminen_cb=None, nollaa: bool = False) -> tuple[int, int]:
    """Käy kurssit läpi; kirjoittaa luokittelut Kurssiluokitus-tauluun.

    Huomioidaan vain tutkimukseen valittujen korkeakoulujen kurssit. Lukuvuosi ja
    vähintään yksi korkeakoulu ovat pakollisia — muuten nostetaan ValueError.

    nollaa=False (oletus): ohitetaan kurssit joilla on jo luokittelu tässä tutkimuksessa.
    nollaa=True: ylikirjoitetaan kaikki olemassaolevat luokittelut.
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
    jo_luokitellut = set() if nollaa else {l["KID"] for l in mallit.hae_luokitukset(tid)}
    kasiteltavat = [k for k in kurssit if k["KID"] not in jo_luokitellut]

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
