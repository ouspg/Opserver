""""N / M kurssia arvioitu" laskee myös ihmisen korjaamat vastaukset (sama kuin CLIUI):
kurssi, jonka LLM-vastaukset ovat tyhjiä mutta ihminen on vastannut, on arvioitu."""
from urllib.parse import parse_qs, urlparse

from testit.selain.conftest import SLUG

TYHJA = {"vastaus": "", "luokka": None, "pisteet": None, "lista": None}


def test_ihmisen_korjaus_lasketaan_arvioiduksi(kayttaja):
    def vain_korjaus(reitti):
        data = reitti.fetch().json()
        for k in data["kurssit"]:
            k["vastaukset"] = [dict(v, **TYHJA) for v in k["vastaukset"]]
            k["korjaukset"] = {}
        sivu = parse_qs(urlparse(reitti.request.url).query).get("sivu", ["0"])[0]
        if sivu == "0" and data["kurssit"] and data["kysymykset"]:  # vain yksi kurssi koko listasta
            kysid = str(data["kysymykset"][0]["KysID"])
            data["kurssit"][0]["korjaukset"] = {kysid: dict(TYHJA, vastaus="Ihmisen vastaus", nimi="Testaaja")}
        reitti.fulfill(json=data)

    s = kayttaja(f"/tutkimukset/{SLUG}/arvioinnit",
                 alustus=lambda k: k.route("**/arvioinnit?*", vain_korjaus))
    s.wait_for_function("arvioinnit_data && !arvioinnit_kesken", timeout=60000)
    teksti = s.locator("#tutkimus-arvioinnit-lkm").inner_text()
    assert teksti.startswith("1 / "), teksti
