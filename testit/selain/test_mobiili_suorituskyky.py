"""Mobiilinäkymän suorituskyky: puhelimen kokoinen kosketusnäyttö + CPU hidastettuna 4×
(keskitason puhelin). Mittarit Long Tasks- ja Event Timing -rajapinnoista.

Tavallinen ajo (`./testit/selaintesti.sh`) mittaa siemendataa (~900 kurssia) regressiovahtina.
Tuotantokokoinen data (perf-kanta, ~32 k kurssia): käynnistä WebUI sitä vasten ja
  SELAIN_POHJA=http://127.0.0.1:18766 ./testit/selaintesti.sh -m suorituskyky -s
(-s tulostaa mittaukset). Rajat ovat puhelimen käyttökokemuksen rajoja, eivät koneen."""
import os

import pytest

pytestmark = pytest.mark.suorituskyky

CPU_HIDASTUS = 4
TUOTANTO = bool(os.environ.get("SELAIN_POHJA"))
VASTE_MS = 100          # napautuksesta seuraavaan piirtoon (koettu välittömäksi)
PISIN_JUMI_MS = 300     # pisin pääsäikeen tehtävä listan rakentuessa (hidastettuna)
KURSSIT_RIVI = "#kurssit-rungot tr.kurssi-rivi"

# Mittarit talteen ennen sivun omaa koodia: pitkät tehtävät ja syötteiden vasteajat.
_MITTARIT = """
window.__jumit = []; window.__vasteet = [];
new PerformanceObserver((l) => l.getEntries().forEach((e) => __jumit.push(e.duration)))
  .observe({ type: "longtask", buffered: true });
new PerformanceObserver((l) => l.getEntries().forEach((e) =>
  __vasteet.push({ tyyppi: e.name, kesto: e.duration })))
  .observe({ type: "event", durationThreshold: 16, buffered: true });
"""


@pytest.fixture
def puhelin(selain, pohja):
    """puhelin(polku, odota) → sivu puhelimen kokoisena (390×844, kosketus, CPU 4× hitaampi);
    tyopoyta=True → 1280×800 samalla CPU-hidastuksella (vertailukohta)."""
    kontekstit, virheet = [], []

    def uusi(polku, odota=None, tyopoyta=False):
        k = (selain.new_context(viewport={"width": 1280, "height": 800}) if tyopoyta else
             selain.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3,
                                is_mobile=True, has_touch=True))
        kontekstit.append(k)
        k.add_init_script(_MITTARIT)
        sivu = k.new_page()
        sivu.on("pageerror", lambda e: virheet.append(str(e)))
        k.new_cdp_session(sivu).send("Emulation.setCPUThrottlingRate", {"rate": CPU_HIDASTUS})
        sivu.goto(pohja + polku)
        if odota:
            sivu.wait_for_selector(odota, timeout=60000)
        return sivu

    yield uusi
    for k in kontekstit:
        k.close()
    assert not virheet, f"JS-virheet sivulla: {virheet}"


def _vaste(sivu, toiminto):
    """Ajaa toiminnon (napautus) ja palauttaa pisimmän syötteen vasteajan (ms) seuraavaan piirtoon."""
    sivu.evaluate("__vasteet.length = 0")
    toiminto()
    sivu.wait_for_timeout(500)  # Event Timing -merkintä valmistuu piirron jälkeen
    return max([v["kesto"] for v in sivu.evaluate("__vasteet")] or [0])


def _kurssit_valmiina(sivu):
    sivu.wait_for_function(f"""!kurssit_kesken && kurssit_jarjestyksessa.length > 0
        && document.querySelectorAll("{KURSSIT_RIVI}").length === kurssit_jarjestyksessa.length""",
                           timeout=180000, polling=500)


