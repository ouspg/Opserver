"""Meta-suodatus: kirjoittaa Kurssiluokitus-rivit taso- ja oppiainerajauksilla."""
from tietokanta import mallit


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

    nollaa=False (oletus): ohitetaan kurssit joilla on jo luokittelu tässä tutkimuksessa.
    nollaa=True: ylikirjoitetaan kaikki olemassaolevat luokittelut.
    Palauttaa (läpäisseet, käsitelty).
    """
    tid = tutkimus["TID"]
    tasorajaus = tutkimus.get("Tasorajaus")
    oppiainerajaus = tutkimus.get("Oppiainerajaus")

    kurssit = mallit.hae_kurssit()
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
