"""Yksinkertainen TTL-välimuisti staattisille kyselyille.

Tarkoitettu vain datalle joka EI muutu käytön aikana (kurssikatalogi,
korkeakoulut, lukuvuodet, tasot) — ei annotointiriippuvaiselle datalle, joka
WebUI:ssa pitää näkyä reaaliaikaisesti. Prosessikohtainen (WebUI-kontti omansa).
"""
import functools
import time


def ttl_valimuisti(sekunnit: float, kello=time.monotonic):
    """Dekoraattori: muistaa paluuarvon argumenttien mukaan `sekunnit` ajan.

    Funktiolle lisätään `.tyhjenna()` välimuistin nollaamiseen (esim. testit).
    """
    def kaare(fn):
        varasto: dict = {}

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            avain = (args, tuple(sorted(kwargs.items())))
            nyt = kello()
            osuma = varasto.get(avain)
            if osuma is not None and osuma[0] > nyt:
                return osuma[1]
            arvo = fn(*args, **kwargs)
            varasto[avain] = (nyt + sekunnit, arvo)
            return arvo

        wrapper.tyhjenna = varasto.clear
        return wrapper

    return kaare
