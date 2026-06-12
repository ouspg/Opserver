"""Meta-suodatus: kirjoittaa Kurssiluokitus-rivit taso- ja oppiainerajauksilla."""
from tietokanta import mallit


def _taso_ok(kurssi: dict, tasorajaus: str | None) -> bool:
    if not tasorajaus:
        return True
    sallitut = {t.strip() for t in tasorajaus.split(",") if t.strip()}
    return kurssi.get("Taso") in sallitut


def _oppiaine_ok(kurssi: dict, oppiainerajaus: str | None) -> bool:
    if not oppiainerajaus:
        return True
    oppiaine = (kurssi.get("Oppiaine") or "").lower()
    return any(t.strip().lower() in oppiaine for t in oppiainerajaus.split(",") if t.strip())


def aja(tutkimus: dict, edistyminen_cb=None) -> tuple[int, int]:
    """Käy kaikki kurssit läpi; kirjoittaa hylätyt Kurssiluokitus-tauluun.

    Palauttaa (läpäisseet, yhteensä). Idempotentti.
    """
    tid = tutkimus["TID"]
    tasorajaus = tutkimus.get("Tasorajaus")
    oppiainerajaus = tutkimus.get("Oppiainerajaus")

    kurssit = mallit.hae_kurssit()
    lapaisseet = 0

    for i, kurssi in enumerate(kurssit):
        taso_ok = _taso_ok(kurssi, tasorajaus)
        oa_ok = _oppiaine_ok(kurssi, oppiainerajaus)

        if taso_ok and oa_ok:
            lapaisseet += 1
        else:
            syyt = []
            if not taso_ok:
                syyt.append(f"taso '{kurssi.get('Taso')}' ∉ '{tasorajaus}'")
            if not oa_ok:
                syyt.append(f"oppiaine '{kurssi.get('Oppiaine')}' ≉ '{oppiainerajaus}'")
            mallit.aseta_luokitus(tid, kurssi["KID"], False, "meta: " + "; ".join(syyt))

        if edistyminen_cb:
            edistyminen_cb(i + 1, len(kurssit))

    return lapaisseet, len(kurssit)
