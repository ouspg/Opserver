"""Arviointitaulun 15 s pollaus (#135): sama data ei rakenna taulua uudelleen (työpöydällä
koko <table>in asettelu ~240 ms CPU 4×), muuttunut data rakentaa."""
import json

from testit.selain.conftest import SLUG

ARV_RIVI = "#tutkimus-arvioinnit-sisalto tr.kurssi-rivi"


def test_pollaus_rakentaa_taulun_vain_kun_data_muuttui(kayttaja):
    s = kayttaja(f"/tutkimukset/{SLUG}/arvioinnit")
    s.wait_for_function("arvioinnit_data && !arvioinnit_kesken", timeout=60000)
    merkitse = f"document.querySelector('{ARV_RIVI}').merkki = 1"
    merkitty = f"document.querySelector('{ARV_RIVI}').merkki === 1"

    s.evaluate(merkitse)
    s.evaluate("paivitaArvioinnit()")
    assert s.evaluate(merkitty), "sama data rakensi taulun uudelleen"

    def muutettu(reitti):
        data = reitti.fetch().json()
        if data["kurssit"]:
            data["kurssit"][0]["KurssiNimi"] = "Muuttunut nimi"
        reitti.fulfill(content_type="application/json", body=json.dumps(data))
    s.route("**/arvioinnit?*", muutettu)
    s.evaluate("paivitaArvioinnit()")
    assert not s.evaluate(merkitty)
    assert s.locator(ARV_RIVI, has_text="Muuttunut nimi").count() > 0
