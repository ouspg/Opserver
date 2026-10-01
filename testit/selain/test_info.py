"""Opserver-infomodaali: sisältö, versio, avaus/sulkeminen ja modaalin sisäinen kursori-
sijainti (vieraan pallura seuraa modaalin sisältöä vierityksessä, reunapallura vie kohtaan)."""
import pytest

TUTKIMUKSET = "/tutkimukset"
RIVI = "#tutkimukset-rungot tr"
SISALTO = "#info-modaali .modaali-sisalto"


def _avaa_info(s):
    s.click("#info-nappi")
    s.wait_for_selector("#info-teksti h2", timeout=15000)


def test_infomodaali_sisalto_ja_sulkeminen(kayttaja, pohja):
    """Info avautuu URL:ia vaihtamatta; logo, teksti ja versiolinkki; sulkunappi, tausta ja näppäimistö."""
    s = kayttaja(TUTKIMUKSET, RIVI, korkeus=900)
    polku = s.evaluate("location.pathname")
    _avaa_info(s)
    assert s.evaluate("location.pathname") == polku
    assert s.inner_text("#info-teksti h2").strip()
    assert s.evaluate("document.querySelector('.info-logo').naturalWidth > 0")
    assert s.locator("#info-teksti li").count() > 0
    versio = s.request.get(pohja + "/api/info").json()["versio"]
    assert s.inner_text("#info-versio").startswith(f"Versio {versio}")
    if versio != "tuntematon":
        assert s.get_attribute("#info-versio a", "href").endswith(f"/commit/{versio}")
    s.click("#info-modaali .modaali-sulje")
    s.wait_for_selector("#info-modaali", state="hidden")
    s.click("#info-nappi")
    s.wait_for_selector("#info-modaali:not(.piilotettu)")
    s.mouse.click(10, 880)  # tausta
    s.wait_for_selector("#info-modaali", state="hidden")
    s.focus("#info-nappi")
    s.keyboard.press("Enter")
    s.wait_for_selector("#info-modaali:not(.piilotettu)")


def _vieras(s, ehto="true"):
    """Odottaa vieraan kursorin, joka täyttää ehdon (k = {x, y, ulkona, kulma}); palauttaa sen."""
    lauseke = """(ehto) => { const el = document.querySelector('#kursori-kerros .vieras-kursori');
      if (!el) return null; const r = el.querySelector('canvas').getBoundingClientRect();
      const k = { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2),
                  ulkona: el.classList.contains('ulkona'), kulma: parseFloat(el.style.getPropertyValue('--kulma')) || 0 };
      return new Function('k', 'return ' + ehto)(k) ? k : null; }"""
    return s.wait_for_function(lauseke, arg=ehto, timeout=10000).json_value()


def _sisalto_y(s):
    return s.evaluate(f"document.querySelector('{SISALTO}').getBoundingClientRect().top")


def _odotettu(katsoja, kohde, osoitin_y):
    """Kohteen osoittimen sisältökohta katsojan ruudulla."""
    return round(_sisalto_y(katsoja) + osoitin_y - _sisalto_y(kohde))


def _vieras_kohdassa(katsoja, kohde, osoitin_y):
    """Odottaa, että vieras pallura on kohteen osoittimen sisältökohdassa (±2 px)."""
    for _ in range(50):
        k = _vieras(katsoja)
        if abs(k["y"] - _odotettu(katsoja, kohde, osoitin_y)) <= 2:
            return k
        katsoja.wait_for_timeout(200)
    pytest.fail(f"pallura y={k['y']}, odotettu {_odotettu(katsoja, kohde, osoitin_y)}")


def test_infomodaalin_vieritys_siirtaa_vieraan_kursoria(kayttaja):
    """Modaalissa vieraan pallura on samassa sisältökohdassa kummankin vierityksestä riippumatta;
    ruudun ulkopuolinen näkyy reunapallurana nuolella, jonka klikkaus vierittää kohtaan."""
    a = kayttaja(TUTKIMUKSET, RIVI, korkeus=500)
    b = kayttaja(TUTKIMUKSET, RIVI, korkeus=500)
    for s in (a, b):
        _avaa_info(s)
    a.mouse.move(640, 300)
    a.mouse.move(641, 300)
    b.mouse.move(150, 450)
    b.mouse.move(151, 450)
    _vieras_kohdassa(b, a, 300)
    b.evaluate("document.getElementById('info-modaali').scrollBy(0, 150)")
    _vieras_kohdassa(b, a, 300)
    _vieras(a, "k.ulkona && k.kulma > 1 && k.kulma < 2.2")  # B vieritti alas → A:lle reunassa, nuoli alas
    a.mouse.wheel(0, 100)  # rulla liikuttamatta hiirtä
    _vieras_kohdassa(b, a, 300)
    b.evaluate("document.getElementById('info-modaali').scrollBy(0, 3000)")
    k = _vieras(b, "k.ulkona && k.kulma < -1")  # A yläpuolella → nuoli ylös
    b.mouse.click(k["x"], k["y"])
    _vieras(b, "!k.ulkona")
    _vieras_kohdassa(b, a, 300)
    assert b.is_visible("#info-modaali")
