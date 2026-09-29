"""Yhteiset fixturet."""
from contextlib import ExitStack
from unittest.mock import MagicMock, patch
import pytest

_YHTEYDEN_AVAAJAT = ("_yhteiset", "kurssit", "tutkimukset", "luokitukset", "vastaukset",
                     "raportti", "testimallit")


@pytest.fixture
def mock_yhteys():
    """Mockattu tietokantayhteys: (yht, kursori). Patchataan jokaiseen moduuliin, joka
    avaa yhteyden itse (mallit on jaettu aihepiireittäin, ks. tietokanta/mallit.py)."""
    yht = MagicMock()
    kursori = MagicMock()
    yht.__enter__ = MagicMock(return_value=yht)
    yht.__exit__ = MagicMock(return_value=False)
    yht.cursor.return_value.__enter__ = MagicMock(return_value=kursori)
    yht.cursor.return_value.__exit__ = MagicMock(return_value=False)
    with ExitStack() as pino:
        for moduuli in _YHTEYDEN_AVAAJAT:
            pino.enter_context(patch(f"tietokanta.{moduuli}.yhteys", return_value=yht))
        yield yht, kursori
