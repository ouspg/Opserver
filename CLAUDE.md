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
- **Tallennus:** MySQL (portti 21212; nyk. etäpalvelin geopalvelin1 / Tailscale — ks. Kehityskäytännöt) — kurssitiedot, LLM-vastaukset, mukaan/pois-päätökset
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

WebUI:n esittely yleisölle = tuotannon `https://<TUOTANTO_DOMAIN>` (Caddy päättää TLS:n), suojattu HTTP Basic Authilla (`WEBUI_AUTH_KAYTTAJA`/`WEBUI_AUTH_SALASANA` `.env`:ssä). Webui ei julkaise porttia 12121 hostiin (vain `expose`) — kaikki liikenne Caddyn kautta.

## Kehityskäytännöt

- Python-projekti; pidä riippuvuudet minimissä ja kirjaa ne `requirements.txt`-tiedostoon
- MySQL kaikelle pysyvyydelle portissa 21212; WebUI Docker-kontissa (portti 12121)
  - **Huom:** jaettu/testi-MySQL on migroitu etäpalvelin **geopalvelin1**:lle (Tailscale-osoite `100.123.32.101:21212`, korkea/piikikäs latenssi). Yhteysasetukset `.env`:stä (`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`); `docker-compose.yml`:n mysql-palvelu jää paikalliskehitykseen. Kirjoita tietokantakoodi etälatenssia varten: yhteyspooli (`tietokanta/yhteys.py`), `COUNT`/aggregaatit rivinouton sijaan, älä toista raskaita hakuja.
  - **Tuotanto on eri, erillinen kone** — ei geopalvelin1 (se on testiympäristö). Tuotanto ajaa oman paikallisen MySQL+WebUI+Caddy-pinonsa Dockerissa (443, ks. Kehitystyökalut `./asenna`).
  - **Tietokantamuutokset:** uusi `tietokanta/migraatio_NNN.sql` (juokseva numero) muutosta varten. `./asenna` ajaa puuttuvat migraatiot idempotentisti tuotannossa (`_migraatiot`-seurantataulu). `alustus.sql` on nykyinen perusskeema (squashattu migratoidusta kannasta) — squashaa se ajoittain uudelleen (`mysqldump --no-data --routines` migratoidusta kannasta), ettei migraatiolista kasva loputtomiin. Squashauksen jälkeen päivitä `alustus_migraatiot.sql`:n esitäyttölista (vain tuoreelle kannalle, initdb.d), tai tuore asennus yrittää ajaa migraatiot uudelleen. **Jokainen skeemamuutos kuuluu migraatioon myös silloin kun teet sen käsin kehityskantaan** — muuten se päätyy squashiin muttei migraatioketjuun, ja vanha kanta ei enää migratoidu (`Vastaukset`, `Tutkimus.Slug`). `./testit/migraatiotesti.sh` ajaa ketjun vanhasta skeemasta ja vertaa lopputuloksen tuoreeseen asennukseen.
- LLM-kutsut kulkevat yhden ohuen kääreen kautta (`llm/kutsu.py`), jotta malli/palveluntarjoaja voidaan vaihtaa — OpenAI-yhteensopiva rajapinta, konfiguraatio `.env`:ssä (`LLM_PROVIDER` = perus-URL, `LLM_API_KEY`, `LLM_MODEL`)
- Promptit sijaitsevat omissa tiedostoissaan (ei koodin sisällä), jotta niitä voi iteroida koskematta logiikkaan
- Hakurobottien täytyy olla kohteliaita: noudata `robots.txt`:ää, lisää viiveet, älä kuormita palvelimia
- Kaikki pipeline-vaiheet ovat idempotenteja — vaiheen uudelleenajo on aina turvallista
- DRY — ei kopioitua logiikkaa; yhteiset apufunktiot yhteiseen moduuliin
- Tiedostokoko: jokaisen tiedoston täytyy olla niin pieni, että Claude pystyy lukemaan sen kerralla (käytännön raja ~500 riviä); jaa tiedosto ajoissa jos se kasvaa liian suureksi
- **Funktioiden ja muuttujien nimet kirjoitetaan suomeksi** — ainoat poikkeukset ovat kirjastojen vaatimat rajapinnat ja yleisesti vakiintuneet lyhenteet (esim. `db`, `url`, `id`)

## Git-käytännöt

