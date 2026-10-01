"""Muiden käyttäjien pallurat: yläpalkin tooltip kertoo tekemisen, muut pallurat pelkän
nimimerkin; yläpalkin palluran klikkaus vie toisen luo (sivu, näkymä, sivutussivu, modaali)."""
import json
import re

from playwright.sync_api import expect

from testit.selain.conftest import SLUG

TUTKIMUS = f"/tutkimukset/{SLUG}"
VALITUT = f"{TUTKIMUS}/kurssit-valittu"
RIVI = "#tutkimus-kurssit-rungot tr.kurssi-rivi"
YLAPALKKI = "#muut-ympyrat canvas[data-id]"
ARVIO_RIVI = "#tutkimus-arvioinnit-sisalto tr.kurssi-rivi"


def _nimi(sivu):
    return sivu.evaluate("omaNimimerkki()")


def _odota_tekeminen(b, nimi, kuvaus):
    """B:n yläpalkin pallura = "nimimerkki: kuvaus…" (kuvaus alkuosana)."""
    expect(b.locator(YLAPALKKI)).to_have_attribute(
        "data-tooltip", re.compile("^" + re.escape(f"{nimi}: {kuvaus}")), timeout=10000)


def _hover(sivu, valitsin):
    """Hiiri valitsimen ensimmäisen näkyvän elementin keskelle → tooltipin teksti tai None."""
    keski = None
    for _ in range(50):  # pallura voi olla vielä liukumassa / piirtymässä
        keski = sivu.evaluate("""(v) => { const c = [...document.querySelectorAll(v)]
          .find((e) => e.getBoundingClientRect().width > 0); if (!c) return null;
          const r = c.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }""", valitsin)
        if keski:
            break
        sivu.wait_for_timeout(200)
    assert keski, f"ei palluraa: {valitsin}"
    sivu.wait_for_timeout(600)  # siirtymäanimaatio (0.5 s) loppuun
    keski = sivu.evaluate("""(v) => { const r = [...document.querySelectorAll(v)]
      .find((e) => e.getBoundingClientRect().width > 0).getBoundingClientRect();
      return [r.left + r.width / 2, r.top + r.height / 2]; }""", valitsin)
    sivu.mouse.move(keski[0] + 3, keski[1] + 3)
    sivu.mouse.move(*keski)
    tt = sivu.locator("#nimis-tooltip")
    return tt.inner_text() if tt.is_visible() else None


def _tila(sivu):
    return sivu.evaluate("""({polku: location.pathname, nakyma: window.omaNakyma?.() ?? null,
      sivunumero: window.omaSivunumero?.() ?? null, modaali: window.omaModaali?.() ?? null})""")


def _siirry(a, b):
    """B klikkaa A:n yläpalkin palluraa (kun A:n nykyinen tila on ehtinyt B:lle);
    odottaa että B:n tila = A:n tila. (Tila JSONina: wait_for_function välittää None → undefined.)"""
    tila = json.dumps(list(_tila(a).values()), separators=(",", ":"), ensure_ascii=False)
    b.wait_for_function("(t) => muutKayttajat.some((k) => t === JSON.stringify("
                        "[k.sivu, k.nakyma ?? null, k.sivunumero ?? null, k.lomake ?? k.katselu ?? null]))",
                        arg=tila, timeout=10000)
    b.locator(YLAPALKKI).click()
    for _ in range(75):
        if _tila(b) == _tila(a):
            return
        b.wait_for_timeout(200)
    assert _tila(b) == _tila(a)


