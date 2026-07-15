# Raportointitoiminnallisuuden katsaus (pipelinen vaihe 4: Raportti)

Tämä dokumentti kuvaa, miten pipelinen vaihe 4 ("Raportti") on toteutettu: mitkä ominaisuudet on rakennettu, missä tiedostoissa, mitä ne tekevät ja miten. Tarkoitus on toimia lähtökohtana toteutuksen tarkastukselle CLAUDE.md:n valmistumiskriteerejä vasten.

*Tiedostoviittaukset ja väitteet varmennettu koodikannasta 2026-07-15. Tämä versio kuvaa tilan **PR #5:n jälkeen** (HITL-juurisyy + laatumittarit + tuoreusseuranta). Aiemmin dokumentoitu avoin puute ("%-osuus riittämättömiksi merkityistä oppaista") on nyt toteutettu — ks. kohta "Toteutettu: virhetaksonomia ja laatumittarit".*

## Yleiskuva

Raportointi jakautuu kolmeen puoliskoon:

1. **Generointi** (`raportti/llmraportti.py`) — rakentaa tietokannan tilasta kolme LLM-promptia (johdanto, kurssit, arvioinnit), lähettää ne `llm/kutsu.py`:n kautta ja kirjoittaa vastaukset `RaporttiOsio`-tauluun (avaimena `TID` + `OsioAvain`). Ajo on idempotentti. Kurssit-osion promptiin injektoidaan **HITL-laatumittarit** (käsin-muutos-% + juurisyyjakauma). Generoinnin hetkellä tallennetaan myös **laskentatiiviste** — hash lähdeaineistosta tuoreusseurantaa varten.
2. **Esitys ja muokkaus** — Web-UI lukee `RaporttiOsio`-taulun sisällön, laskee lisäksi rakenteelliset tilastot lennossa (per-kysymys-jakaumat + HITL-laatumittarit) ja tarjoaa muokattavan, usean käyttäjän yhteismuokattavan HTML-raportin, tulostus/PDF-napin sekä **tuoreuspalkin**. Curses-UI laukaisee generoinnin ja näyttää **"Näytä tilanne"** -sivun (tekoaika, tuoreus, generoinnin jälkeiset muutokset).
3. **Tuoreusseuranta** (A+B) — sekä CLIUI:n "Näytä tilanne" että Web-UI:n tuoreuspalkki kertovat: milloin raportti generoitiin, onko lähdeaineisto muuttunut sen jälkeen (laskentatiivistevertailu), ja montako HITL-korjausta/kommenttia on tehty generoinnin jälkeen.

## Tiedostot ja niiden roolit

### Ydinlogiikka

- **`raportti/__init__.py`** — tyhjä pakettimerkki.

