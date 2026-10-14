"""Mobiilinäkymä (≤ 600 px): yläpalkissa vain logo + hampurilaisnappi, navigointi/läsnäolo/
nimimerkki valikossa; kurssilistoissa koodi/taso/oppiaine/op yhtenä sarakkeena "6op [A] 🌐"
ja oppiaine nimen perässä. Suorituskyky: test_mobiili_suorituskyky.py."""
import re

from playwright.sync_api import expect

from testit.selain.conftest import SLUG

KURSSIT_RIVI = "#kurssit-rungot tr.kurssi-rivi"
VALITUT_RIVI = "#tutkimus-kurssit-rungot tr.kurssi-rivi"
PUHELIN = {"leveys": 390, "korkeus": 844}


def test_ylapalkissa_vain_logo_ja_valikkonappi(kayttaja):
    s = kayttaja("/kurssit", KURSSIT_RIVI, **PUHELIN)
    expect(s.locator("header h1.logo img")).to_be_visible()
    expect(s.locator("#mobiilivalikko-nappi")).to_be_visible()
    for piilossa in ("#paanav", "#oma-ympyra", "#nimimerkki-kentta", "#valikkovihje"):
        expect(s.locator(piilossa)).to_be_hidden()
    assert s.locator("header").bounding_box()["height"] < 70


def test_valikossa_navigointi_lasnaolo_ja_nimimerkki(kayttaja):
    kayttaja("/kurssit", KURSSIT_RIVI)  # toinen käyttäjä → pallura valikkoon
    s = kayttaja("/kurssit", KURSSIT_RIVI, **PUHELIN)
    s.click("#mobiilivalikko-nappi")
    expect(s.locator("#mobiilivalikko-nappi")).to_have_attribute("aria-expanded", "true")
    for nakyvissa in ("#paanav", "#oma-ympyra", "#nimimerkki-kentta", "#nollaa-nimimerkki"):
        expect(s.locator(nakyvissa)).to_be_visible()
    expect(s.locator("#muut-ympyrat canvas[data-id]")).to_have_count(1, timeout=10000)
    # Valikon kentät eivät mene ruudun yli
    assert s.locator("#nollaa-nimimerkki").bounding_box()["x"] + 10 < 390
    s.fill("#nimimerkki-kentta", "Puhelin")
    expect(s.locator("#paanav")).to_be_visible()  # muokkaus ei sulje valikkoa
    s.locator("#paanav button", has_text="Tutkimukset").click()
    expect(s).to_have_url(re.compile("/tutkimukset$"))
    expect(s.locator("#paanav")).to_be_hidden()
    s.click("#mobiilivalikko-nappi")
    s.keyboard.press("Escape")
    expect(s.locator("#paanav")).to_be_hidden()


def test_kurssilistan_yhdistetty_sarake_ja_oppiaine_nimessa(kayttaja):
    s = kayttaja("/kurssit", KURSSIT_RIVI, **PUHELIN)
    for otsikko in ("Koodi", "Taso", "Oppiaine", "op"):
        expect(s.locator("#s-kurssit thead th", has_text=re.compile(f"^{otsikko}"))).to_be_hidden()
    expect(s.locator("#s-kurssit thead th", has_text="Tiedot")).to_be_visible()
    rivi = s.locator(KURSSIT_RIVI).first
    kurssi = s.evaluate("kurssit_jarjestyksessa[0]")
    expect(rivi.locator("td").first).to_have_text(f"{kurssi['KurssiNimi']} ({kurssi['Oppiaine']})")
    tiedot = rivi.locator(".mobiili-tiedot")
    expect(tiedot).to_have_text(re.compile(rf"^{kurssi['Opintopisteet']}op \[[YPAS]\] 🌐$"))
    expect(tiedot.locator("a.ops-linkki")).to_have_attribute("href", s.evaluate("kurssiUrl(kurssit_jarjestyksessa[0])"))
    assert s.evaluate("document.documentElement.scrollWidth") <= 390  # ei vaakavieritystä
    valinta = s.locator(f"{KURSSIT_RIVI} .vuosivalinta").first.bounding_box()
    assert valinta["x"] + valinta["width"] <= 390


