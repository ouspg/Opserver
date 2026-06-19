"""Lukuvuoden kattavuuslogiikka.

Kurssin OPS-kausi voi kattaa useamman lukuvuoden (esim. 2023-2026). Tutkimus
kohdistuu yhteen lukuvuoteen (esim. 2024-2025). Kausi kattaa tutkimuksen
lukuvuoden, jos se alkaa viimeistään tutkimuksen alkuvuonna ja päättyy
aikaisintaan tutkimuksen loppuvuonna.

Tukee muotoja "YYYY-YYYY" (esim. 2024-2025) ja "YYYY-YY" (Sisu/HY, esim. 2024-25).
"""
import re

_KAAVA = re.compile(r"^(\d{4})-(\d{2,4})$")


def _parsi_vuodet(kausi: str) -> tuple[int, int]:
    """Palauttaa (alkuvuosi, loppuvuosi). 'YYYY-YY' täydennetään vuosisadalla."""
    osuma = _KAAVA.match(kausi.strip())
    if not osuma:
        raise ValueError(f"Virheellinen lukuvuosi: {kausi!r}")
    alku = int(osuma.group(1))
    loppu_osa = osuma.group(2)
    if len(loppu_osa) == 2:
        loppu = (alku // 100) * 100 + int(loppu_osa)
        if loppu < alku:
            loppu += 100
    else:
        loppu = int(loppu_osa)
    return alku, loppu


def kauden_vuodet(kausi: str) -> list[str]:
    """Yksittäiset lukuvuodet jotka OPS-kausi kattaa.

    Esim. "2024-2027" -> ["2024-2025", "2025-2026", "2026-2027"];
    "2025-2026" -> ["2025-2026"]; "2026-27" -> ["2026-2027"].
    """
    alku, loppu = _parsi_vuodet(kausi)
    return [f"{v}-{v + 1}" for v in range(alku, loppu)]


def kattaa(ops_kausi: str, tutkimus_lukuvuosi: str) -> bool:
    """Kattaako kurssin OPS-kausi tutkimuksen lukuvuoden?"""
    ops_alku, ops_loppu = _parsi_vuodet(ops_kausi)
    tutk_alku, tutk_loppu = _parsi_vuodet(tutkimus_lukuvuosi)
    return ops_alku <= tutk_alku and ops_loppu >= tutk_loppu