- **`raportti/llmraportti.py`** — ydinmoduuli.
  - `OSIOT = ["johdanto", "kurssit", "arvioinnit"]` — kolme kiinteää raporttiosiota.
  - `hitl_mittarit(tilastot)` (r. 105) — laskee CLAUDE.md:n vaatimat kaksi laatumittaria: **käsin muutettujen luokittelupäätösten osuus** (muutetut / LLM-luokitellut) ja **juurisyyjakauma** (riittämätön opas vs. LLM:n virhe, osuutena korjauksista). Julkinen — jaettu WebUI-päätepisteen kanssa (DRY).
  - `_hitl_yhteenveto_teksti(m)` (r. 127) — muotoilee mittarit raporttikehotteen tekstilohkoksi.
  - `_rakenna_*_viesti` — rakentavat kolme käyttäjäviestiä `mallit.hae_tilastot_yliopistoittain(tid)`, `mallit.hae_kysymykset(tid)`, `mallit.hae_arviokommentit_kaikki(tid)` ja tutkimuksen kehote-/rajauskenttien pohjalta. Kurssit-viesti sisältää laatumittarit ja ohjeistaa LLM:ää raportoimaan riittämättömien oppaiden osuuden eksplisiittisesti.
  - `raporttitiiviste(tutkimus, tilastot=None, kysymykset=None)` (r. 10) — SHA-256-tiiviste lähdeaineistosta, josta raportti koottiin: per-yliopisto-tilastot (luokitukset + HITL), kysymykset, arviointien tila (`hae_vastaus_tiivisteet`), kommentit ja tutkimuksen kehotteet/rajaukset. Muuttuu, jos jokin raporttiin vaikuttava tieto muuttuu — kattaa myös aikaleimattomat taulut (`Kurssiluokitus`, `Vastaukset`), joten seulonnan/haun uudelleenajo näkyy.
  - `koosta_tilanne(tutkimus)` (r. 49) — kokoaa raportin tuoreustiedot status-näkymiin (**curses- ja HTTP-riippumaton**, jaettu CLIUI + WebUI). Palauttaa `{"generoitu": False}` tai osioiden tilan + aikaleimat, tuoreuden (`ajan_tasalla` / `vanhentunut` / `tuntematon`, tiivistevertailu) ja generoinnin jälkeen tehtyjen HITL-korjausten/kommenttien määrän.
  - `aja(tutkimus, edistyminen_cb=None) -> int` — pääfunktio: laskee laskentatiivisteen, käy läpi kolme osiota, kutsuu `llm.kutsu.kysy`:tä ja tallentaa tuloksen `mallit.aseta_raportti_osio(tid, avain, teksti, laskentatiiviste=...)`:llä.

- **`raportti/_kehotteet.py`** — debug-CLI (`./kehoteraportti`-wrapper). Tulostaa tutkimuksen järjestelmäkehotteen ja kolme käyttäjäviestiä **kutsumatta LLM:ää**. Ei testikattavuutta.

- **`kehotteet/raporttijarjestelma.txt`** — järjestelmäkehote (asiantuntija-analyytikko, ei keksi lukuja, ei markdown-otsikoita, 2–4 kappaletta per osio).

### Tietokantakerros

- **`tietokanta/mallit.py`**
  - `JUURISYYT` (r. 830) — virhetaksonomian koodit → nimet (`riittamaton_opas`, `llm_virhe`); jaettu WebUI-validoinnin ja raporttitilastojen kesken.
  - `tallenna_hitl_korjaus(..., juurisyy=None)` (r. 836) — tallentaa HITL-korjauksen valinnaisen juurisyyn kera.
  - `hae_tilastot_yliopistoittain(tid)` (r. 999) — per-yliopisto `KurssiYhteensa`, `LLMKasitelty`, `Mukana`, `Hylatty`, `HitlLkm`, sekä **`HitlKursseja`** (käsin muutetut kurssit) ja **juurisyyjakauma** (`RiittamatonOpas` / `LlmVirhe` / `TuntematonSyy`, laskettu kunkin kurssin *viimeisimmästä* korjauksesta).
  - `aseta_raportti_osio(tid, avain, teksti, laskentatiiviste=None)` (r. 924) — upsert; `laskentatiiviste` tallennetaan generoinnissa, säilytetään WebUI-tekstimuokkauksessa (`COALESCE`).
  - `hae_raportti_tila(tid)` (r. 950) — per-osio aikaleima + laskentatiiviste (ei hae Teksti-kenttää).
  - `laske_hitl_korjaukset_jalkeen(tid, aika)` (r. 963), `laske_arviokommentit_jalkeen(tid, aika)` (r. 974) — COUNT annetun ajan jälkeen (tuoreussivun "generoinnin jälkeen" -signaalit).
  - CRUD `RaporttiOsio`-tauluun: `hae_raportti_osiot`, `hae_raportti_osio`.

- **`tietokanta/migraatio_007.sql`** — `Tutkimus.Raportointikehote` + `RaporttiOsio`-taulu (`Aikaleima` `ON UPDATE CURRENT_TIMESTAMP`).
- **`tietokanta/migraatio_016.sql`** — `HitlKorjaus.Juurisyy VARCHAR(32) NULL` (virhetaksonomia).
- **`tietokanta/migraatio_017.sql`** — `RaporttiOsio.Laskentatiiviste VARCHAR(64) NULL` (tuoreustarkistus).
  - *Molemmat additiivisia (nullable); sovellettu geopalvelin1-kantaan kehityksen aikana.*