def test_tasotagin_napautus_nayttaa_selitteen_avaamatta_kurssia(kayttaja):
    s = kayttaja("/kurssit", KURSSIT_RIVI, **PUHELIN)
    tagit = s.locator(f"{KURSSIT_RIVI} .taso-tagi")
    tagi = tagit.filter(has_text="[S]").first
    tagi.click()
    expect(tagi).to_have_class(re.compile("auki"))
    assert s.evaluate("(t) => getComputedStyle(t, '::after').content", tagi.element_handle()) == '"Syventävät opinnot"'
    expect(s.locator("#modaali")).to_be_hidden()
    tagit.filter(has_text="[P]").first.click()  # toinen tagi sulkee ensimmäisen
    expect(s.locator(".taso-tagi.auki")).to_have_count(1)
    s.locator(f"{KURSSIT_RIVI} td").first.click()  # muu rivin napautus avaa kurssin kuten ennen
    expect(s.locator("#modaali")).to_be_visible()
    expect(s.locator(".taso-tagi.auki")).to_have_count(0)


def test_valittujen_kurssien_rivi(kayttaja):
    """Esim. 'Nimi (Oppiaine) | 5op [A] 🌐 | [LLM] [Hyväksy] [Hylkää]'."""
    s = kayttaja(f"/tutkimukset/{SLUG}/kurssit-valittu", VALITUT_RIVI, **PUHELIN)
    rivi = s.locator(VALITUT_RIVI).first
    nakyvat = rivi.locator("td:visible")
    expect(nakyvat).to_have_count(3)
    expect(nakyvat.nth(1)).to_have_text(re.compile(r"^\d+op \[[YPAS]\]"))
    expect(nakyvat.nth(2).locator(".perustelu-pylpyra")).to_have_count(1)
    expect(nakyvat.nth(2).locator(".hitl-nappi")).to_be_visible()
    assert s.evaluate("document.documentElement.scrollWidth") <= 390  # myös pitkä tutkimusotsikko rivittyy


def test_tyopoydalla_ennallaan(kayttaja):
    s = kayttaja("/kurssit", KURSSIT_RIVI)
    expect(s.locator("#mobiilivalikko-nappi")).to_be_hidden()
    expect(s.locator("#paanav")).to_be_visible()
    expect(s.locator("#nimimerkki-kentta")).to_be_visible()
    expect(s.locator(f"{KURSSIT_RIVI}").first.locator("td:visible")).to_have_count(6)
    expect(s.locator(".vain-mobiili:visible")).to_have_count(0)


def _ei_vaakavieritysta(s):
    assert s.evaluate("document.documentElement.scrollWidth") <= PUHELIN["leveys"]


def test_korkeakoulut(kayttaja):
    """Opinto-opas nimen alla (oma sarake piilossa), vuosisarakkeet mahtuvat ruutuun."""
    s = kayttaja("/korkeakoulut", "#korkeakoulut-rungot tr", **PUHELIN)
    expect(s.locator("#korkeakoulut-otsikko th", has_text="Opinto-opas")).to_be_hidden()
    rivi = s.locator("#korkeakoulut-rungot tr").first
    expect(rivi.locator(".kk-nimi a.ops-linkki")).to_be_visible()
    expect(rivi.locator(".kk-opas")).to_be_hidden()
    _ei_vaakavieritysta(s)


def test_tutkimukset_korttina_ja_pitka_teksti_avautuu(kayttaja):
    """Rivi korttina: nimi, tiedot otsikoineen allekkain, napit vierekkäin. Pitkä oppiaine-
    rajaus rajattu muutamaan riviin; napautus avaa ja sulkee (ei hover-titleä puhelimessa)."""
    s = kayttaja("/tutkimukset", "#tutkimukset-rungot tr", **PUHELIN)
    s.evaluate("""() => { const td = document.querySelector('.tutkimus-oppiaine-solu');
      td.textContent = Array.from({length: 120}, (_, i) => 'Oppiaine ' + i).join(','); }""")
    expect(s.locator("#s-tutkimukset thead")).to_be_hidden()
    _ei_vaakavieritysta(s)
    napit = s.locator("#tutkimukset-rungot .nappi-pieni")
    assert len({round(napit.nth(i).bounding_box()["y"]) for i in range(3)}) == 1  # samalla rivillä
    rajaus = s.locator(".tutkimus-oppiaine-solu")
    korkeus = rajaus.bounding_box()["height"]
    assert korkeus < 80
    rajaus.click()
    expect(rajaus).to_have_class(re.compile("auki"))
    assert rajaus.bounding_box()["height"] > 3 * korkeus
    expect(s).to_have_url(re.compile("/tutkimukset$"))
    rajaus.click()
    expect(rajaus).not_to_have_class(re.compile("auki"))


