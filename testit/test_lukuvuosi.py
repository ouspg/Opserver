"""Testit lukuvuoden kattavuuslogiikalle (luokittelu/lukuvuosi.py).

OPS-kausi [a,b] kattaa tutkimuksen lukuvuoden [s,e] ⟺ a ≤ s JA b ≥ e.
"""
import pytest
from luokittelu import lukuvuosi


class TestKattaa:
    # Tutkimuksen lukuvuosi 2024-2025: nämä kaudet kattavat sen
    @pytest.mark.parametrize("ops", ["2024-2025", "2023-2026", "2022-2025", "2024-2026"])
    def test_kattaa(self, ops):
        assert lukuvuosi.kattaa(ops, "2024-2025") is True

    # Nämä eivät kata: alkaa liian myöhään tai loppuu liian aikaisin
    @pytest.mark.parametrize("ops", ["2025-2027", "2022-2024", "2026-2027", "2020-2023"])
    def test_ei_kata(self, ops):
        assert lukuvuosi.kattaa(ops, "2024-2025") is False

    def test_yyyy_yy_muoto(self):
        # Sisu/HY: 2024-25 tarkoittaa lukuvuotta 2024-2025
        assert lukuvuosi.kattaa("2024-25", "2024-2025") is True
        assert lukuvuosi.kattaa("2024-2025", "2024-25") is True
        assert lukuvuosi.kattaa("2025-26", "2024-2025") is False


class TestKaudenVuodet:
    def test_monivuotinen_kausi(self):
        assert lukuvuosi.kauden_vuodet("2024-2027") == ["2024-2025", "2025-2026", "2026-2027"]

    def test_yhden_vuoden_kausi(self):
        assert lukuvuosi.kauden_vuodet("2025-2026") == ["2025-2026"]

    def test_yyyy_yy_muoto(self):
        assert lukuvuosi.kauden_vuodet("2026-27") == ["2026-2027"]


class TestParsiVuodet:
    def test_yyyy_yyyy(self):
        assert lukuvuosi._parsi_vuodet("2024-2025") == (2024, 2025)
        assert lukuvuosi._parsi_vuodet("2023-2026") == (2023, 2026)

    def test_yyyy_yy(self):
        assert lukuvuosi._parsi_vuodet("2024-25") == (2024, 2025)
        assert lukuvuosi._parsi_vuodet("2099-00") == (2099, 2100)

    def test_virheellinen_nostaa_virheen(self):
        with pytest.raises(ValueError):
            lukuvuosi._parsi_vuodet("ei-vuosi")
