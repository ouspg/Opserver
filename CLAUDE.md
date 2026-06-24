# Opserver — Automaattinen kurssitutkimusputki

## Projektin tarkoitus

Automaattinen pipeline suomalaisten yliopistojen opinto-oppaiden läpikäymiseen ja relevanttien kurssien tunnistamiseen annetun tutkimusaiheen suhteen (aluksi: kyberturvallisuus / ESR-konteksti). Tuottaa jäsennellyn raportin, jossa on kaksi ihminen-silmukassa -tarkistuspistettä.

## Pipelinen vaiheet

```
1. Haku       → Suodata kurssit opinto-oppaista tiedekunnan / kurssin tason mukaan
                 (yleis | perus | aine | syventävä)
                 → tallennetaan raakadata MySQL-tietokantaan (Docker, portti 21212)

2. Seulonta   → Lähetetään kurssin kuvaus LLM:lle
                 → LLM vastaa kiinteään kysymyssarjaan: mukaan vai pois?
                 → tuottaa: mukaan otettujen kurssien lista + perustelu per kurssi

3. Arviointi  → Mukaan otetuille kursseille LLM vastaa syvempään kysymyssarjaan
                 → tuottaa: per-kurssi jäsennellyt arviot

4. Raportti   → Loppuraportti generoidaan tietokannan tilasta

5. HITL-A     → Ihminen tarkistaa mukaan otettujen / pois jätettyjen kurssien listan
                 Virheiden kaksi juurisyytä:
                   a) Hiljainen tieto — opinto-opas ei sisältänyt tietoa → kirjataan raporttiin,
                      ihminen täydentää vastauksen + tilasto riittämättömistä oppaista
                   b) LLM:n virhe → paranna promptia → aja vaihe 2 uudelleen

6. HITL-B     → Ihminen tarkistaa per-kurssi arviot
                 Samat juurisyyt ja korjaustoimenpiteet kuin HITL-A:ssa
```

## Tietovirrat

- **Syöte:** opinto-oppaiden URL:t + suodatusasetukset (tiedekunta, taso, aihe)
- **Tallennus:** MySQL Docker-kontti (portti 21212) — kurssitiedot, LLM-vastaukset, mukaan/pois-päätökset
- **LLM-kutsut:** seulontakysymyssarja (vaihe 2), arviointikysymyssarja (vaihe 3)
- **Tuloste:** jäsennelty raportti + tilastot oppaiden laadusta

## Virhetaksonomia (kriittinen promptien suunnittelulle)

| Juurisyy | Signaali | Korjaustoimenpide |
|---|---|---|
| Riittämätön opinto-opas | Oikea vastaus ei ole johdettavissa tekstistä | Kirjataan raporttiin; ihminen täydentää vastauksen; seurataan %-osuutta |
| LLM:n väärinymmärrys | Vastaus on johdettavissa, mutta on väärä | Paranna promptia; aja vaihe uudelleen |

## Käyttöliittymät

**Curses-UI** — operaattorille tarkoitettu terminaalikäyttöliittymä pipelinen ajamiseen ja seurantaan. Käytetään paikallisesti prosessia ohjaavan henkilön toimesta.

**Web-UI** — localhost-verkkopalvelin tulosten esittämiseen yleisölle yhteisen WiFi-verkon kautta. Yleisön jäsenet liittyvät omilla laitteillaan paikallisverkon osoitteen kautta. Suunniteltu yhteisöllisiin HITL-annotointisessioihin:
- Näyttää kurssilistat ja per-kurssi arviot; kurssin nimi linkittää suoraan Peppi-opinto-oppaaseen
- Useat käyttäjät voivat annotoida ja korjata tekoälyn päätöksiä reaaliajassa
- Annotoinnit päivittyvät raporttiin (ks. HITL-A / HITL-B -vaiheet)

Käyttöliittymät ovat toisistaan riippumattomia: curses-UI ohjaa pipelinen suoritusta; web-UI on vain tulosten ja annotointien luku/kirjoitusliittymä.

WebUI:n esittely yleisölle (seminaari-lähiverkko ja etäkokous-Tailscale Funnel) sekä suojaus (HTTP Basic Auth, `WEBUI_AUTH_*`): ks. **`DEMO.md`**. Suositus: aja demo aina Funnelin (HTTPS) kautta, jolloin Basic Auth on turvallinen.

## Kehityskäytännöt

