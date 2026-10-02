"""Reititys: päänavigaatio, tutkimuksen alasivut ja tilavälilehdet napeilla, selaimen
takaisin-nappi. Ei JS- eikä konsolivirheitä."""
from testit.selain import siemen

LKM_ON = "(t) => document.getElementById('tutkimus-kurssit-lkm').textContent === t"


def _odotetut_maarat():
    """Tutkimuksen kurssit tiloittain siemen.py:n KID-numeroinnista (kaikki versiot kattavat lukuvuoden)."""
    maarat = {"mukana": 0, "hylätty": 0, "odottaa": 0}
    rivit = len(siemen.KOULUT) * (siemen.KURSSEJA + -(-siemen.KURSSEJA // 5))
    for kid in range(1, rivit + 1):
        tila = kid % 10
        maarat["mukana" if tila <= 1 else "hylätty" if tila <= 6 else "odottaa"] += 1
    return maarat


def test_navigointi_napeilla_kaikille_sivuille(kayttaja):
    """Päänavigaatio → kurssit → tutkimus → alasivut → tilat; määrät vastaavat dataa ja
    takaisin-nappi palaa edelliseen polkuun."""
    s = kayttaja("/korkeakoulut", "#korkeakoulut-rungot tr", leveys=1400, korkeus=900)
    konsoli = []
    s.on("console", lambda m: m.type == "error" and konsoli.append(m.text))
    assert s.locator("#korkeakoulut-rungot tr").count() == len(siemen.KOULUT)

    s.click("#paanav button[data-polku='/kurssit']")
    s.wait_for_function("!kurssit_kesken && kaikki_kurssit.length > 0", timeout=30000)
    assert s.locator("#kurssit-rungot tr.kurssi-rivi").count() > 0

    s.click("#paanav button[data-polku='/tutkimukset']")
    s.locator("#tutkimukset-rungot .tutkimus-nimi-solu").first.click()
    s.wait_for_selector("#tutkimus-tiedot-sisalto h2")
    assert s.is_visible("#s-tutkimus-tiedot")
    for alasivu, odota in [("kurssit", "#tutkimus-kurssit-rungot tr.kurssi-rivi"),
                           ("arvioinnit", "#tutkimus-arvioinnit-sisalto table"),
                           ("raportti", ".raportti-osio")]:
        s.click(f"#tutkimus-nav button[data-tutkimus-alasivu='{alasivu}']")
        s.wait_for_selector(odota)
        s.evaluate("_paivitaNakyma()")  # pollauskierros ei riko näkymää
        s.wait_for_selector(odota)

    s.click("#tutkimus-nav button[data-tutkimus-alasivu='kurssit']")
    s.wait_for_selector("#tutkimus-nav-tila:not(.piilotettu)")
    odotetut = _odotetut_maarat()
    for alasivu, tila in [("kurssit-odottaa", "odottaa"), ("kurssit-hylatty", "hylätty"),
                          ("kurssit-valittu", "mukana")]:
        s.click(f"#tutkimus-nav-tila .tila-nappi-nav[data-alasivu='{alasivu}']")
        s.wait_for_function(LKM_ON, arg=f"{odotetut[tila]} kurssia")
        assert s.evaluate("location.pathname").endswith(alasivu)

    s.go_back()
    s.wait_for_function("location.pathname.endsWith('kurssit-hylatty')")
    s.wait_for_function(LKM_ON, arg=f"{odotetut['hylätty']} kurssia")
    assert s.inner_text("#paivitysaika").startswith("Päivitetty")
    assert not konsoli, konsoli
