"""Modaalit: taustan vierityslukko ja katselumodaalien läsnäolo (kurssin tiedot, Opserver-info)
— muut näkevät avoimen modaalin ankkurin kohdalla vain samalla sivulla/näkymässä."""

import pytest

from testit.selain.conftest import SLUG

VALITUT = f"/tutkimukset/{SLUG}/kurssit-valittu"
ARVIOINNIT = f"/tutkimukset/{SLUG}/arvioinnit"
RIVI = "#tutkimus-kurssit-rungot tr.kurssi-rivi"
ARV_RIVI = "#tutkimus-arvioinnit-sisalto tr.kurssi-rivi"
EI_MERKKEJA = [False, 0]


def _merkit(s, avain):
    """[ankkuri sykkii, pikkupallurat ankkurin vieressä] tai None jos ankkuria ei ole."""
    return s.evaluate("""(avain) => { const a = document.querySelector(`[data-lomake="${avain}"]`);
      if (!a) return null; const r = a.nextElementSibling?.classList.contains('lomake-pallurat') ? a.nextElementSibling : null;
      return [a.classList.contains('lomake-auki'), r ? r.querySelectorAll('canvas').length : 0]; }""", avain)


def _isot(s):
    """Isot vieraat kursorit: lista ulkona-lippuja (reunapallura = True)."""
    return s.evaluate("[...document.querySelectorAll('#kursori-kerros .vieras-kursori')].map((e) => e.classList.contains('ulkona'))")


def _odota(s, lauseke, arg=None):
    s.wait_for_function(lauseke, arg=arg, timeout=10000)


def _odota_merkit(s, avain, odotettu):
    s.wait_for_function("""([avain, o]) => { const a = document.querySelector(`[data-lomake="${avain}"]`);
      if (!a) return false; const r = a.nextElementSibling?.classList.contains('lomake-pallurat') ? a.nextElementSibling : null;
      return a.classList.contains('lomake-auki') === o[0] && (r ? r.querySelectorAll('canvas').length : 0) === o[1]; }""",
                        arg=[avain, odotettu], timeout=10000)


def _avaa_kurssimodaali(s, rivi):
    rivi.locator("td").first.click(position={"x": 5, "y": 5})
    s.wait_for_selector("#modaali:not(.piilotettu)")
    return f"kurssi:{rivi.get_attribute('data-kid')}"


@pytest.mark.parametrize("modaali", ["modaali", "hitl-modaali", "info-modaali"])
def test_modaali_lukitsee_taustan_vierityksen(kayttaja, modaali):
    """Avoin modaali: tausta ei vieritä, modaali vierittyy; sulkemisen jälkeen tausta vierittyy taas."""
    s = kayttaja(VALITUT, RIVI, korkeus=400)  # matala ikkuna → lyhytkin modaali vierittyy
    avaa = {"modaali": lambda: s.locator(f"{RIVI} td").first.click(),
            "hitl-modaali": lambda: s.locator("#tutkimus-kurssit-rungot .hitl-nappi").first.click(),
            "info-modaali": lambda: s.click("#info-nappi")}[modaali]
    avaa()
    s.wait_for_selector(f"#{modaali}:not(.piilotettu)")
    if modaali == "info-modaali":
        s.wait_for_selector("#info-teksti h2")
    s.wait_for_timeout(300)  # avausklikkaus voi vierittää napin näkyviin
    alku = s.evaluate("scrollY")
    s.mouse.move(40, 380)
    s.mouse.wheel(0, 600)
    s.mouse.move(640, 200)
    s.mouse.wheel(0, 400)
    _odota(s, f"document.getElementById('{modaali}').scrollTop > 0")
    assert s.evaluate("scrollY") == alku
    s.click(f"#{modaali} .modaali-sulje")
    s.wait_for_selector(f"#{modaali}", state="hidden")
    s.mouse.wheel(0, 300)
    _odota(s, f"scrollY !== {alku}")


def test_kurssimodaalin_katselu_nakyy_samalla_sivulla(kayttaja):
    """Kurssimodaali (luokitukset): saman sivun käyttäjä näkee sykkivän nimen + palluran,
    ruudun ulkopuolella reunapalluran; eri sivulla ei mitään; sulkeminen poistaa merkit."""
    a, b = kayttaja(VALITUT, RIVI), kayttaja(VALITUT, RIVI)
    c = kayttaja(ARVIOINNIT, ARV_RIVI)
    avain = _avaa_kurssimodaali(a, a.locator(RIVI).first)
    _odota_merkit(b, avain, [True, 1])
    assert _isot(b) == []  # nimi näkyvissä → riittää pikkupallura
    b.evaluate("scrollTo(0, 3000)")
    _odota(b, "document.querySelectorAll('#kursori-kerros .vieras-kursori.ulkona').length === 1")
    assert _isot(b) == [True]
    assert _merkit(c, avain) in (None, EI_MERKKEJA) and _isot(c) == []
    a.click("#modaali .modaali-sulje")
    b.evaluate("scrollTo(0, 0)")
    _odota_merkit(b, avain, EI_MERKKEJA)
    _odota(b, "document.querySelectorAll('#kursori-kerros .vieras-kursori').length === 0")


def test_arviointien_kurssimodaali_nakyy_vain_arvioinneissa(kayttaja):
    """Arvioinnit-sivun kurssimodaali merkitsee nimen arvioinneissa, ei luokitussivulla."""
    a, c = kayttaja(ARVIOINNIT, ARV_RIVI), kayttaja(ARVIOINNIT, ARV_RIVI)
    b = kayttaja(VALITUT, RIVI)
    avain = _avaa_kurssimodaali(a, a.locator(ARV_RIVI).first)
    _odota_merkit(c, avain, [True, 1])
    assert _merkit(b, avain) in (None, EI_MERKKEJA)


def test_infomodaalin_katselu_nakyy_logossa_samalla_sivulla(kayttaja):
    """Opserver-info: logo sykkii + pallura saman sivun käyttäjällä, ei eri sivulla."""
    a = kayttaja(ARVIOINNIT, ARV_RIVI)
    b = kayttaja(VALITUT, RIVI)
    b.click("#info-nappi")
    b.wait_for_selector("#info-modaali:not(.piilotettu)")
    b2 = kayttaja(VALITUT, RIVI)  # liittyy vasta modaalin avauksen jälkeen
    _odota_merkit(b2, "info", [True, 1])
    assert _isot(b2) == []  # logo näkyvissä → ei isoa palluraa
    assert _merkit(a, "info") == EI_MERKKEJA


def test_kurssit_vanhan_version_avaus_merkitsee_rivin(kayttaja):
    """Kurssit-sivu: vanhemman lukuvuoden version avaus merkitsee rivin nimen muille."""
    a, c = kayttaja("/kurssit"), kayttaja("/kurssit")
    for s in (a, c):
        _odota(s, "!kurssit_kesken && kaikki_kurssit.length > 0")
    rivi = a.locator("#kurssit-rungot tr.kurssi-rivi:has(.vuosivalinta)").first
    kid = rivi.get_attribute("data-kid")
    rivi.locator(".vuosivalinta").select_option(index=1)
    rivi.locator("td").first.click(position={"x": 5, "y": 5})
    a.wait_for_selector("#modaali:not(.piilotettu)")
    c.evaluate(f"document.querySelector('[data-lomake=\"kurssi:{kid}\"]').scrollIntoView({{block: 'center'}})")
    _odota_merkit(c, f"kurssi:{kid}", [True, 1])