### Curses-UI

- **`cliui/valikko.py`** — päävalikon `"6) Tee raportti"` → `raporttinaytto.nayta`.
- **`cliui/raporttinaytto.py`** — "Generoi raportti LLM:llä" (kutsuu `llmraportti.aja`) tai **"Näytä tilanne"** (`_nayta_tilanne` → `llmraportti.koosta_tilanne`): näyttää generointiajan, per-osio aikaleimat, tuoreuden (`_TUOREUS_TEKSTI`: ajan tasalla / vanhentunut / tuntematon) ja generoinnin jälkeen tehdyt korjaukset/kommentit. `_aika_str` muotoilee aikaleiman.

### Web-UI

- **`webui/palvelin.py`** — FastAPI-reitit:
  - `POST .../kurssit/{kid}/hitl` (r. 525) — `HitlPyynto` (r. 516) sisältää valinnaisen `juurisyy`-kentän; reitti validoi sen `JUURISYYT`:ia vasten (400 tuntemattomalle).
  - `GET .../raportti` (r. ~536) → `{tid, osiot}`.
  - `GET .../raportti/tilastot` (r. 548) → per-kysymys-jakaumat **+ `hitl`-lohko** (`llmraportti.hitl_mittarit`: käsin-muutos-% + juurisyyjakauma, auktoritatiivinen rakenteellinen luku).
  - `GET .../raportti/tilanne` (r. 623) → `koosta_tilanne`-tuoreustiedot, `_raportti_tilanne_valimuistissa` (r. 332, TTL-välimuisti ettei 15 s -päivitys kuormita etäkantaa).
  - WebSocket-pohjainen yhteismuokkauskerros (`raportti-liity`/`-teksti`/`-tallenna`/`-poistu`).

- **`webui/staattinen/sovellus.js`** — `renderTutkimusRaportti` hakee raportin, tilastot ja tuoreuden; `_renderTuoreusPalkki` (tuoreuspalkki: generointiaika + ajan tasalla/vanhentunut/tuntematon + muutokset), `_renderHitlMittarit` (laatumittarit kurssit-osioon), `_renderTilastotTaulukko` (per-kysymys-jakaumat arvioinnit-osioon), `avaaRaporttiTulostus` (tulosta-PDF, sisältää myös HITL-mittarit).

- **`webui/staattinen/index.html`** — HITL-modaali sisältää **pakolliset juurisyy-radionapit** (riittämätön opas / LLM:n virhe). `sovellus.js?v=43`, `tyyli.css?v=36`.

- **`webui/staattinen/raporttimuokkaus.js`** — yhteismuokkausmodaali (live-teksti + etäkursorit).

### Testit

- **`testit/test_raportti.py`** — `llmraportti`: taulukko, viestirakentajat, `hitl_mittarit`, `raporttitiiviste` (`TestRaporttiTiiviste`: determinismi + herkkyys), `koosta_tilanne` (`TestKoostaTilanne`: neljä tuoreustilaa), `aja` (osiot, edistyminen, idempotenssi, laskentatiivisteen kirjoitus).
- **`testit/test_tietokanta.py`** — `TestHitlKorjaus` (juurisyy), `TestRaporttiTila` (aseta_raportti_osio-tiiviste, hae_raportti_tila, laske_*_jalkeen).
- **`testit/test_webui.py`** — HITL-reitti (juurisyy: välitys, valinnaisuus, 400 tuntemattomalle), `/raportti`, `/raportti/tilastot` (ml. `hitl`-lohko), `/raportti/tilanne` (tuoreus + 404).
- **`testit/test_cliui.py`** — curses-savutestit.

## Toteutettu: virhetaksonomia ja laatumittarit (aiempi avoin puute)