def test_ylapalkin_pallura_kertoo_sivun(kayttaja):
    """Yläpalkin pallurassa toisen nimimerkki + mitä sivua hän katsoo."""
    a, b = kayttaja("/korkeakoulut", "#paanav"), kayttaja("/korkeakoulut", "#paanav")
    nimi = _nimi(a)
    tutkimuksessa = 'tutkimuksessa "Kansallinen'
    for polku, kuvaus in [("/korkeakoulut", "Katsoo Korkeakoulut-sivua"), ("/kurssit", "Katsoo Kurssit-sivua"),
                          ("/tutkimukset", "Katsoo Tutkimukset-sivua"),
                          (TUTKIMUS, 'Katsoo tutkimusta "Kansallinen'),
                          (VALITUT, f"Katsoo valittuja kursseja {tutkimuksessa}"),
                          (f"{TUTKIMUS}/kurssit-hylatty", f"Katsoo hylättyjä kursseja {tutkimuksessa}"),
                          (f"{TUTKIMUS}/kurssit-odottaa", f"Katsoo odottavia kursseja {tutkimuksessa}"),
                          (f"{TUTKIMUS}/arvioinnit", f"Katsoo arviointeja {tutkimuksessa}"),
                          (f"{TUTKIMUS}/raportti", f"Katsoo raporttia {tutkimuksessa}")]:
        a.evaluate("(p) => navigoi(p)", polku)
        _odota_tekeminen(b, nimi, kuvaus)
    assert _hover(b, YLAPALKKI).startswith(f"{nimi}: Katsoo raporttia")


def test_ylapalkin_pallura_kertoo_avoimen_modaalin(kayttaja):
    """Avoin katselumodaali tai jaettu lomake näkyy toisen yläpalkin pallurassa."""
    a, b = kayttaja(VALITUT, RIVI), kayttaja("/korkeakoulut", "#paanav")
    nimi = _nimi(a)
    a.locator(f"{RIVI} td").first.click()
    a.wait_for_selector("#modaali:not(.piilotettu)")
    _odota_tekeminen(b, nimi, 'Katsoo kurssia "')
    a.click("#modaali .modaali-sulje")
    a.locator("#tutkimus-kurssit-rungot .hitl-nappi").first.click()
    _odota_tekeminen(b, nimi, 'Muokkaa luokittelua kurssille "')
    a.click("#hitl-modaali .modaali-sulje")
    a.click("#info-nappi")
    _odota_tekeminen(b, nimi, "Katsoo Opserver-infosivua")
    a.click("#info-modaali .modaali-sulje")
    a.evaluate("(p) => navigoi(p)", f"{TUTKIMUS}/arvioinnit")
    a.locator("#tutkimus-arvioinnit-sisalto button[data-lomake]").first.click(timeout=30000)
    _odota_tekeminen(b, nimi, 'Muokkaa arviointia kurssille "')
    a.click("#arviointimuokkaus-modaali .modaali-sulje")
    a.evaluate("(p) => navigoi(p)", f"{TUTKIMUS}/raportti")
    a.locator(".raportti-muokkaa-nappi").first.click(timeout=30000)
    _odota_tekeminen(b, nimi, 'Muokkaa raporttia tutkimuksessa "Kansallinen')
    a.click("#raporttimuokkaus-peruuta")
    _odota_tekeminen(b, nimi, "Katsoo raporttia")


