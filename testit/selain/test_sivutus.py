"""Sivutus + paikannus pysyvät näkyvissä yläpalkin alla; toisella sivulla oleva käyttäjä
näkyy pallurana sivunumerossa (#104)."""
from testit.selain.conftest import SLUG

HYLATTY = f"/tutkimukset/{SLUG}/kurssit-hylatty"
RIVI = "#tutkimus-kurssit-rungot tr[data-kid]"
SIVUTUS = ".nakyma.aktiivinen .tutkimus-kurssit-sivutus"


def _ylareunat(sivu, *valitsimet):
    return sivu.evaluate("(vs) => vs.map((v) => document.querySelector(v).getBoundingClientRect().top)",
                         list(valitsimet))


def test_toisella_sivulla_oleva_nakyy_kiinnitetyssa_sivutuksessa(kayttaja):
    a, b = kayttaja(HYLATTY, RIVI), kayttaja(HYLATTY, RIVI)
    assert a.locator(SIVUTUS).count() == 1  # alalaidan sivutus poistettu
    b.locator(f"{SIVUTUS} button", has_text="3").first.click()
    a.evaluate("scrollTo(0, 4000)")
    a.wait_for_selector(f"{SIVUTUS} .sivu-numero:has-text('3') > *", timeout=10000)
    alaraja = a.evaluate("document.querySelector('header').getBoundingClientRect().bottom")
    kiinn, otsikko = _ylareunat(a, "#s-tutkimus-kurssit .kiinnitetyt", "#s-tutkimus-kurssit thead th")
    assert abs(kiinn - alaraja) < 2
    assert otsikko >= kiinn + a.evaluate("document.querySelector('#s-tutkimus-kurssit .kiinnitetyt').offsetHeight") - 2


def test_kurssit_sivun_paikannus_kiinnitetty_ja_rivi_nakyviin(kayttaja):
    a = kayttaja("/kurssit", "#kurssit-rungot tr[data-kid]")
    a.evaluate("scrollTo(0, 3000)")
    alaraja = a.evaluate("document.querySelector('header').getBoundingClientRect().bottom")
    assert abs(_ylareunat(a, "#s-kurssit .kiinnitetyt")[0] - alaraja) < 2
    a.fill("#kurssit-paikannus input", "Kryptografia")
    a.wait_for_selector("#kurssit-paikannus li")
    a.keyboard.press("Enter")
    rivi = a.wait_for_selector("#kurssit-rungot tr.paikannettu", timeout=10000)
    laatikko = rivi.bounding_box()
    palkin_ala = a.evaluate("document.querySelector('#s-kurssit thead th').getBoundingClientRect().bottom")
    assert palkin_ala <= laatikko["y"] and laatikko["y"] + laatikko["height"] <= 800
