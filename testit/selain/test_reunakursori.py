"""Toisen leijuva kursori: yläpalkissa oleva näkyy yläpalkin alueella, ruudun ulkopuolella
oleva reunapallurana heti yläpalkin alla (nuoli suuntaan), reunapalluran klikkaus vierittää luo.
Rajana on yläpalkin alareuna — tai kurssilistan kiinnitetyn sivutus-/paikannuspalkin
alareuna, kun palkki on jumittunut yläpalkin alle (#106). Palkissa oleva osoitin näkyy
toisella hänen palkissaan (palkin suhteen, vierityksestä riippumatta)."""
import pytest
from playwright.sync_api import TimeoutError as Aikakatkaisu

from testit.selain.conftest import SLUG

VALITUT = f"/tutkimukset/{SLUG}/kurssit-valittu"
RIVI = "#tutkimus-kurssit-rungot tr.kurssi-rivi"
REUNA = 30  # KURSORI_REUNA (yhteistyo.js)
AY = 650  # A:n osoittimen y ylhäällä: kurssirivi kiinnitetyn palkin (n. 360–440) alapuolella
KURSORI = """() => { const el = document.querySelector('#kursori-kerros .vieras-kursori');
  if (!el || el.getAnimations().length) return null; const r = el.querySelector('canvas').getBoundingClientRect();
  const k = {x: r.left + r.width / 2, y: r.top + r.height / 2, ulkona: el.classList.contains('ulkona'),
          kulma: parseFloat(el.style.getPropertyValue('--kulma')),
          ylapalkki: document.querySelector('header').getBoundingClientRect().bottom,
          palkki: [...document.querySelectorAll('.kiinnitetyt')].find((e) => e.offsetParent).getBoundingClientRect().toJSON()};
  k.ala = k.palkki.top <= k.ylapalkki + 1 ? k.palkki.bottom : k.ylapalkki; return k; }"""


def _odota_kursori(b, ehto):
    """Odottaa, että A:n kursori B:llä (k) täyttää JS-ehdon; palauttaa sen tiedot (vasta kun
    left/top-liukuma on päättynyt — muuten klikkaus osuu ohi, #115)."""
    try:
        b.wait_for_function(f"() => {{ const k = ({KURSORI})(); return k && ({ehto}); }}", timeout=10000)
    except Aikakatkaisu:
        pytest.fail(f"ehto {ehto} ei täyttynyt: {b.evaluate(KURSORI)}")
    return b.evaluate(KURSORI)


def _vierita(sivu, y):
    """Vierittää kohtaan y vasta, kun lista on renderöity niin pitkäksi (osa kerrallaan) —
    muuten scrollTo jää vajaaksi ja kursori ei ole ruudun ulkopuolella (#115)."""
    sivu.wait_for_function(f"document.documentElement.scrollHeight >= {y} + innerHeight", timeout=15000)
    sivu.evaluate(f"scrollTo(0, {y})")
    sivu.wait_for_function(f"Math.abs(scrollY - {y}) < 1")


def _liikuta(sivu, x, y):
    sivu.mouse.move(x - 5, y)
    sivu.mouse.move(x, y)


def _liikuta_riville(a):
    """A:n osoitin sisältöön (kurssiriville), ei kiinnitettyyn palkkiin: palkissa oleva
    sijainti lähetetään palkin suhteen (#106), ja palkin kohta elää latauksen aikana (#115)."""
    a.wait_for_function(f"document.elementFromPoint(645, {AY})?.closest('tr.kurssi-rivi')")
    _liikuta(a, 645, AY)


@pytest.fixture
def kaksi(kayttaja):
    a, b = kayttaja(VALITUT, RIVI), kayttaja(VALITUT, RIVI)
    b.mouse.move(640, 600)
    return a, b


def test_ylapalkissa_oleva_nakyy_ylapalkissa(kaksi):
    """A vierittänyt alas, hiiri yläpalkissa → B:llä pallura yläpalkin alueella, ei nuolta."""
    a, b = kaksi
    _vierita(a, 2000)
    _liikuta(a, 705, 45)
    _odota_kursori(b, "!k.ulkona && Math.abs(k.x - 705) < 2 && k.y <= k.ylapalkki")