def test_muut_pallurat_nayttavat_vain_nimimerkin(kayttaja):
    """Leijuva kursori, nav-, välilehti-, sivutus- ja lomakepallurat: tooltip = pelkkä nimimerkki."""
    a, b = kayttaja(VALITUT, RIVI), kayttaja(VALITUT, RIVI)
    nimi = _nimi(a)
    a.mouse.move(500, 300)
    assert _hover(b, "#kursori-kerros .vieras-kursori canvas") == nimi
    a.evaluate("navigoi('/kurssit')")
    assert _hover(b, "#nav-indikaattorit canvas") == nimi
    a.evaluate("(p) => navigoi(p)", VALITUT)
    a.wait_for_selector(RIVI)
    a.locator(".nakyma.aktiivinen .nakyma-valilehti", has_text="+").first.click()
    assert _hover(b, ".nakyma.aktiivinen .nakyma-valilehti .nakyma-pallura") == nimi
    a.locator(".nakyma.aktiivinen .nakyma-valilehti", has_text="Kaikki").first.click()
    a.locator(".nakyma.aktiivinen .tutkimus-kurssit-sivutus button", has_text="2").first.click()
    assert _hover(b, ".tutkimus-kurssit-sivutus .nakyma-pallura") == nimi
    a.locator(".nakyma.aktiivinen .tutkimus-kurssit-sivutus button", has_text="1").first.click()
    a.wait_for_function("window.omaSivunumero() === 0")  # 0-pohjainen
    a.locator(f"{RIVI} td").first.click()
    a.wait_for_selector("#modaali:not(.piilotettu)")
    assert _hover(b, "#tutkimus-kurssit-rungot .lomake-pallurat canvas") == nimi  # kurssin nimen vieressä
    a.click("#modaali .modaali-sulje")
    a.locator("#tutkimus-kurssit-rungot .hitl-nappi").first.click()
    assert _hover(b, "#tutkimus-kurssit-rungot .lomake-pallurat canvas") == nimi  # HITL-napin vieressä


def test_modaalissa_vain_modaalin_pallurat_reagoivat(kayttaja):
    """Jaetussa lomakkeessa muokkaajarivin ja tekstikursorin tooltip näkyy, taustan yläpalkin ei."""
    a, b = kayttaja(VALITUT, RIVI), kayttaja(VALITUT, RIVI)
    nimi = _nimi(a)
    a.locator("#tutkimus-kurssit-rungot .hitl-nappi").first.click()
    a.wait_for_selector("#hitl-modaali:not(.piilotettu)")
    b.locator("#tutkimus-kurssit-rungot .hitl-nappi").first.click()
    a.click("#hitl-perustelu")
    a.keyboard.type("abc")
    assert _hover(b, "#hitl-modaali .lomake-muokkaaja canvas") == nimi
    assert _hover(b, "#hitl-modaali .lomake-kursori canvas") == nimi
    assert _hover(b, YLAPALKKI) is None
    b.mouse.move(640, 790)
    expect(b.locator("#nimis-tooltip")).to_be_hidden()


def test_klikkaus_menee_kursorin_lapi(kayttaja):
    """Toisen leijuva kursori napin päällä ei estä napin klikkausta."""
    a, b = kayttaja(VALITUT, RIVI), kayttaja(VALITUT, RIVI)
    nappi = b.locator("#s-tutkimus-kurssit .tila-nappi[data-tila='odottaa']").bounding_box()
    x, y = nappi["x"] + nappi["width"] / 2, nappi["y"] + nappi["height"] / 2
    a.mouse.move(x + 3, y)
    a.mouse.move(x, y)
    b.wait_for_function("""([x, y]) => { const k = document.querySelector('#kursori-kerros .vieras-kursori canvas');
      if (!k) return false; const r = k.getBoundingClientRect();
      return r.left <= x && x <= r.right && r.top <= y && y <= r.bottom; }""", arg=[x, y], timeout=10000)
    b.mouse.click(x, y)
    b.wait_for_function("location.pathname.endsWith('/kurssit-odottaa')", timeout=10000)


def test_siirtyminen_toisen_nakymaan_sivulle_ja_lomakkeeseen(kayttaja):
    """Eri sivu + oma suodatinnäkymä + sivutussivu + avoin HITL-lomake → B liittyy samaan lomakkeeseen."""
    a, b = kayttaja(f"{TUTKIMUS}/kurssit-hylatty", RIVI), kayttaja("/korkeakoulut", "#paanav")
    a.locator(".nakyma.aktiivinen .nakyma-valilehti", has_text="+").first.click()
    a.select_option("#tutkimus-kurssit-suodatin .suod-koulu", index=1)
    a.click(".nakyma-luo")
    a.wait_for_selector(RIVI)
    a.locator(".nakyma.aktiivinen .tutkimus-kurssit-sivutus button", has_text="2").first.click()
    a.wait_for_function("window.omaSivunumero() === 1")  # 0-pohjainen
    a.wait_for_selector(RIVI)
    a.locator("#tutkimus-kurssit-rungot .hitl-nappi").nth(3).click()
    a.click("#hitl-perustelu")
    a.keyboard.type("A:n perustelu")
    _siirry(a, b)
    assert _tila(a) == _tila(b) and _tila(b)["nakyma"] and _tila(b)["sivunumero"] == 1
    expect(b.locator("#hitl-perustelu")).to_have_value("A:n perustelu", timeout=10000)
    for s in (a, b):
        s.click("#hitl-modaali .modaali-sulje")


