"""Yhteisten apureiden käyttökohdat (DRY-PR): profiilimuokkain, läsnäolopallurat, jaetut
HITL-lomakkeet, modaalien sulkeminen, suodatinnimet ja raportin tuloste."""
import json
import urllib.parse

from testit.selain import siemen
from testit.selain.conftest import SLUG

KURSSIT = f"/tutkimukset/{SLUG}/kurssit-valittu"
RIVI = "#tutkimus-kurssit-rungot tr.kurssi-rivi"
HITL_NAPPI = "#tutkimus-kurssit-rungot .hitl-nappi"


# Onko valitsimen canvasissa yksikin näkyvä pikseli.
PIIRRETTY_JS = """(v) => { const c = document.querySelector(v); if (!c) return false;
  const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
  for (let i = 3; i < d.length; i += 4) if (d[i]) return true; return false; }"""


def _piirretty(sivu, valitsin):
    return sivu.evaluate(PIIRRETTY_JS, valitsin)


def _odota_piirretty(sivu, valitsin):
    sivu.wait_for_function(PIIRRETTY_JS, arg=valitsin, timeout=15000)


def _ei_tallennusta(sivu):
    """HITL-tallennus ei kirjoita jaettuun kantaan."""
    sivu.route("**/hitl", lambda r: r.fulfill(status=200, content_type="application/json", body='{"ok": true}'))


def test_profiilimuokkain_vaihtaa_varit_ja_symbolin(kayttaja):
    """Värivalinnat ja uusi symboli päivittyvät profiiliin ja evästeeseen."""
    a = kayttaja(KURSSIT, RIVI)
    a.click("#oma-ympyra")
    tausta, etuala = a.locator("#tausta-varit .vari-nappula").nth(3), a.locator("#etuala-varit .vari-nappula").nth(2)
    tausta.click()
    etuala.click()
    profiili = a.evaluate("omaProfiili")
    assert profiili["taustavari"] == tausta.get_attribute("title")
    assert profiili["etualavari"] == etuala.get_attribute("title")
    assert a.locator("#tausta-varit .vari-nappula.valittu").count() == 1
    for _ in range(5):
        a.click("#arvo-uusi-symboli")
        if a.evaluate("omaProfiili.bitmappi") != profiili["bitmappi"]:
            break
    assert a.evaluate("omaProfiili.bitmappi") != profiili["bitmappi"]
    evaste = next(c["value"] for c in a.context.cookies() if c["name"] == "opserverKayttaja")
    assert json.loads(urllib.parse.unquote(evaste))["taustavari"] == profiili["taustavari"]
    a.click("#sulje-muokkaus")


def test_toisen_lasnaolo_nakyy_ylapalkissa_navissa_ja_valilehdella(kayttaja):
    """Toinen käyttäjä: ympyrä yläpalkissa, pallurat navissa, kursori; välilehden vaihto näkyy."""
    a, b = kayttaja(KURSSIT, RIVI), kayttaja(KURSSIT, RIVI)
    b.mouse.move(400, 400)
    _odota_piirretty(a, "#kursori-kerros .vieras-kursori canvas")
    assert _piirretty(a, "#muut-ympyrat canvas")
    assert a.locator("#nav-indikaattorit canvas").count() == 1
    assert a.locator("#tutkimus-nav-indikaattorit canvas").count() == 1
    b.locator(".nakyma-valilehti", has_text="+").first.click()
    _odota_piirretty(a, ".nakyma-valilehti .nakyma-pallura")


def test_jaetun_hitl_lomakkeen_pallurat_ja_sulkeminen(kayttaja):
    """B avaa HITL-lomakkeen → A näkee pallurat napin vieressä ja liittyessään modaalissa."""
    a, b = kayttaja(KURSSIT, RIVI), kayttaja(KURSSIT, RIVI)
    b.locator(HITL_NAPPI).first.click()
    _odota_piirretty(a, "#tutkimus-kurssit-rungot .lomake-pallurat canvas")
    a.locator(HITL_NAPPI).first.click()
    _odota_piirretty(a, "#hitl-modaali .lomake-muokkaaja canvas")
    assert not a.evaluate("window.lomakeOlenAloittaja()")
    b.click("#hitl-modaali .modaali-sulje")
    assert b.is_hidden("#hitl-modaali")


