"""Raporttimuokkain lomakesession päällä: yhteismuokkaus, pallurat, tallennus, sulkeminen.
Tallennus mockataan (POST tallennetaan listaan) → kanta ei muutu."""
import json
import re

from playwright.sync_api import expect

from testit.selain.conftest import SLUG

RAPORTTI = f"/tutkimukset/{SLUG}/raportti"
TA = "#raporttimuokkaus-tekstialue"
MODAALI = "#raporttimuokkaus-modaali"


def _muokkaa(osio):
    return f".raportti-osio[data-avain={osio}] .raportti-muokkaa-nappi"


def _uusi(kayttaja, tallennukset=None):
    sivu = kayttaja(RAPORTTI, ".raportti-osio", leveys=1400, korkeus=900)

    def tallenna(reitti):
        if tallennukset is not None:
            tallennukset.append(json.loads(reitti.request.post_data))
        reitti.fulfill(status=200, content_type="application/json", body='{"ok": true}')
    sivu.route("**/raportti/*", lambda r: tallenna(r) if r.request.method == "POST" else r.continue_())
    return sivu


def _avaa(sivu, osio):
    sivu.click(_muokkaa(osio))
    sivu.wait_for_function(f"!document.querySelector('{TA}').disabled")


def _piirretty(sivu, valitsin):
    """Onko canvasissa yksikin ei-läpinäkyvä pikseli (pallura/kursori piirretty)?"""
    return sivu.evaluate("""(v) => [...document.querySelectorAll(v)].some((c) => {
      const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
      for (let i = 3; i < d.length; i += 4) if (d[i]) return true; return false; })""", valitsin)


def test_yhteismuokkaus_teksti_kursorit_ja_pallurat(kayttaja):
    """Molemmat saavat kannan tekstin, kirjoitus ja kursori välittyvät, sivulla oleva näkee muokkaajat napilla."""
    a, b, c = _uusi(kayttaja), _uusi(kayttaja), _uusi(kayttaja)
    kannassa = a.evaluate(f"haeJson('/api/tutkimukset/{SLUG}/raportti').then((d) => d.osiot.johdanto)")
    assert kannassa.startswith("Johdanto: ")
    _avaa(a, "johdanto")
    assert a.input_value(TA) == kannassa
    _avaa(b, "johdanto")
    expect(b.locator(TA)).to_have_value(kannassa)

    a.click(TA)
    a.keyboard.press("End")
    a.keyboard.type(" LISÄYS")
    expect(b.locator(TA)).to_have_value(kannassa + " LISÄYS", timeout=10000)
    b.wait_for_selector(f"{MODAALI} .lomake-kursori canvas", state="attached")
    assert _piirretty(b, f"{MODAALI} .lomake-kursori canvas")
    assert _piirretty(b, f"{MODAALI} .lomake-muokkaaja canvas")

    c.mouse.move(300, 300)
    c.wait_for_selector(".raportti-osio[data-avain=johdanto] .lomake-pallurat canvas", timeout=10000)
    expect(c.locator(_muokkaa("johdanto"))).to_have_class(re.compile(r"\blomake-auki\b"))

    a.fill(TA, "p" * 30000)
    expect(b.locator(TA)).to_have_value("p" * 30000, timeout=10000)


def test_tallennus_paivittaa_kaikki_ja_sulkee_muiden_modaalin(kayttaja):
    """Tallentajan teksti lähtee palvelimelle, osio päivittyy molemmilla ja toisen modaali sulkeutuu."""
    tallennukset = []
    a, b = _uusi(kayttaja, tallennukset), _uusi(kayttaja)
    _avaa(a, "arvioinnit")
    _avaa(b, "arvioinnit")
    a.fill(TA, "Uusi arviointi\nrivi 2")
    expect(b.locator(TA)).to_have_value("Uusi arviointi\nrivi 2", timeout=10000)
    a.click("#raporttimuokkaus-tallenna")
    expect(a.locator(MODAALI)).to_be_hidden(timeout=15000)
    assert tallennukset[-1] == {"teksti": "Uusi arviointi\nrivi 2"}
    osio = ".raportti-osio[data-avain=arvioinnit] .raportti-osio-teksti"
    expect(b.locator(MODAALI)).to_be_hidden(timeout=10000)
    for sivu in (a, b):
        expect(sivu.locator(osio)).to_contain_text("Uusi arviointi")
        expect(sivu.locator(osio)).to_contain_text("rivi 2")


def test_sulkeminen_ruksilla_ja_taustasta(kayttaja):
    """Modaali sulkeutuu ✕:stä ja taustan klikkauksesta, avautuu uudelleen ja lomakesessio päättyy."""
    a = _uusi(kayttaja)
    _avaa(a, "johdanto")
    a.click(f"{MODAALI} .modaali-sulje")
    expect(a.locator(MODAALI)).to_be_hidden()
    _avaa(a, "johdanto")
    a.mouse.click(5, 450)
    expect(a.locator(MODAALI)).to_be_hidden()
    assert a.evaluate("window.omaLomake()") is None
