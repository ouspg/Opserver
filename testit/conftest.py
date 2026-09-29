"""Yhteiset fixturet."""
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_yhteys():
    """Mockattu tietokantayhteys: (yht, kursori). Kattaa sekä mallit- että
    testimallit-moduulin (jälkimmäisen monilauseiset transaktiot)."""
    yht = MagicMock()
    kursori = MagicMock()
    yht.__enter__ = MagicMock(return_value=yht)
    yht.__exit__ = MagicMock(return_value=False)
    yht.cursor.return_value.__enter__ = MagicMock(return_value=kursori)
    yht.cursor.return_value.__exit__ = MagicMock(return_value=False)
    with patch("tietokanta.mallit.yhteys", return_value=yht), \
         patch("tietokanta.testimallit.yhteys", return_value=yht):
        yield yht, kursori