def test_hitl_tallennus_muistaa_nimen_ja_lahettaa_uutisen(kayttaja):
    """Yksin avattu HITL-lomake: nimi muistiin, muut saavat uutisen; nimi esitäytetään
    arviointimuokkaimeen, joka sulkeutuu ✕:llä ja taustaklikillä. Kurssimodaali sulkeutuu taustaklikillä."""
    a, b = kayttaja(KURSSIT, RIVI), kayttaja(KURSSIT, RIVI)
    _ei_tallennusta(a)
    a.locator(HITL_NAPPI).nth(1).click()
    a.wait_for_selector("#hitl-modaali:not(.piilotettu)")
    a.wait_for_function("window.lomakeOlenAloittaja()")
    a.fill("#hitl-nimi", "Testi Nimi")
    a.fill("#hitl-sahkoposti", "testi@example.com")
    a.fill("#hitl-perustelu", "perustelu")
    a.locator('input[name="hitl-juurisyy"]').first.check()
    a.click("#hitl-laheta")
    a.wait_for_selector("#hitl-modaali.piilotettu", state="attached", timeout=15000)
    assert a.evaluate("[hitl_nimi, localStorage.getItem('hitl_nimi')]") == ["Testi Nimi"] * 2
    b.wait_for_selector(f"#uutispalkki:has-text('{a.evaluate('omaNimimerkki()')}')", timeout=10000)

    a.locator(f"{RIVI} td").first.click()
    a.wait_for_selector("#modaali:not(.piilotettu)")
    a.mouse.click(5, 450)
    assert a.is_hidden("#modaali")

    a.goto(a.url.replace("/kurssit-valittu", "/arvioinnit"))
    a.wait_for_function("arvioinnit_data && !arvioinnit_kesken", timeout=60000)
    muokkain, korjaa = "#arviointimuokkaus-modaali", "#tutkimus-arvioinnit-sisalto button[data-lomake]"
    a.locator(korjaa).first.click()
    a.wait_for_selector(f"{muokkain}:not(.piilotettu)")
    assert a.input_value("#arvio-nimi") == "Testi Nimi"
    a.click(f"{muokkain} .modaali-sulje")
    assert a.is_hidden(muokkain)
    a.locator(korjaa).first.click()
    a.wait_for_selector(f"{muokkain}:not(.piilotettu)")
    a.mouse.click(5, 450)
    assert a.is_hidden(muokkain)


def test_suodatinnimi_ja_tasot_suomeksi(kayttaja):
    """Välilehden nimi suodattimesta; suodatinpalkin tasovalinnat."""
    a = kayttaja(f"/tutkimukset/{SLUG}/arvioinnit")
    a.wait_for_function("arvioinnit_data && !arvioinnit_kesken", timeout=60000)
    assert a.evaluate("suodatinNimi({taso: 'aine', hakusana: 'x'})") == 'Aineopinnot · "x"'
    tasot = a.eval_on_selector_all("#tutkimus-arvioinnit-suodatin .suod-taso option", "e => e.map((o) => o.textContent)")
    assert tasot[0] == "Kaikki tasot" and sorted(tasot[1:]) == sorted(siemen.TASOT)


def test_raportin_mittarit_nakymassa_ja_tulosteessa(kayttaja):
    """HITL-mittaritaulukko näkyy raportissa ja PDF-tulosteessa, luvut oikealle tasattuina."""
    a = kayttaja(f"/tutkimukset/{SLUG}/raportti", ".raportti-osio")
    a.wait_for_selector(".hitl-mittarit table.tilasto-taulu tr")
    rivit = a.locator(".hitl-mittarit table.tilasto-taulu tr").count()
    a.evaluate("window.print = () => {}")
    with a.expect_popup() as ikkuna:
        a.click("#raportti-pdf-nappi")
    tuloste = ikkuna.value
    tuloste.wait_for_load_state()
    assert tuloste.locator("table tr").count() >= rivit > 1
    assert tuloste.evaluate(
        "getComputedStyle(document.querySelector('table tr:nth-child(2) td:nth-child(2)')).textAlign") == "right"