def test_tutkimuskuvauksen_kehotteet_avautuvat(kayttaja):
    """Kehotteet ja oppiainerajaus rajattu muutamaan riviin, napautus avaa; työpöydällä kokonaan."""
    s = kayttaja(f"/tutkimukset/{SLUG}", "#tutkimus-tiedot-sisalto .kehote-teksti", **PUHELIN)
    s.evaluate("""() => document.querySelectorAll('#tutkimus-tiedot-sisalto .avattava').forEach((el) => {
      el.textContent = 'Pitkä kehote. '.repeat(100); })""")
    # Tuotannon oppiainerajaus: pilkuilla ilman välilyöntejä → ei luonnollisia rivityskohtia
    s.evaluate("document.querySelector('#tutkimus-tiedot-sisalto td.avattava').textContent = 'Oppiaine,'.repeat(200)")
    avattavat = s.locator("#tutkimus-tiedot-sisalto .avattava")
    expect(avattavat).to_have_count(4)  # 3 kehotetta + oppiainerajaus
    _ei_vaakavieritysta(s)
    kehote = s.locator(".kehote-teksti").first
    korkeus = kehote.bounding_box()["height"]
    assert korkeus < 100
    kehote.click()
    assert kehote.bounding_box()["height"] > 3 * korkeus
    s.set_viewport_size({"width": 1280, "height": 900})
    s.evaluate("document.querySelectorAll('.avattava.auki').forEach((el) => el.classList.remove('auki'))")
    assert kehote.evaluate("(el) => el.scrollHeight <= el.clientHeight + 1")  # ei rajausta


ARVIOINTI_RIVI = "#tutkimus-arvioinnit-sisalto tr.kurssi-rivi"


def test_arvioinnit_kurssikortteina(kayttaja):
    """Kurssi kortiksi: 'Nimi (Oppiaine) | 6op [A] 🌐', alla kukin kysymys otsikoineen ja
    Hyväksy/Korjaa vastauksen vieressä. Pitkä vastaus rajattu, napautus avaa (ei avaa kurssia)."""
    s = kayttaja(f"/tutkimukset/{SLUG}/arvioinnit", ARVIOINTI_RIVI, **PUHELIN)
    expect(s.locator("#tutkimus-arvioinnit-sisalto th.kysymys-sarake").first).to_be_hidden()
    _ei_vaakavieritysta(s)
    rivi = s.locator(ARVIOINTI_RIVI).first
    kurssi = s.evaluate("arvioinnit_data.kurssit[0]")
    # inner_text = näkyvä teksti (työpöydän opaslinkki piilossa)
    assert rivi.locator("td").first.inner_text().strip() == f"{kurssi['KurssiNimi']} ({kurssi['Oppiaine']})"
    expect(rivi.locator(".mobiili-tiedot")).to_have_text(re.compile(rf"^{kurssi['Opintopisteet']}op \[[YPAS]\]"))
    solut = rivi.locator("td.arviointi-vastaus")
    kysymykset = s.evaluate("arvioinnit_data.kysymykset.length")
    expect(solut).to_have_count(kysymykset)
    for i in range(kysymykset):
        laatikko = solut.nth(i).bounding_box()
        assert laatikko["width"] > 300  # koko kortin levyinen
        assert solut.nth(i).evaluate("(td) => getComputedStyle(td, '::before').content").strip('"')
    korjaa = solut.first.locator("button[data-lomake]")
    assert korjaa.bounding_box()["x"] + korjaa.bounding_box()["width"] <= PUHELIN["leveys"]

    teksti = solut.first.locator(".arvio-teksti")
    teksti.evaluate("(el) => { el.textContent = 'Pitkä perustelu. '.repeat(60); }")
    korkeus = teksti.bounding_box()["height"]
    assert korkeus < 80
    teksti.click()
    assert teksti.bounding_box()["height"] > 3 * korkeus
    expect(s.locator("#modaali")).to_be_hidden()
    s.evaluate("renderArvioinnitTaulu()")  # taustapäivitys ei sulje avattua
    expect(solut.first.locator(".arvio-teksti")).to_have_class(re.compile("auki"))
    rivi.locator("td").first.click()  # nimen napautus avaa kurssin kuten ennen
    expect(s.locator("#modaali")).to_be_visible()


