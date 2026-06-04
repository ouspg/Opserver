"""Abstrakti kantaluokka opinto-opaslukijoille (Peppi, Sisu)."""
import os
import time
from abc import ABC, abstractmethod

import requests


class OpsLukija(ABC):
    def __init__(self, korkeakoulu: dict):
        self.korkeakoulu = korkeakoulu
        self.viive = float(os.getenv("CRAWL_DELAY_SECONDS", 2))

    def _hae_json(self, url: str):
        """Kohtelias HTTP GET: odottaa viiveen ja palauttaa JSON-vastauksen."""
        time.sleep(self.viive)
        vastaus = requests.get(url, timeout=30)
        vastaus.raise_for_status()
        return vastaus.json()

    @abstractmethod
    def hae_kurssit(self) -> list[dict]:
        """Hakee kaikki kurssit korkeakoulun opinto-oppaasta."""
