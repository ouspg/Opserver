"""Kurssin paikannus (paikannus.js): autocomplete, näppäimet/klikkaus ja siirtyminen
oikealle riville — Kurssit-sivulla selaimessa, tutkimuksen listoissa palvelimelta oikealle sivulle."""
from playwright.sync_api import expect

from testit.selain.conftest import SLUG

KURSSIT = "/kurssit"
KURSSIT_SYOTE = "#kurssit-paikannus input"
KURSSIT_LISTA = "#kurssit-paikannus .paikannus-lista"
HYLATTY = f"/tutkimukset/{SLUG}/kurssit-hylatty"
HYLATTY_SYOTE = "#tutkimus-kurssit-paikannus input"
API = f"/api/tutkimukset/{SLUG}/luokitukset"


def _avaa_kurssit(kayttaja):
    s = kayttaja(KURSSIT)
    s.wait_for_function("!kurssit_kesken && kaikki_kurssit.length > 0", timeout=30000)
    return s


def _odota_paikannettu(s, runko, kid):
    """Rivi on näkymässä kokonaan ja korostettu."""
    s.wait_for_function(
        """([runko, kid]) => { const r = document.querySelector(`#${runko} tr[data-kid="${kid}"]`);
          if (!r || !r.classList.contains('paikannettu')) return false;
          const b = r.getBoundingClientRect(); return b.top >= 0 && b.bottom <= innerHeight; }""",
        arg=[runko, kid], timeout=10000)


def _ehdotukset(s, lista, vahintaan=1):
    s.wait_for_function("([v, n]) => document.querySelectorAll(v + ' li').length >= n",
                        arg=[lista, vahintaan], timeout=10000)
    return s.locator(f"{lista} li")


def test_kurssit_alusta_osuvat_ensin_ja_aksentiton(kayttaja):
    """Nimen alusta osuvat ehdotetaan ensin; haku ei välitä ääkkösistä (a = ä)."""
    s = _avaa_kurssit(kayttaja)
    osumat = s.evaluate("paikannaKurssit('ka', 100000).map((k) => taita(k.KurssiNimi).startsWith('ka'))")
    assert True in osumat and False in osumat
    assert osumat == sorted(osumat, reverse=True)
    s.fill(KURSSIT_SYOTE, "kayttojarj")
    tekstit = _ehdotukset(s, KURSSIT_LISTA).all_inner_texts()
    assert tekstit and all(t.startswith("Käyttöjärjestelmät") for t in tekstit)


def test_kurssit_enter_ja_tab_paikantavat_listan_loppupaahan(kayttaja):
    """Enter ja Tab (heti kirjoittamisen jälkeen) vierittävät kaukana olevan rivin näkyviin."""
    s = _avaa_kurssit(kayttaja)
    viimeinen, toiseksi = s.evaluate("[kurssit_jarjestyksessa.at(-1), kurssit_jarjestyksessa.at(-50)]")
    s.fill(KURSSIT_SYOTE, viimeinen["Koodi"])
    s.keyboard.press("Enter")
    _odota_paikannettu(s, "kurssit-rungot", viimeinen["KID"])
    expect(s.locator(KURSSIT_SYOTE)).to_have_value(viimeinen["KurssiNimi"])
    s.fill(KURSSIT_SYOTE, toiseksi["Koodi"])
    s.keyboard.press("Tab")
    _odota_paikannettu(s, "kurssit-rungot", toiseksi["KID"])


def test_kurssit_nuoli_klikkaus_ja_esc(kayttaja):
    """Nuoli alas + Enter valitsee toisen ehdotuksen, klikkaus kolmannen, Esc sulkee listan."""
    s = _avaa_kurssit(kayttaja)
    haku = "tieto"
    odotetut = s.evaluate(f"paikannaKurssit('{haku}').map((k) => k.KID)")
    assert len(odotetut) >= 3
    s.fill(KURSSIT_SYOTE, haku)
    _ehdotukset(s, KURSSIT_LISTA, 3)
    s.keyboard.press("ArrowDown")
    s.keyboard.press("Enter")
    _odota_paikannettu(s, "kurssit-rungot", odotetut[1])
    s.fill(KURSSIT_SYOTE, haku)
    _ehdotukset(s, KURSSIT_LISTA, 3).nth(2).click()
    _odota_paikannettu(s, "kurssit-rungot", odotetut[2])
    s.fill(KURSSIT_SYOTE, haku)
    _ehdotukset(s, KURSSIT_LISTA)
    s.keyboard.press("Escape")
    expect(s.locator(KURSSIT_LISTA)).to_be_hidden()


def test_hylatyt_enter_heti_siirtyy_viimeiselle_sivulle(kayttaja):
    """Tutkimuksen hylätyt: Enter heti kirjoittamisen jälkeen hakee palvelimelta ja vaihtaa
    oikealle sivulle (viimeinen sivu)."""
    s = kayttaja(HYLATTY, "#tutkimus-kurssit-rungot tr.kurssi-rivi")
    maara = s.evaluate(f"haeJson('{API}/maarat').then((m) => m['hylätty'])")
    viimeinen_sivu = (maara - 1) // 100
    assert viimeinen_sivu >= 2
    k = s.evaluate(f"haeJson('{API}?tila=hylätty&koko=100&sivu={viimeinen_sivu}').then((r) => r.at(-1))")
    s.fill(HYLATTY_SYOTE, k["Koodi"])
    s.keyboard.press("Enter")
    _odota_paikannettu(s, "tutkimus-kurssit-rungot", k["KID"])
    assert s.evaluate("tutkimus_sivu") == viimeinen_sivu


def test_hylatyt_paikannus_noudattaa_jarjestysta_ja_suodatinta(kayttaja):
    """Paikannus laskee sivun samasta näkymästä kuin lista: op-järjestys laskeva + koulusuodatin."""
    s = kayttaja(HYLATTY, "#tutkimus-kurssit-rungot tr.kurssi-rivi")
    s.click("#s-tutkimus-kurssit th[data-jarjesta=op] .jarjesta-nappi[data-suunta=laskeva]")
    s.wait_for_function("luokitus_jarjestys.sarake === 'op'")
    s.evaluate("luokitus_suodatin.kkid = 1; vaihdaSivu(0)")
    s.wait_for_selector("#tutkimus-kurssit-rungot tr.kurssi-rivi")
    k = s.evaluate(f"haeJson('{API}?tila=hylätty&kkid=1&jarjesta=op&suunta=laskeva&koko=100&sivu=1')"
                   ".then((r) => r.at(-1))")
    s.fill(HYLATTY_SYOTE, k["Koodi"])
    _ehdotukset(s, "#tutkimus-kurssit-paikannus .paikannus-lista")
    s.keyboard.press("Enter")
    _odota_paikannettu(s, "tutkimus-kurssit-rungot", k["KID"])
    assert s.evaluate("tutkimus_sivu") == 1


def test_plus_valilehti_piilottaa_paikannuksen(kayttaja):
    """"+"-välilehdellä (uuden näkymän luonti) ei ole listaa eikä paikannusta."""
    s = kayttaja(HYLATTY, "#tutkimus-kurssit-rungot tr.kurssi-rivi")
    expect(s.locator("#tutkimus-kurssit-paikannus")).to_be_visible()
    s.locator(".nakyma.aktiivinen .nakyma-valilehti", has_text="+").first.click()
    expect(s.locator("#tutkimus-kurssit-paikannus")).to_be_hidden()