def test_arvioinnin_korjauslomake_mahtuu(kayttaja):
    s = kayttaja(f"/tutkimukset/{SLUG}/arvioinnit", ARVIOINTI_RIVI, **PUHELIN)
    s.locator(f"{ARVIOINTI_RIVI} td.arviointi-vastaus button[data-lomake]").first.click()
    sisalto = s.locator(".modaali:not(.piilotettu) .modaali-sisalto")
    expect(sisalto).to_be_visible()
    laatikko = sisalto.bounding_box()
    assert laatikko["x"] >= 0 and laatikko["x"] + laatikko["width"] <= PUHELIN["leveys"]
    assert s.evaluate("document.querySelector('.modaali:not(.piilotettu)').scrollWidth") <= PUHELIN["leveys"]


def test_arviointien_paivitys_ei_siirra_vierityskohtaa(kayttaja):
    """Taustapäivitys (pollaus 15 s) rakentaa kortit uudelleen: näkyvä kortti pysyy paikallaan,
    vaikka ruudun ulkopuolisten erien korkeus on vain arvio (content-visibility)."""
    s = kayttaja(f"/tutkimukset/{SLUG}/arvioinnit", ARVIOINTI_RIVI, **PUHELIN)
    s.wait_for_function("!arvioinnit_kesken && arvioinnit_data.kurssit.length > 100", timeout=30000)
    s.evaluate("document.querySelectorAll('#tutkimus-arvioinnit-sisalto tr.kurssi-rivi')[100].scrollIntoView()")
    s.wait_for_timeout(300)
    kohta = "(() => { const r = document.elementFromPoint(200, 400).closest('tr'); return [r.dataset.kid, Math.round(r.getBoundingClientRect().top)]; })()"
    ennen = s.evaluate(kohta)
    s.evaluate("renderArvioinnitTaulu()")
    s.wait_for_timeout(300)
    jalkeen = s.evaluate(kohta)
    assert jalkeen[0] == ennen[0] and abs(jalkeen[1] - ennen[1]) <= 1


def test_raportti_mahtuu_ja_muokkaus_aukeaa(kayttaja):
    """Raportti ilman vaakavieritystä (leveä tilastotaulu vierii omassa laatikossaan);
    osion Muokkaa-lomake mahtuu ruutuun."""
    s = kayttaja(f"/tutkimukset/{SLUG}/raportti", "#raportti-sisalto .raportti-osio", **PUHELIN)
    s.wait_for_selector("#raportti-sisalto .tilasto-taulu")
    _ei_vaakavieritysta(s)
    for laatikko in s.locator("#raportti-sisalto .tilasto-taulu").evaluate_all(
            "(t) => t.map((el) => el.getBoundingClientRect().right)"):
        assert laatikko <= PUHELIN["leveys"]
    s.locator(".raportti-muokkaa-nappi").first.click()
    sisalto = s.locator(".modaali:not(.piilotettu) .modaali-sisalto")
    expect(sisalto).to_be_visible()
    assert sisalto.bounding_box()["x"] + sisalto.bounding_box()["width"] <= PUHELIN["leveys"]


def test_modaalin_pitka_sana_ei_levenna(kayttaja):
    """Pitkä katkeamaton sana (yhdyssana, URL) kurssimodaalin otsikossa rivittyy."""
    s = kayttaja("/kurssit", KURSSIT_RIVI, **PUHELIN)
    s.locator(f"{KURSSIT_RIVI} td").first.click()
    s.wait_for_selector("#modaali:not(.piilotettu) #modaali-otsikko")
    s.evaluate("document.getElementById('modaali-otsikko').append('Tietoturvallisuusjohtamisjärjestelmäkokonaisuus'.repeat(3))")
    assert s.evaluate("document.getElementById('modaali').scrollWidth") <= PUHELIN["leveys"]