- **Feature-haarat** jokaiselle ei-triviaalille muutokselle — älä commitoi suoraan `main`-haaraan
- **Avoimet löydökset:** uudet ominaisuudet ja ympäristö-/infrastruktuuritehtävät (sekä avoimet päätökset) → `TASKS.md`; nykyisen koodin korjaukset (bugit, suorituskyky, lint, tietoturva) → GitHub-issue (`gh issue create`, nimike `bug`/`enhancement`)
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
- **WebUI JS/CSS versiointi:** kun muutat mitä tahansa `webui/staattinen/`-tiedostoa, kasvata sen `?v=N`-numeroa `index.html`:ssä. Kaksi rinnakkaista PR:ää nostaa helposti saman numeron — toisena yhdistettävässä nosta vielä kerran
- **`./testit/skeematarkistus.sh`** — vertaa ajossa olevan kannan skeemaa tavoiteskeemaan (`testit/fixtures/tavoiteskeema.sql`); aja asennuksen tai migraatioiden jälkeen
- **`./testit/migraatiotesti.sh`** — ajaa migraatioketjun kertakäyttökontissa vanhasta skeemasta ja vaatii saman lopputuloksen kuin tuore asennus (vaatii Dockerin, ei muuta ympäristöä)
- **`./testit/savutesti.sh`** — savutesti: varmistaa, että MySQL + WebUI-kontit vastaavat oikein (olettaa konttien olevan käynnissä)
- **`./asenna`** — tuotantoasennus tuoreelle koneelle (vain Docker + curl tarvitaan alkuun): asentaa python3-venvin pipelinelle, rakentaa/käynnistää Docker-pinon (MySQL + WebUI + Caddy 443:ssa, Let's Encrypt TLS-ALPN-01), ajaa tietokantamigraatiot ja todentaa skeeman (`skeematarkistus.sh`; keskeytyy jos kanta ei vastaa tavoitetta), asentaa `vahtikoira`-cronin. Idempotentti — uudelleenajo on turvallista. Vaatii `.env`:iin `TUOTANTO_DOMAIN`:in etukäteen.
- **`./vahtikoira`** — cron-terveystarkistus tuotannolle (asennetaan `asenna`:n toimesta, ajaa minuutin välein): käynnistää pysähtyneet kontit; kova `docker compose restart` vasta 10 min yhtäjaksoisen epäkunnon jälkeen (ei keskeytä Caddyn ACME-sertifikaatin hakua). Kova restart koskee vain `caddy`- ja `webui`-kontteja — mysql restartataan vain jos se on itse epäterve, koska kannan katkaisu kaataa kesken olevan pipeline-ajon. Käsin debugatessa `touch .vahtikoira_tauolla` (vanhenee 2 h:ssa)
- **`./paivittaja`** — tuotannon automaattipäivitys (root-cron 5 min, `/etc/cron.d/opserver`, asennetaan `asenna`:n toimesta): uusi origin/main → savutesti → `varmuuskopio` → ff-pull → `./asenna` → savutesti; epäonnistuessa koodi + kanta palautetaan, GitHub-issue (`GITHUB_ISSUE_TOKEN` .env:ssä) eikä samaa versiota yritetä uudelleen (`.paivitys_epaonnistui`). Jos sivu on rikki jo ennen päivitystä: ei päivitetä, issue kerran per versio (`.paivitys_rikki_ilmoitettu`). Jos pipeline (`cliui.valikko`) on käynnissä, lopettaa heti ennen fetchiä
- **`./varmuuskopio [nimi]`** / **`./varmuuskopio --palauta TIED`** — mysqldump (gzip) hakemistoon `/var/backups/opserver`, 14 vrk säilytys; cron joka yö 03:15. `asenna` asentaa myös unattended-upgradesin (uudelleenkäynnistys tarvittaessa 04:30)
- **`./testit/paivittajatesti.sh`** / **`./testit/varmuuskopiotesti.sh`** — päivittäjän logiikka stubeilla (ei Dockeria) / dumppi+palautus kertakäyttökontissa (vaatii Dockerin)
- **`./testit/vahtikoiratesti.sh`** — varmistaa stub-dockerilla, ettei vahtikoira restartoi tervettä mysqliä (ei vaadi Dockeria)

## WebUI-käytännöt (huono yhteys + yhteisöllinen annotointi)

WebUI:ta käytetään yhteisöllisissä sessioissa usein huonolla, katkeilevalla yhteydellä. Uusi koodi noudattaa samoja rakennuspalikoita:

- **Datan haku:** `haeJson(url)` (`yhteiset.js`) — yrittää uudelleen verkkovirheessä/5xx ja katkaisee jumittuneen haun (20 s). Isot listat sivutetaan palvelimella (`?sivu&koko` / `?alku&koko`) ja renderöidään osa kerrallaan; näkymä ja otsikko näytetään heti, data täyttyy perässä. Palvelin pakkaa vastaukset (gzip).
- **Käyttäjän toimenpide (tallentava nappi):** aina `lahetaNapilla(nappi, url, runko)` (`lahetys.js`) — lähetys-/odotusanimaatio ja automaattinen uudelleenlähetys. Siksi **jokaisen kirjoittavan API-käsittelijän on oltava idempotentti** (upsert, "jo olemassa = onnistui", ei tuplarivejä historiatauluihin). Ei tallennuksia WebSocketin kautta ilman kuittausta.
- **Korjausmodaali (HITL):** jaettu lomake `avaaLomakesessio(avain, modaali, …)` (`lomakesessio.js`): kentät `data-jaettu="…"`, modaalin avaava nappi `data-lomake="<avain>"`. Muut näkevät avoimen lomakkeen napin kohdalla ja voivat liittyä siihen.
- **Läsnäolo:** kaikki "missä käyttäjä on" -tieto kulkee `yhteistyo.js`:n `lahetaTila()`-objektissa (sivu, nakyma, sivunumero, lomake, katselu, tekeminen, sijainti) → muiden pallurat oikeaan kohtaan. Uusi sijaintitaso = uusi kenttä siihen. Lähettäjä muodostaa tiedon itse (esim. `tekeminen`-kuvaus: avoimen modaalin `kuvaus`, muuten `omaSivuKuvaus`), vastaanottaja vain näyttää.
- **Modaalit läsnäolossa:** jokaisella modaalilla on ankkuri `data-lomake="<avain>"` (avausnappi, kurssin nimi, logo). Jaettu lomake → `avaaLomakesessio`; katselumodaali (ei jaettuja kenttiä) → `naytaKatselumodaali(modaali, avain, kuvaus)` + `kytkeKatselumodaali` (`yhteiset.js`). Sama ankkuri antaa ilmaiseksi sykkivän kehyksen, pikkupallurat, reunakursorin ja `siirryKayttajanLuo`-avauksen (ankkurin klikkaus). Katselu näkyy vain samalla sivulla/näkymässä, jaettu lomake kaikissa (`modaaliAvain`).
- **Kursorien sijainti** (`osoittimenSijainti`): modaalissa sisältölaatikon suhteen, kiinteässä yläpalkissa näkymän koordinaateissa, muuten sivun. Reunapallurat rajataan yläpalkin alareunaan; vieritys päivittää oman sijainnin. Pallura-kerrokset ovat `pointer-events: none` (eivät estä klikkauksia) → tooltip `data-tooltip` + geometrinen osuma (`kytkeTooltipit`), ei `title`.
- **Kurssilistat:** paikannus (`luoPaikannin`, `paikannus.js`) ja kaikki listaus- ja paikannuskyselyt jakavat näkymän parametrit (`luokitusNakyma`) ja järjestyksen (`_luokitus_jarjestys_sql`, päättyy `k.KID` — vakaa sivutus). Taustan vierityslukko kaikille modaaleille on CSS:ssä (`html:has(.modaali:not(.piilotettu))`).
- **Klassiset skriptit jakavat globaalin näkyvyysalueen:** kääri modaalitiedostot lohkoon ja vie ulos vain `window.*`. Näkymätiedostot (`kurssit.js`, `luokitukset.js`, …) jakavat globaalit tarkoituksella; latauksen aikana kutsuttavan tai luettavan määrittelyn tiedoston on oltava `index.html`:ssä aiemmin (`yhteiset.js` ensin, `sovellus.js` käynnistää näkymien jälkeen). Testi estää päällekkäiset globaalit funktiot ja `let`/`const`-nimet ja vaatii jokaisen `.js`:n `index.html`:ään `?v=N`:llä.
- **Todenna selaimella ennen PR:ää:** headless-Chromium tuotantokokoista paikallista kantaa vasten, useampi käyttäjä = eri browser context; verkkokatkos/hitaus CDP:n verkkoemulaatiolla.

## Vaiheiden valmistumiskriteerit

1. **Haku:** Tietokannassa on kurssirivit otsikolla, kuvauksella, tiedekunnalla, tasolla ja lähde-URL:lla
2. **Seulonta:** Jokaisella haussa löydetyllä kurssilla on mukaan/pois-päätös ja per-kysymys LLM-vastaukset tallennettuna
3. **Arviointi:** Jokaisella mukaan otetulla kurssilla on jäsennellyt arviointivastaukset tallennettuna
4. **Raportti:** Ihmisluettava raportti generoitu tietokannan tilasta; sisältää %-osuuden riittämättömiksi merkityistä oppaista
5. **HITL-silmukat:** Käyttöliittymä antaa ihmisen merkitä virheet ja valita juurisyyn; käynnistää uudelleenajon tai annotoinnin