def test_siirtyminen_vierittaa_toisen_hiiren_kohdalle(kayttaja):
    """Samalla sivulla ilman modaalia: B vierittyy niin, että A:n hiiri on ruudun keskellä."""
    a, b = kayttaja(VALITUT, RIVI), kayttaja(VALITUT, RIVI)
    a.evaluate("scrollTo(0, 2500)")
    a.mouse.move(640, 400)
    a.mouse.move(650, 410)
    a_hiiri_y = a.evaluate("scrollY") + 410
    assert a_hiiri_y > 2000
    # A:n hiiri B:n ruudun alapuolella → reunapallura alareunassa
    b.wait_for_function("parseFloat(document.querySelector('#kursori-kerros .vieras-kursori.ulkona')?.style.top)"
                        " > innerHeight / 2", timeout=10000)
    b.locator(YLAPALKKI).click()
    b.wait_for_function("(y) => Math.abs(scrollY + innerHeight / 2 - y) < 20", arg=a_hiiri_y, timeout=10000)


def test_siirtyminen_avaa_saman_kurssimodaalin(kayttaja):
    """A katsoo kurssia arvioinneissa, B raportissa → B:lle aukeaa sama kurssi."""
    a, b = kayttaja(f"{TUTKIMUS}/arvioinnit", ARVIO_RIVI), kayttaja(f"{TUTKIMUS}/raportti", "#paanav")
    a.locator(ARVIO_RIVI).nth(5).locator("td").first.click(position={"x": 5, "y": 5})
    a.wait_for_selector("#modaali:not(.piilotettu)")
    _siirry(a, b)
    expect(b.locator("#modaali")).to_be_visible()
    expect(b.locator("#modaali-otsikko")).to_have_text(a.inner_text("#modaali-otsikko"))


def test_siirtyminen_kurssit_sivun_suodatettuun_nakymaan(kayttaja):
    """A Kurssit-sivun omassa näkymässä; B (ei vielä käynyt Kurssit-sivulla) saa samat suodattimet ja listan."""
    a = kayttaja("/kurssit", "#kurssit-rungot tr[data-kid]")
    a.wait_for_function("!kurssit_kesken && kaikki_kurssit.length > 0", timeout=30000)
    a.locator(".nakyma.aktiivinen .nakyma-valilehti", has_text="+").first.click()
    a.select_option("#suodatin-koulu", index=2)
    a.click(".nakyma-luo")
    a.wait_for_function("!kurssit_kesken && omaNakyma() !== '+'", timeout=30000)
    b = kayttaja("/tutkimukset", "#paanav")
    b.mouse.move(600, 400)
    _siirry(a, b)
    b.wait_for_function("!kurssit_kesken", timeout=30000)
    suodattimet = ("['suodatin-lukuvuosi', 'suodatin-koulu', 'kurssit-lkm']"
                   ".map((i) => { const e = document.getElementById(i); return e.value ?? e.textContent; })")
    assert a.evaluate(suodattimet)[1]
    expect(b.locator("#kurssit-lkm")).to_have_text(a.inner_text("#kurssit-lkm"))
    assert b.evaluate(suodattimet) == a.evaluate(suodattimet)
