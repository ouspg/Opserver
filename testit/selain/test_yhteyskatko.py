"""Päivityskatko käyttäjän silmin: haeJson odottaa 503:n / verkkokatkon yli ja näyttää
yhteysilmoituksen, katkennut WebSocket näyttää saman ilmoituksen, ja uudelleenyhdistyksen
jälkeen vaihtunut versio lataa sivun uudelleen — paitsi jos modaali on auki (ilmoitus)."""
import json

import pytest

TUTKIMUKSET = "/tutkimukset"
RIVI = "#tutkimukset-rungot tr"
ILMOITUS = "#yhteysilmoitus"
# Lyhyet ajastimet: haeJson yrittää 300 ms välein, WS-katko näkyy 300 ms jälkeen.
NOPEAT = "window.YHTEYS = { viiveMaxMs: 300, wsIlmoitusViiveMs: 300, wsUudelleenMs: 300 };"


def _nopea(k):
    k.add_init_script(NOPEAT)


def _katko(tapa):
    def kasittelija(reitti):
        if tapa == "503":
            reitti.fulfill(status=503, headers={"Retry-After": "10", "Content-Type": "application/json"},
                           body=json.dumps({"huolto": True, "detail": "Palvelua päivitetään"}))
        else:
            reitti.abort("connectionrefused")
    return kasittelija


@pytest.mark.parametrize("tapa, teksti", [("503", "päivitetään"), ("verkko", "katkesi")])
def test_haku_odottaa_katkon_yli_ja_ilmoittaa(kayttaja, tapa, teksti):
    """Katko kestää yli vanhan 4 yrityksen rajan → haku ei luovu, ilmoitus näkyy;
    yhteyden palatessa data latautuu ja ilmoitus poistuu."""
    reitti = "**/api/tutkimukset"
    s = kayttaja(TUTKIMUKSET, alustus=lambda k: (_nopea(k), k.route(reitti, _katko(tapa))))
    s.wait_for_selector(f"{ILMOITUS}.katko:has-text('{teksti}')", timeout=10000)
    s.wait_for_timeout(2500)  # > 4 yritystä 300 ms viiveellä
    assert s.locator(RIVI).count() == 0
    assert s.is_visible(ILMOITUS)
    s.context.unroute(reitti)
    s.wait_for_selector(RIVI, timeout=10000)
    s.wait_for_selector(ILMOITUS, state="hidden")


def test_katkennut_websocket_nayttaa_ilmoituksen(kayttaja):
    """Offline (CDP-verkkoemulaatio) + WS katki → ilmoitus; yhteys takaisin → ilmoitus pois."""
    s = kayttaja(TUTKIMUKSET, RIVI, alustus=_nopea)
    s.wait_for_function("ws && ws.readyState === WebSocket.OPEN")
    s.context.set_offline(True)
    s.evaluate("ws.close()")
    s.wait_for_selector(f"{ILMOITUS}.katko", timeout=10000)
    s.context.set_offline(False)
    s.wait_for_selector(ILMOITUS, state="hidden", timeout=10000)


def _uusi_versio(k):
    def info(reitti):
        vastaus = reitti.fetch()
        reitti.fulfill(response=vastaus, json={**vastaus.json(), "versio": "uusi-versio"})
    k.route("**/api/info", info)


def _yhdista_uudelleen(s):
    s.wait_for_function("latausVersio() !== null && ws && ws.readyState === WebSocket.OPEN")
    s.evaluate("window.__ennen_latausta = true")
    _uusi_versio(s.context)
    s.evaluate("ws.close()")


def test_uusi_versio_lataa_sivun_kun_modaali_ei_auki(kayttaja):
    s = kayttaja(TUTKIMUKSET, RIVI, alustus=_nopea)
    _yhdista_uudelleen(s)
    s.wait_for_function("!window.__ennen_latausta", timeout=10000)  # sivu latautui
    s.wait_for_selector(RIVI)
    s.wait_for_function("latausVersio() === 'uusi-versio'")
    assert not s.is_visible(ILMOITUS)


def test_uusi_versio_vain_ilmoitus_kun_modaali_auki(kayttaja):
    """Avoin modaali (kesken oleva HITL-korjaus ei saa kadota) → ilmoitus + Lataa-nappi."""
    s = kayttaja(TUTKIMUKSET, RIVI, alustus=_nopea)
    s.click("#info-nappi")
    s.wait_for_selector("#info-modaali:not(.piilotettu)")
    _yhdista_uudelleen(s)
    s.wait_for_selector(f"{ILMOITUS}.uusi-versio:has-text('Uusi versio saatavilla')", timeout=10000)
    s.wait_for_timeout(500)
    assert s.evaluate("window.__ennen_latausta") is True
    assert s.is_visible("#info-modaali")
    s.click(f"{ILMOITUS} button")
    s.wait_for_function("!window.__ennen_latausta", timeout=10000)
