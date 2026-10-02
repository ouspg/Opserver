"""Delegoidut klikkikäsittelijät (suorituskyky-PR): rivin klikkaus avaa kurssimodaalin,
rivin sisäiset napit/valinnat eivät; järjestys; muiden kursorit ja ympyrät."""

from testit.selain.conftest import SLUG

KURSSIT_RIVI = "#kurssit-rungot tr.kurssi-rivi"
LUOK_RIVI = "#tutkimus-kurssit-rungot tr.kurssi-rivi"
ARV_RIVI = "#tutkimus-arvioinnit-sisalto tr.kurssi-rivi"


def _ok(sivu, polku):
    """Hyväksynnät eivät kirjoita jaettuun kantaan; palauttaa kaapatut URL:t."""
    urlit = []

    def vastaa(reitti):
        urlit.append(reitti.request.url)
        reitti.fulfill(status=200, content_type="application/json", body='{"ok": true}')
    sivu.route(polku, vastaa)
    return urlit


def _modaalin_otsikko(sivu):
    sivu.wait_for_selector("#modaali:not(.piilotettu)", timeout=15000)
    otsikko = sivu.inner_text("#modaali-otsikko")
    sivu.click("#modaali-sulje")
    return otsikko


def test_kurssit_jarjestys_ja_rivin_klikkaus(kayttaja):
    """Kurssit-sivu: laskeva nimijärjestys suomen aakkosin, rivi avaa modaalin, vuosivalinta ei."""
    s = kayttaja("/kurssit")
    s.wait_for_function("!kurssit_kesken && kaikki_kurssit.length > 0")
    s.click("#s-kurssit th[data-jarjesta=nimi] .jarjesta-nappi[data-suunta=laskeva]")
    s.wait_for_function(f"document.querySelectorAll('{KURSSIT_RIVI}').length === kurssit_jarjestyksessa.length")
    nimet = s.eval_on_selector_all(f"{KURSSIT_RIVI} td:first-child", "e => e.map((x) => x.textContent)")
    assert nimet[0].startswith("Ö")  # siemen: "Öljyteollisuuden …" → ä/ö aakkosten lopussa
    assert s.evaluate("(n) => n.every((x, i) => i === 0 || LAJITTELIJA.compare(n[i - 1], x) >= 0)", nimet)
    solu = s.locator(KURSSIT_RIVI).first.locator("td").first
    nimi = solu.inner_text()
    solu.click()
    assert nimi in _modaalin_otsikko(s)
    s.locator(f"{KURSSIT_RIVI} .vuosivalinta").first.click()
    assert s.is_hidden("#modaali")


def test_tutkimuksen_kurssit_rivin_napit(kayttaja):
    """Rivi avaa modaalin; perustelupylpyrä, HITL- ja hyväksy-nappi eivät avaa kurssimodaalia."""
    s = kayttaja(f"/tutkimukset/{SLUG}/kurssit-valittu", LUOK_RIVI)
    hyvaksynnat = _ok(s, "**/hyvaksy")
    rivi = s.locator(LUOK_RIVI).first
    nimi = rivi.locator("td").first.inner_text()
    rivi.locator("td").first.click()
    assert nimi in _modaalin_otsikko(s)
    pylpyra = rivi.locator(".perustelu-pylpyra").first
    pylpyra.click()
    assert "auki" in pylpyra.get_attribute("class") and s.is_hidden("#modaali")
    s.locator("#tutkimus-kurssit-rungot .hitl-nappi").first.click()
    assert s.is_visible("#hitl-modaali") and s.is_hidden("#modaali")
    s.evaluate("suljeHitlModaali()")
    with s.expect_request("**/hyvaksy"):
        s.locator("#tutkimus-kurssit-rungot .hyvaksy-nappi").first.click()
    assert hyvaksynnat and s.is_hidden("#modaali")


def test_arvioinnit_rivin_napit(kayttaja):
    """Rivi avaa modaalin; korjausnappi avaa oikean kysymyksen; hyväksy osuu kysymykseen."""
    s = kayttaja(f"/tutkimukset/{SLUG}/arvioinnit")
    s.wait_for_function("arvioinnit_data && !arvioinnit_kesken", timeout=60000)
    hyvaksynnat = _ok(s, "**/hyvaksy")
    rivi = s.locator(ARV_RIVI).first
    nimi = rivi.locator("td").first.inner_text().split(" 🌐")[0]
    rivi.locator("td").first.click()
    assert nimi in _modaalin_otsikko(s)
    rivi.locator("td.arviointi-vastaus").nth(1).locator("button[data-lomake]").click()
    s.wait_for_selector("#arviointimuokkaus-modaali:not(.piilotettu)")
    assert s.inner_text("#arviointimuokkaus-otsikko") == s.evaluate("arvioinnit_data.kysymykset[1].Kysymys")
    assert s.is_hidden("#modaali")
    s.click("#arviointimuokkaus-peruuta")
    with s.expect_request("**/hyvaksy"):
        s.locator("#tutkimus-arvioinnit-sisalto .arvio-hyvaksy-nappi").first.click()
    assert "/kysymykset/" in hyvaksynnat[0] and s.is_hidden("#modaali")


def test_muiden_kursorit_ja_ympyrat(kayttaja):
    """Kaksi muuta hiirtä liikuttavaa käyttäjää → kaksi vieraskursoria ja kaksi yläpalkin ympyrää."""
    a = kayttaja("/tutkimukset")
    muut = [kayttaja("/tutkimukset") for _ in range(2)]
    for i, m in enumerate(muut):
        m.mouse.move(200 + 100 * i, 300)
    a.wait_for_function("document.querySelectorAll('#kursori-kerros .vieras-kursori').length === 2", timeout=15000)
    assert a.locator("#muut-ympyrat canvas").count() == 2
