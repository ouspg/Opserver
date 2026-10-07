"""Jaettu lomake (lomakesessio.js): ennen liittymisvastausta tai WebSocket-katkon aikana
kirjoitettu teksti ei katoa (TASKS #10). Tallennukset mockataan → kanta ei muutu."""
from playwright.sync_api import expect

from testit.selain.conftest import SLUG

RAPORTTI = f"/tutkimukset/{SLUG}/raportti"
VALITTU = f"/tutkimukset/{SLUG}/kurssit-valittu"
TA = "#raporttimuokkaus-tekstialue"
# Eri osio kuin test_raportti.py:ssä → palvelimen lomaketila ei vuoda testistä toiseen.
MUOKKAA = ".raportti-osio[data-avain=kurssit] .raportti-muokkaa-nappi"
HITL = "#tutkimus-kurssit-rungot .hitl-nappi"
# Palvelimen lomakeviestit (myös liittymisvastaus) saapuvat 2 s viiveellä.
HIDASTA = """(() => { const k = window.lomakeKuuntelija;
  window.lomakeKuuntelija = (v) => setTimeout(() => k(v), 2000); })()"""


def _uusi(kayttaja, polku, odota):
    sivu = kayttaja(polku, odota, leveys=1400, korkeus=900)
    for reitti in ("**/hitl", "**/raportti/kurssit"):
        sivu.route(reitti, lambda r: r.fulfill(status=200, content_type="application/json", body='{"ok": true}'))
    return sivu


def _avaa_raportti(sivu):
    sivu.click(MUOKKAA)
    sivu.wait_for_function(f"!document.querySelector('{TA}').disabled")


def test_kirjoitus_ennen_liittymisvastausta_ja_katkon_aikana_sailyy(kayttaja):
    """Ennen liittymisvastausta kirjoitettu säilyy ja välittyy; katkon aikana kirjoitettu yhdistyy toisen muutokseen."""
    a = _uusi(kayttaja, RAPORTTI, ".raportti-osio")
    a.evaluate(HIDASTA)
    _avaa_raportti(a)
    alku = a.input_value(TA)
    a.keyboard.press("End")
    a.keyboard.type(" ABC")
    b = _uusi(kayttaja, RAPORTTI, ".raportti-osio")
    _avaa_raportti(b)
    expect(b.locator(TA)).to_have_value(alku + " ABC", timeout=10000)
    expect(a.locator(TA)).to_have_value(alku + " ABC")

    a.evaluate("ws.close()")
    a.wait_for_function("ws.readyState === WebSocket.CLOSED")
    a.click(TA)
    a.keyboard.press("End")
    a.keyboard.type(" OFF")
    b.click(TA)
    b.keyboard.press("End")
    b.keyboard.type(" BEE")
    odotettu = alku + " ABC BEE OFF"  # uudelleenyhdistyksessä A:n lisäys palvelimen tilan perään
    expect(a.locator(TA)).to_have_value(odotettu, timeout=15000)
    expect(b.locator(TA)).to_have_value(odotettu, timeout=15000)


def test_liittyminen_hitl_lomakkeeseen_ennen_vastausta(kayttaja):
    """Liittyjän ennen vastausta kirjoittama yhdistyy olemassa olevaan; avaaja ei välähdä; jatkomuokkaus välittyy."""
    b = _uusi(kayttaja, VALITTU, HITL)
    a = _uusi(kayttaja, VALITTU, HITL)
    b.locator(HITL).first.click()
    b.fill("#hitl-nimi", "Bertta")
    b.click("#hitl-perustelu")
    b.keyboard.type("B-teksti")
    # B:n arvot palvelimella: kolmas käyttäjä liittyy ja saa ne.
    c = _uusi(kayttaja, VALITTU, HITL)
    c.locator(HITL).first.click()
    expect(c.locator("#hitl-perustelu")).to_have_value("B-teksti", timeout=10000)
    c.click("#hitl-modaali-sulje")

    a.evaluate(HIDASTA)
    a.locator(HITL).first.click()
    a.click("#hitl-perustelu")
    a.keyboard.type("A1")
    a.wait_for_timeout(300)
    assert b.input_value("#hitl-perustelu") == "B-teksti"  # ei välähdä ennen A:n liittymistä
    expect(a.locator("#hitl-perustelu")).to_have_value("B-tekstiA1", timeout=10000)
    expect(b.locator("#hitl-perustelu")).to_have_value("B-tekstiA1", timeout=10000)
    expect(a.locator("#hitl-nimi")).to_have_value("Bertta")
    a.keyboard.type("Z")
    expect(b.locator("#hitl-perustelu")).to_have_value("B-tekstiA1Z", timeout=10000)


def test_aloittajuus_sailyy_websocket_katkon_yli(kayttaja):
    """#102: lomakkeen avannut A pysyy aloittajana, vaikka hänen yhteytensä katkeaa B:n
    ollessa mukana → A:n tallennus muistaa hänen oman nimensä ja sähköpostinsa."""
    a = _uusi(kayttaja, VALITTU, HITL)
    b = _uusi(kayttaja, VALITTU, HITL)
    a.locator(HITL).nth(1).click()
    a.fill("#hitl-nimi", "Aino")
    a.fill("#hitl-sahkoposti", "aino@esimerkki.fi")
    a.fill("#hitl-perustelu", "katkon yli")
    a.locator('input[name="hitl-juurisyy"]').first.check()
    b.locator(HITL).nth(1).click()
    expect(b.locator("#hitl-nimi")).to_have_value("Aino", timeout=10000)

    a.evaluate("""(() => { const k = window.lomakeKuuntelija; window._vastauksia = 0;
      window.lomakeKuuntelija = (v) => { window._vastauksia++; k(v); }; })()""")
    a.evaluate("ws.close()")
    a.wait_for_function("ws.readyState === WebSocket.CLOSED")
    a.evaluate("window._vastauksia = 0")
    # Uudelleenyhdistys (3 s) → uudelleenliittyminen → palvelimen vastaus (2 jäsentä).
    a.wait_for_function("ws.readyState === WebSocket.OPEN && window._vastauksia > 0", timeout=15000)
    assert a.evaluate("window.lomakeOlenAloittaja()")
    a.click("#hitl-laheta")
    a.wait_for_function("localStorage.getItem('hitl_nimi') === 'Aino'", timeout=10000)
    assert a.evaluate("localStorage.getItem('hitl_sahkoposti')") == "aino@esimerkki.fi"