def test_ylapuolella_oleva_heti_ylapalkin_alla(kaksi):
    """A ylhäällä, B vierittänyt alas → reunapallura heti yläpalkin alla, nuoli ylös."""
    a, b = kaksi
    _liikuta_riville(a)
    _vierita(b, 2500)
    _odota_kursori(b, f"k.ulkona && k.kulma < -1 && k.ala < k.y && k.y <= k.ala + {REUNA} + 10")


def test_ylapalkin_taakse_vierittynyt_reunassa(kaksi):
    """A:n kohta on B:llä yläpalkin takana → reunapallura heti yläpalkin alla."""
    a, b = kaksi
    _liikuta_riville(a)
    _vierita(b, AY - 40)
    k = _odota_kursori(b, f"k.ulkona && k.ala < k.y && k.y <= k.ala + {REUNA} + 10")
    assert k["ala"] > 40  # A:n kohta (y=40 näkymässä) on todella yläpalkin alla


def test_reunapalluran_klikkaus_vierittaa_luo(kaksi):
    """Reunapalluran klikkaus vierittää B:n niin, että A:n osoitin näkyy."""
    a, b = kaksi
    _liikuta_riville(a)
    _vierita(b, 2500)
    k = _odota_kursori(b, "k.ulkona && k.kulma < -1")
    b.mouse.click(k["x"], k["y"])
    b.wait_for_function(f"scrollY + document.querySelector('header').getBoundingClientRect().bottom <= {AY}"
                        f" && {AY} <= scrollY + innerHeight", timeout=10000)


def test_koottu_ylapalkki_pallura_ylapalkin_alareunassa(kaksi):
    """B:n yläpalkki koottu, A:n hiiri navissa (B:llä piilossa) → pallura B:n yläpalkin
    alareunassa samassa x:ssä, ei nuolta."""
    a, b = kaksi
    b.click("#valikkovihje")
    b.wait_for_function("document.querySelector('header').classList.contains('koottu')")
    laatikko = a.locator("#paanav button[data-polku='/kurssit']").bounding_box()
    ax, ay = laatikko["x"] + laatikko["width"] / 2, laatikko["y"] + laatikko["height"] / 2
    _liikuta(a, ax, ay)
    k = _odota_kursori(b, f"!k.ulkona && Math.abs(k.x - {ax}) < 2 && k.ala - {REUNA} <= k.y && k.y <= k.ala")
    assert ay > k["ala"]  # A:n kohta on B:n kootun yläpalkin alapuolella


def test_kiinnitetyn_palkin_alla_reunapallura_palkin_alapuolella(kaksi):
    """B vierittänyt alas → sivutuspalkki jumittunut yläpalkin alle; A ylhäällä → reunapallura
    palkin alla, ei sivutusnappien päällä (#106)."""
    a, b = kaksi
    _liikuta_riville(a)
    _vierita(b, 2500)
    k = _odota_kursori(b, f"k.ulkona && k.kulma < -1 && k.palkki.bottom < k.y && k.y <= k.palkki.bottom + {REUNA} + 10")
    assert k["palkki"]["top"] <= k["ylapalkki"] + 1  # palkki todella jumittunut


def test_kiinnitetyssa_palkissa_oleva_nakyy_palkissa(kaksi):
    """A osoittaa sivutusta eri vierityksellä kuin B → B:llä pallura B:n palkissa samassa
    kohdassa palkin suhteen, ei reunapallurana."""
    a, b = kaksi
    _vierita(a, 2000)
    nappi = a.locator(".kiinnitetyt:visible .sivutus button").first.bounding_box()
    palkki_a = a.locator(".kiinnitetyt:visible").bounding_box()
    ax, ay = nappi["x"] + nappi["width"] / 2, nappi["y"] + nappi["height"] / 2
    _liikuta(a, ax, ay)
    k = _odota_kursori(b, f"!k.ulkona && Math.abs(k.x - {ax}) < 2"
                          f" && Math.abs(k.y - k.palkki.top - {ay - palkki_a['y']}) < 2")
    assert k["palkki"]["top"] > k["ylapalkki"] + 1  # B ylhäällä: palkki eri kohdassa kuin A:lla
