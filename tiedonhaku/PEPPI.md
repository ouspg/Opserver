# Peppi-opinto-oppaan rajapinta (Oulun yliopisto)

Havainnot Oulun yliopiston Peppi-opinto-oppaasta. Sama rakenne pätee todennäköisesti
muihinkin Peppi-pohjaisiin opinto-oppaisiin, mutta osoitteet ja id:t ovat instanssikohtaisia.

## Yleiskuva

- **Frontend (SPA):** `https://opas.peppi.oulu.fi` — Angular-sovellus, ei sisällä dataa HTML:ssä.
- **Backend (REST/JSON):** `https://opasbe.peppi.oulu.fi/api` — kaikki data haetaan täältä.
  - Frontendin JS-bundlessa: `backendUrl = "opasbe.peppi.oulu.fi"`, kutsut muotoa `//{backendUrl}/api/{polku}{?period=}`.
- **robots.txt:** ei varsinaista robots.txt:ää (palauttaa SPA:n). Ollaan silti kohteliaita: viive pyyntöjen välillä (`CRAWL_DELAY_SECONDS`).
- **Kausiparametri:** lähes kaikki kutsut vaativat `?period=`-parametrin. Nykyinen kausi: **`2025-2026`**.
  Formaatti on `{alkuvuosi}-{loppuvuosi}` (esim. monivuotiset opsit `2018-2020`).
  Tyhjä `?period=` → HTTP 404; väärä mutta validin muotoinen kausi → `200 []`.

## Datamalli

Hierarkia (juuresta kursseihin):

```
navigation-kategoria        (esim. "Perustutkintokoulutukset")  id 11738
  └─ EDUCATION              (koulutus, esim. "Computer Science…")  id 43205
       └─ PROGRAMME         (ohjelma)                              id 45691
            └─ STUDY_MODULE  (opintokokonaisuus, rekursiivinen)
                 └─ COURSE_UNIT  (opintojakso = haettava kurssi)   id 2628
                      └─ OFFERING (toteutus, ei tarvita)
```

Kaikki nimet ovat monikielisiä objekteja: `{"valueFi": "...", "valueEn": "...", "valueSv": "..."}`.

## Hakustrategia (kaikki kurssit)

1. **`GET /api/navigation?period=2025-2026`**
   → lista ylätason kategorioita (`id`, `name`, `type`, `organisationView`).
   Kiinnostavat tutkintokoulutus-kategoriat, esim. `11738` (perustutkinnot 3+2v),
   `11739` (kandit), `11740` (maisterit).

2. **`GET /api/education/{kategoriaId}/education-type?period=2025-2026`**
   → lista `EDUCATION`-solmuja. Jokaisella `children`-kentässä `PROGRAMME`-solmut (ohjelma-id:t).
   Huom: tämä endpoint ottaa **navigation-kategorian id:n**, ei tiedekunnan id:tä.
   (`/api/education/{tiedekuntaId}/education-type` palauttaa tyhjän.)

3. **`GET /api/accomplishment-plan/{ohjelmaId}?period=2025-2026`**
   → ohjelman koko opetussuunnitelmapuu (rekursiivinen `children`).
   Käy puu läpi ja kerää kaikki solmut, joilla `type == "COURSE_UNIT"`.
   Solmusta saa: `id`, `code`, `name`, `minCredits`/`maxCredits`, `hasRealizations`.

4. **`GET /api/course/{courseUnitId}?period=2025-2026`**
   → yksittäisen kurssin täydet tiedot (ks. alla). Tämä on varsinainen kurssikuvauksen lähde.

Sama `COURSE_UNIT` esiintyy useassa ohjelmassa → **dedupataan `id`:n perusteella**
ennen `/api/course/{id}` -kutsuja (säästää pyyntöjä ja on idempotenttia).

## Kurssin tiedot: `GET /api/course/{id}`

```json
{
  "id": "2628",
  "code": "405023Y",
  "name": { "valueFi": "Opintoihin orientoituminen", "valueEn": "Orientation to studies" },
  "credits": 1.0,
  "minCredits": 1,
  "maxCredits": 1,
  "tags": [],
  "contentList": [
    { "title": {"valueFi": "Osaamistavoitteet"}, "content": {"valueFi": "..."} },
    { "title": {"valueFi": "Sisältö"},           "content": {"valueFi": "..."} }
  ]
}
```

- **Kurssikuvaus** (`OpsKuvaus`-kenttäämme varten) kootaan `contentList`-listan
  `title` + `content` -pareista (esim. Osaamistavoitteet, Sisältö, Edeltävät opinnot).
  Tekstissä on `\r\n` ja markdown-tyylistä listamerkintää (`*`).

## Kytkentä `Kurssi`-tauluun

| Kurssi-sarake   | Lähde Peppi-rajapinnasta                                        |
|-----------------|----------------------------------------------------------------|
| `KurssiNimi`    | `course.name.valueFi` (fallback `valueEn`)                      |
| `Opintopisteet` | `course.credits` (tai `minCredits`/`maxCredits`)               |
| `OpsKuvaus`     | `contentList` koottuna tekstiksi                                |
| `Oppiaine`      | johdettava ohjelmasta/EDUCATIONista tai kurssikoodin prefiksistä |
| `Taso`          | ei suoraan rajapinnassa — ks. avoin kysymys alla               |
| `KKID`          | meidän tietokannasta (Oulun yliopisto)                          |

## Avoimet kysymykset

- **Taso** (yleis/perus/aine/syventävä): ei suoraan `course`-vastauksessa. Kurssikoodin
  loppukirjain on perinteinen vihje (Oulussa esim. `Y`=yleisopinnot, `P`=perus, `A`=aine,
  `S`=syventävä). Varmistettava ennen suodatuksen (kohta 6) toteutusta.
- **Oppiaine / tiedekunta:** EDUCATION/PROGRAMME-solmun nimestä tai koodista johdettavissa,
  mutta suora tiedekunta→ohjelma-mappaus ei tullut esiin. `/api/organisation` listaa
  tiedekunnat (id + nimi), mutta `/api/organisation/{id}` palauttaa vain solmun metatiedot.
- **Kausi:** kovakoodataanko `2025-2026` vai luetaanko ohjelmallisesti? (Frontend lukee sen
  jostain konfiguraatiosta; ei vielä löydetty erillistä period-listausendpointtia.)

## Hyödylliset lisäendpointit (eivät pakollisia perushaussa)

- `GET /api/organisation` → tiedekuntien lista (id + monikielinen nimi).
- `GET /api/realizations/course/{id}?period=` → kurssin toteutukset.
- `GET /api/programme/{id}/description?period=` → ohjelman kuvausteksti.
- `GET /api/navigation` / `…/links` / `/api/text/{avain}` → UI-tekstejä, ei kurssidataa.

## Tutkimusmenetelmä (miten yllä oleva selvitettiin)

1. JS-bundlen (`main.*.js`) analyysi: `backendUrl`, `/api/`-polkujen rakennus.
2. Endpointtien koeammunta `curl`:lla.
3. Oikeiden pyyntöjen kaappaus Playwrightilla (järjestelmän Chrome, headless):
   ladattiin etusivu → ohjelma → kurssi ja kirjattiin kaikki `opasbe`-pyynnöt.
