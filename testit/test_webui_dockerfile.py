"""WebUI-kuva sisältää kaikki paketit, joita webui importtaa (suoraan tai välillisesti).

Selaintestit ajavat uvicornia repon juuresta, joten puuttuva COPY näkyy vasta
tuotannon kontissa (#109: raportti → arviointi.luokat puuttui kuvasta).
"""
import ast
import re
from pathlib import Path

JUURI = Path(__file__).resolve().parent.parent


def _kopioidut_paketit() -> set[str]:
    teksti = (JUURI / "webui" / "Dockerfile").read_text()
    return set(re.findall(r"^COPY (\w+)/ ", teksti, re.MULTILINE))


def _projektin_importit(tiedosto: Path) -> set[str]:
    """Tiedoston importtaamat projektin omat moduulit (pisteellinen nimi)."""
    nimet = set()
    for solmu in ast.walk(ast.parse(tiedosto.read_text())):
        if isinstance(solmu, ast.Import):
            nimet.update(a.name for a in solmu.names)
        elif isinstance(solmu, ast.ImportFrom) and solmu.module and not solmu.level:
            nimet.add(solmu.module)
            nimet.update(f"{solmu.module}.{a.name}" for a in solmu.names)
    return {n for n in nimet if (JUURI / n.split(".")[0]).is_dir()}


def _moduulin_tiedosto(nimi: str) -> Path | None:
    polku = JUURI.joinpath(*nimi.split("."))
    for ehdokas in (polku.with_suffix(".py"), polku / "__init__.py"):
        if ehdokas.is_file():
            return ehdokas
    return None


def test_webuin_importtaamat_paketit_kopioidaan_kuvaan():
    kaydyt, jono = set(), [p for p in (JUURI / "webui").glob("*.py")]
    paketit = set()
    while jono:
        tiedosto = jono.pop()
        if tiedosto in kaydyt:
            continue
        kaydyt.add(tiedosto)
        for nimi in _projektin_importit(tiedosto):
            paketit.add(nimi.split(".")[0])
            if (seuraava := _moduulin_tiedosto(nimi)) is not None:
                jono.append(seuraava)
    puuttuvat = paketit - _kopioidut_paketit()
    assert not puuttuvat, f"webui/Dockerfile: lisää COPY {sorted(puuttuvat)}"
