"""Testit tiedonhaku/konfiguraatio.py:lle — korkeakoulun API-osoitteen selvitys.

Geneerinen: sama logiikka kaikille Peppi/Sisu-instansseille, ei per-korkeakoulu-
erikoistapauksia. Verkko mockataan.
"""
from unittest.mock import patch
import pytest
from tiedonhaku import konfiguraatio


def _vastaus(teksti="", status=200):
    class V:
        text = teksti
        status_code = status
        def raise_for_status(self):
            if self.status_code >= 400:
                import requests
                raise requests.HTTPError(f"HTTP {self.status_code}")
    return V()


class TestNormalisoiHost:
    def test_lisaa_https_kun_puuttuu(self):
        assert konfiguraatio._normalisoi_host("opasbe.peppi.oulu.fi") == "https://opasbe.peppi.oulu.fi"

    def test_sailyttaa_olemassa_olevan_skeeman_ja_riisuu_kauttaviivan(self):
        assert konfiguraatio._normalisoi_host("https://opas.peppi.utu.fi/") == "https://opas.peppi.utu.fi"

    def test_riisuu_lainausmerkit(self):
        assert konfiguraatio._normalisoi_host('"studiehandboken.abo.fi"') == "https://studiehandboken.abo.fi"


class TestEtsiBackendBundlesta:
    def test_kaksoispiste_ilman_skeemaa(self):  # Oulu-tyyli
        js = 'foo,backendUrl:"opasbe.peppi.oulu.fi",bar'
        assert konfiguraatio._etsi_backend_bundlesta(js) == "https://opasbe.peppi.oulu.fi"

    def test_yhtasuuruus_skeeman_kanssa(self):  # UTU-tyyli
        js = 'x.backendUrl="https://opas.peppi.utu.fi",y'
        assert konfiguraatio._etsi_backend_bundlesta(js) == "https://opas.peppi.utu.fi"

    def test_puuttuva_backendurl_nostaa_virheen(self):
        with pytest.raises(ValueError):
            konfiguraatio._etsi_backend_bundlesta("ei mitään relevanttia")


class TestSelvitaKonfiguraatio:
    def test_peppi_lukee_backendin_bundlesta_ja_varmistaa(self):
        front_html = '<script src="main.abc123.js"></script>'
        bundle_js = 'config={backendUrl:"opasbe.peppi.oulu.fi"}'
        with patch("tiedonhaku.konfiguraatio.requests.get") as get:
            get.side_effect = [_vastaus(front_html), _vastaus(bundle_js), _vastaus("[]")]
            tulos = konfiguraatio.selvita_konfiguraatio("https://opas.peppi.oulu.fi", "Peppi")
        assert tulos == {"api_osoite": "https://opasbe.peppi.oulu.fi"}
        # viimeinen kutsu varmistaa navigation-endpointin oikealla hostilla
        assert get.call_args_list[-1].args[0] == "https://opasbe.peppi.oulu.fi/api/navigation"

    def test_peppi_sama_host_kun_bundle_julistaa_frontendin(self):  # UTU/Vaasa/Åbo-tyyli
        front_html = '<script src="main.def456.js"></script>'
        bundle_js = 'backendUrl="https://opas.peppi.utu.fi"'
        with patch("tiedonhaku.konfiguraatio.requests.get") as get:
            get.side_effect = [_vastaus(front_html), _vastaus(bundle_js), _vastaus("[]")]
            tulos = konfiguraatio.selvita_konfiguraatio("https://opas.peppi.utu.fi", "Peppi")
        assert tulos == {"api_osoite": "https://opas.peppi.utu.fi"}

    def test_sisu_kayttaa_samaa_originia_ja_varmistaa_korin(self):
        with patch("tiedonhaku.konfiguraatio.requests.get") as get:
            get.side_effect = [_vastaus("[]")]
            tulos = konfiguraatio.selvita_konfiguraatio("https://sisu.helsinki.fi", "Sisu")
        assert tulos == {"api_osoite": "https://sisu.helsinki.fi"}
        assert get.call_args_list[-1].args[0] == "https://sisu.helsinki.fi/kori/api/curriculum-periods"

    def test_tuntematon_tyyppi_nostaa_virheen(self):
        with pytest.raises(ValueError):
            konfiguraatio.selvita_konfiguraatio("https://x", "Muu")
