"""XSS-hyötykuormat näkyvät tekstinä eivätkä suoritu; raportti ei tyhjene pollauksen ajaksi;
jumittunut haku toipuu aikarajan jälkeen."""
import json
import urllib.parse

import pytest

from testit.selain.conftest import SLUG, _db_asetukset

KUORMA = '<img src=x onerror="window.__xss=(window.__xss||0)+1">XSSTESTI'
# Palvelin välittää nimimerkin muille vain ≤ 40 merkkisenä (yhteistyo.py, #100).
NIMI_KUORMA = "<img src=x onerror=__xss=1>XSSTESTI"
KURSSIT = f"/tutkimukset/{SLUG}/kurssit-valittu"
RIVI = "#tutkimus-kurssit-rungot tr.kurssi-rivi"

# (taulu, sarake, ehto): kentät, joihin kuorma kirjoitetaan yhdelle mukana olevalle kurssille
KENTAT = [("Kurssi", "KurssiNimi", "KID = %(kid)s"), ("Kurssi", "Oppiaine", "KID = %(kid)s"),
          ("Kurssiluokitus", "Luokitteluperuste", "KID = %(kid)s"),
          ("Vastaukset", "Vastaus", "KID = %(kid)s AND KysID = 5"),
          ("Tutkimus", "Luokittelukehote", "TID = 1"), ("Tutkimus", "Arviointikehote", "TID = 1"),
          ("RaporttiOsio", "Teksti", "OsioAvain = 'johdanto'")]


@pytest.fixture(scope="module")
def kuorma(kanta):
    """Kirjoittaa kuorman KENTAT-sarakkeisiin ja palauttaa alkuperäiset arvot lopuksi."""
    import mysql.connector
    yht = mysql.connector.connect(**_db_asetukset(), database=kanta, autocommit=True)
    k = yht.cursor()
    k.execute("SELECT MIN(KID) FROM Kurssiluokitus WHERE Mukana = 1")
    p = {"kid": k.fetchone()[0]}
    vanhat = []
    for taulu, sarake, ehto in KENTAT:
        k.execute(f"SELECT {sarake} FROM {taulu} WHERE {ehto}", p)
        vanhat.append(k.fetchone()[0])
        k.execute(f"UPDATE {taulu} SET {sarake} = CONCAT(%(kuorma)s, ' ', {sarake}) WHERE {ehto}",
                  {**p, "kuorma": KUORMA})
    yield p["kid"]
    for (taulu, sarake, ehto), arvo in zip(KENTAT, vanhat):
        k.execute(f"UPDATE {taulu} SET {sarake} = %(arvo)s WHERE {ehto}", {**p, "arvo": arvo})
    yht.close()


def _xss(sivu):
    return sivu.evaluate("window.__xss || 0")


def test_kurssilista_ja_modaalit_nayttavat_kuorman_tekstina(kayttaja, kuorma):
    """Kurssirivi, HITL-modaalin perustelu ja kurssimodaali: kuorma tekstinä, ei suoritu."""
    a = kayttaja(KURSSIT, RIVI)
    a.evaluate("luokitus_suodatin.hakusana = 'XSSTESTI'; lataaTilaSivu(true)")
    a.wait_for_function("document.querySelector('#tutkimus-kurssit-rungot').textContent.includes('XSSTESTI')")
    assert "<img" in a.inner_text("#tutkimus-kurssit-rungot")
    a.click("#tutkimus-kurssit-rungot .hitl-nappi")
    a.wait_for_selector("#hitl-ai-perustelu-osio:has-text('XSSTESTI')")
    assert "<img" in a.inner_text("#hitl-ai-perustelu-osio")
    a.evaluate("suljeHitlModaali()")
    a.click(f"{RIVI} td:first-child")
    a.wait_for_selector("#modaali:not(.piilotettu):has-text('XSSTESTI')")
    assert "<img" in a.inner_text("#modaali")
    assert _xss(a) == 0