CLAUDE.md:n vaiheen 4 valmistumiskriteeri "sisältää %-osuuden riittämättömiksi merkityistä oppaista" oli aiemmin toteuttamatta. **Nyt toteutettu:**

1. **Juurisyyn kirjaus** — `HitlKorjaus.Juurisyy` (migraatio 016) erottaa taksonomian: *riittämätön opinto-opas* (oikea vastaus ei johdettavissa oppaan tekstistä → data-ongelma) vs. *LLM:n väärinymmärrys* (vastaus johdettavissa, mutta malli erehtyi → kehote-ongelma). Jaettu `JUURISYYT`-vakio.
2. **UI-kontrolli** — pakollinen juurisyy-radiovalinta WebUI:n HITL-annotointimodaalissa; reitti validoi arvon.
3. **Kaksi laatumittaria** (per yliopisto + koko aineisto), käyttäjän tarkennuksen mukaan:
   - **Käsin muutettujen osuus** = muutetut kurssit / LLM-luokitellut kurssit
   - **Juurisyyjakauma** = korjauksista montako % johtui riittämättömästä oppaasta vs. LLM:n virheestä
   Esitetään sekä LLM-raporttikehotteessa (proosa) että rakenteellisena, auktoritatiivisena lukuna (`/raportti/tilastot` → WebUI:n kurssit-osio + tulostus-PDF).

## Toteutettu: raportin tuoreusseuranta (A+B)

Aiemmin CLIUI:n "Näytä tilanne" näytti vain ✓/— per osio, eikä kertonut milloin raportti tehtiin tai onko aineisto muuttunut. **Nyt:**

- **A** (aikaleimapohjainen): generointiaika (`RaporttiOsio.Aikaleima`) + "generoinnin jälkeen N HITL-korjausta, M kommenttia" (`HitlKorjaus`/`ArvioKommentti`-aikaleimoista).
- **B** (tiivistepohjainen, kattaa aikaleimattomat taulut): `RaporttiOsio.Laskentatiiviste` (migraatio 017) tallentaa lähdeaineiston hashin generoinnin hetkellä; status vertaa tallennettua nykyiseen → yksiselitteinen *ajan tasalla / vanhentunut / tuntematon*.
- Sama `koosta_tilanne`-logiikka molemmissa käyttöliittymissä (CLIUI "Näytä tilanne" + WebUI tuoreuspalkki).

## Avoimet kohdat / mahdollinen jatkokehitys

Vaiheen 4 valmistumiskriteerit täyttyvät. Jäljellä olevat kohdat ovat testikattavuutta ja laajempaa HITL-silmukkaa:

1. **Testikattavuuden aukot:**
   - `raportti/_kehotteet.py` — ei testejä (debug-skripti, matala prioriteetti).
   - WebUI:n WebSocket-**yhteismuokkaus** raportin osalta — ei automaattitestejä.
   - Frontend-JS:n renderöinti ja PDF-vienti (`avaaRaporttiTulostus`) — vain Playwright-savutestit HITL-mittareille, juurisyy-modaalille ja tuoreuspalkille; yhteismuokkaus- ja PDF-polku ilman automaattitestejä.

2. **HITL-silmukan automaatio (CLAUDE.md-kriteeri #5, raportin ulkopuolella):** UI kirjaa juurisyyn, mutta *ei automaattisesti* käynnistä vaiheen 2 uudelleenajoa kun juurisyy on "LLM:n virhe" — uudelleenajo on yhä manuaalinen CLIUI-toiminto. Juurisyy on nyt kirjattuna saatavilla tätä automaatiota varten.

3. **Tuoreustiivisteen rajaus (tietoinen suunnitteluvalinta):** laskentatiiviste kattaa raportin *generointi-inputit* (aggregaatit + arviointien tila + kehotteet). Yksittäisen vapaatekstivastauksen muokkaus, joka ei muuta aggregaatteja tai tiivisteen inputteja, ei käännä tuoreuslippua — tämä on tarkoituksellista (raportti itsessään ei riipu vapaatekstin sisällöstä).