@pytest.mark.parametrize("tyopoyta", [False, True], ids=["puhelin", "tyopoyta"])
def test_kurssit_lista_rakentuu_jumittamatta(puhelin, tyopoyta):
    """Koko Kurssit-lista erissä DOMiin: ei pitkiä jumeja (napautukset vastaavat latauksen aikanakin).
    Työpöytä vertailuna: mobiilin piilotetut solut eivät saa hidastaa sitä."""
    s = puhelin("/kurssit", KURSSIT_RIVI, tyopoyta=tyopoyta)
    ensimmaiset = s.evaluate("performance.now()")
    _kurssit_valmiina(s)
    valmis = s.evaluate("performance.now()")
    jumit = s.evaluate("__jumit")
    rivit = s.evaluate(f'document.querySelectorAll("{KURSSIT_RIVI}").length')
    tbt = sum(max(0, j - 50) for j in jumit)
    print(f"\n[kurssit {'työpöytä' if tyopoyta else 'puhelin'}] {rivit} riviä: ensimmäiset {ensimmaiset:.0f} ms, valmis {valmis:.0f} ms, "
          f"pisin jumi {max(jumit, default=0):.0f} ms, TBT {tbt:.0f} ms ({len(jumit)} jumia)")
    assert max(jumit, default=0) <= PISIN_JUMI_MS


def test_valikko_aukeaa_heti_eika_siirra_sisaltoa(puhelin):
    """Hampurilaisvalikko: vaste ≤ 100 ms myös täyden kurssilistan päällä, eikä sisältö siirry
    (siirtyminen = koko listan uudelleenasettelu)."""
    s = puhelin("/kurssit", KURSSIT_RIVI)
    _kurssit_valmiina(s)
    rivi_ennen = s.locator(KURSSIT_RIVI).first.bounding_box()
    auki = _vaste(s, lambda: s.tap("#mobiilivalikko-nappi"))
    assert s.is_visible("#paanav") and s.is_visible("#nimimerkki-kentta")
    assert s.locator(KURSSIT_RIVI).first.bounding_box() == rivi_ennen
    kiinni = _vaste(s, lambda: s.tap("#mobiilivalikko-nappi"))
    assert not s.is_visible("#paanav")
    print(f"\n[valikko] auki {auki:.0f} ms, kiinni {kiinni:.0f} ms")
    assert auki <= VASTE_MS and kiinni <= VASTE_MS


def test_tasotagin_selite_aukeaa_heti(puhelin):
    s = puhelin("/kurssit", KURSSIT_RIVI)
    _kurssit_valmiina(s)
    tagi = s.locator(f"{KURSSIT_RIVI} .taso-tagi").first
    vaste = _vaste(s, lambda: tagi.tap())
    assert s.locator(".taso-tagi.auki").count() == 1
    print(f"\n[tasotagi] {vaste:.0f} ms")
    assert vaste <= VASTE_MS


def test_pitka_lista_vierittyy_sujuvasti(puhelin):
    """Kosketusvieritys täyden listan yli: ruutuvälien 95. persentiili (hidastettuna)."""
    s = puhelin("/kurssit", KURSSIT_RIVI)
    _kurssit_valmiina(s)
    s.evaluate("""window.__ruudut = []; (function f(t) { __ruudut.push(t); requestAnimationFrame(f); })(0)""")
    cdp = s.context.new_cdp_session(s)
    cdp.send("Input.synthesizeScrollGesture", {"x": 200, "y": 600, "yDistance": -6000, "speed": 3000,
                                               "gestureSourceType": "touch"})
    ruudut = s.evaluate("__ruudut.slice(2)")
    valit = sorted(b - a for a, b in zip(ruudut, ruudut[1:]))
    p95 = valit[int(len(valit) * 0.95)] if valit else 0
    print(f"\n[vieritys] {len(valit)} ruutua, ruutuväli p95 {p95:.0f} ms, pisin {valit[-1] if valit else 0:.0f} ms, "
          f"vieritetty {s.evaluate('scrollY'):.0f} px")
    assert s.evaluate("scrollY") > 1000
    assert p95 <= 50