- Python-projekti; pidä riippuvuudet minimissä ja kirjaa ne `requirements.txt`-tiedostoon
- MySQL Docker-kontissa (portti 21212) kaikelle pysyvyydelle; WebUI Docker-kontissa (portti 12121)
- LLM-kutsut kulkevat yhden ohuen kääreen kautta (`llm/kutsu.py`), jotta malli/palveluntarjoaja voidaan vaihtaa — OpenAI-yhteensopiva rajapinta, konfiguraatio `.env`:ssä (`LLM_PROVIDER` = perus-URL, `LLM_API_KEY`, `LLM_MODEL`)
- Promptit sijaitsevat omissa tiedostoissaan (ei koodin sisällä), jotta niitä voi iteroida koskematta logiikkaan
- Hakurobottien täytyy olla kohteliaita: noudata `robots.txt`:ää, lisää viiveet, älä kuormita palvelimia
- Kaikki pipeline-vaiheet ovat idempotenteja — vaiheen uudelleenajo on aina turvallista
- DRY — ei kopioitua logiikkaa; yhteiset apufunktiot yhteiseen moduuliin
- Tiedostokoko: jokaisen tiedoston täytyy olla niin pieni, että Claude pystyy lukemaan sen kerralla (käytännön raja ~500 riviä); jaa tiedosto ajoissa jos se kasvaa liian suureksi
- **Funktioiden ja muuttujien nimet kirjoitetaan suomeksi** — ainoat poikkeukset ovat kirjastojen vaatimat rajapinnat ja yleisesti vakiintuneet lyhenteet (esim. `db`, `url`, `id`)

## Git-käytännöt

- **Feature-haarat** jokaiselle ei-triviaalille muutokselle — älä commitoi suoraan `main`-haaraan
- **Haara-nimeämiskäytäntö:** `feature/kuvaus` uusille ominaisuuksille, `fix/kuvaus` bugikorjauksille, `claude/kuvaus` dokumentaatio- ja konfiguraatiomuutoksille
- **Pienet, selkeät commitit** — jokainen commit edustaa yhtä ymmärrettävää muutosyksikköä
- **Commitoi jokaisen loogisen kokonaisuuden jälkeen** — älä odota session loppuun; kun yksi itsenäinen muutos on valmis ja testattu, commitoi se heti
- Kaikkien testien täytyy mennä läpi ennen haaran yhdistämistä

## Testaus

- **Testilähtöinen kehitys (TDD):** kirjoita testi ensin, sitten toteuta kunnes testi menee läpi
- Testit sijaitsevat testattavan koodin rinnalla (esim. `tests/test_hakija.py` tiedostolle `hakija.py`)
- Aja koko testijoukko jokaisen ei-triviaalin muutoksen jälkeen; ei yhdistämistä epäonnistuneiden testien kanssa
- Testien täytyy olla nopeita eivätkä ne saa vaatia verkkoyhteyttä — mock-ita ulkoiset kutsut (HTTP, LLM API)

## Kehitystyökalut

- **`./run`** — käynnistää Curses-UI:n (`.venv/bin/python -m cliui.valikko`)
- **`./db "SQL"`** — ajaa tietokantakyselyn lukien kirjautumistiedot `.env`:stä
- **`docker compose up -d`** — käynnistää MySQL + WebUI kontit
- **`docker compose build webui && docker compose up -d webui`** — pakollinen webui-koodimuutosten jälkeen
- **WebUI JS/CSS versiointi:** kun muutat `sovellus.js` tai `tyyli.css`, kasvata `?v=N`-numeroa `index.html`:ssä
- **`./testit/savutesti.sh`** — savutesti: varmistaa, että MySQL + WebUI-kontit vastaavat oikein (olettaa konttien olevan käynnissä)

## Vaiheiden valmistumiskriteerit

1. **Haku:** Tietokannassa on kurssirivit otsikolla, kuvauksella, tiedekunnalla, tasolla ja lähde-URL:lla
2. **Seulonta:** Jokaisella haussa löydetyllä kurssilla on mukaan/pois-päätös ja per-kysymys LLM-vastaukset tallennettuna
3. **Arviointi:** Jokaisella mukaan otetulla kurssilla on jäsennellyt arviointivastaukset tallennettuna
4. **Raportti:** Ihmisluettava raportti generoitu tietokannan tilasta; sisältää %-osuuden riittämättömiksi merkityistä oppaista
5. **HITL-silmukat:** Käyttöliittymä antaa ihmisen merkitä virheet ja valita juurisyyn; käynnistää uudelleenajon tai annotoinnin