def test_arvioinnit_ja_tiedot_eivat_suorita_kuormaa(kayttaja, kuorma):
    """Arviointivastaus ja tutkimuksen kehotteet näkyvät tekstinä."""
    a = kayttaja(f"/tutkimukset/{SLUG}/arvioinnit")
    a.wait_for_function("arvioinnit_data && !arvioinnit_kesken", timeout=60000)
    a.evaluate("arvioinnit_suodatin.hakusana = 'XSSTESTI'; renderArvioinnitTaulu()")
    a.wait_for_selector("#tutkimus-arvioinnit-sisalto td:has-text('XSSTESTI')")
    assert "<img" in a.inner_text("#tutkimus-arvioinnit-sisalto")
    a.goto(a.url.replace("/arvioinnit", "/tiedot"))
    a.wait_for_selector("#tutkimus-tiedot-sisalto pre:has-text('XSSTESTI')")
    assert "<img" in a.inner_text("#tutkimus-tiedot-sisalto")
    assert _xss(a) == 0


def test_raportti_kuorma_tekstina_eika_tyhjene_pollauksessa(kayttaja, kuorma):
    """Raporttiosio näkyy tekstinä; hidas taustapäivitys ei tyhjennä osioita haun ajaksi."""
    a = kayttaja(f"/tutkimukset/{SLUG}/raportti", ".raportti-osio")
    a.wait_for_selector("#raportti-sisalto:has-text('XSSTESTI')")
    assert "<img" in a.inner_text("#raportti-sisalto")
    assert _xss(a) == 0
    a.evaluate("""() => { const f = window.fetch; window.__viivytetty = 0;
      window.fetch = (u, ...x) => String(u).endsWith('/raportti')
        ? (window.__viivytetty++, new Promise((ok) => setTimeout(() => ok(f(u, ...x)), 3000))) : f(u, ...x); }""")
    a.evaluate("window.__paivitys = _paivitaNakyma()")
    a.wait_for_function("window.__viivytetty > 0")
    assert a.locator(".raportti-osio").count() > 0
    a.evaluate("window.__paivitys")
    assert a.locator(".raportti-osio").count() > 0


def test_nimimerkki_raporttimuokkaimessa_tekstina(kayttaja, pohja, kuorma):
    """Toisen käyttäjän kuormaa sisältävä nimimerkki näkyy muokkaajissa tekstinä + ympyrä piirretty."""
    a = kayttaja(f"/tutkimukset/{SLUG}/raportti", ".raportti-osio")
    profiili = {"nimimerkki": NIMI_KUORMA,"taustavari": "#c0392b", "etualavari": "#ffffff",
                "bitmappi": [24, 60, 126, 219, 255, 90, 129, 66]}
    b = kayttaja("/")
    b.context.add_cookies([{"name": "opserverKayttaja", "url": pohja,
                            "value": urllib.parse.quote(json.dumps(profiili))}])
    b.goto(f"{pohja}/tutkimukset/{SLUG}/raportti")
    b.wait_for_selector(".raportti-osio")
    nappi = ".raportti-muokkaa-nappi[data-lomake$=':johdanto']"
    a.click(nappi)
    b.click(nappi)
    b.type("#raporttimuokkaus-tekstialue", "x")
    a.wait_for_selector("#raporttimuokkaus-modaali .lomake-muokkaajat:has-text('XSSTESTI')")
    assert "<img" in a.inner_text("#raporttimuokkaus-modaali .lomake-muokkaajat")
    assert a.evaluate("""() => { const c = document.querySelector('#raporttimuokkaus-modaali .lomake-muokkaaja canvas');
      return !!c && c.getContext('2d').getImageData(7, 7, 1, 1).data[3] > 0; }""")
    assert _xss(a) == 0 and _xss(b) == 0


def test_jumittunut_haku_toipuu_aikarajan_jalkeen(kayttaja):
    """Ensimmäinen luokitushaku ei vastaa koskaan → haeJson katkaisee ja yrittää uudelleen."""
    a = kayttaja("/")
    ohitettu = []

    def jumi(reitti):
        if not ohitettu:
            ohitettu.append(reitti)  # ei vastausta koskaan
            return
        reitti.continue_()
    a.route("**/luokitukset?*", jumi)
    a.goto(a.url.rstrip("/") + KURSSIT)
    a.wait_for_selector(RIVI, timeout=60000)
    assert ohitettu
