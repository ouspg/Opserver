# LLM-arviointiprotokolla

## Viestin rakenne

LLM:lle lähetetään yksi pyyntö per erä kursseja. Viesti koostuu neljästä osasta järjestyksessä:

```
[Järjestelmäkehote]
[Arviointikehote]
[Tarkentavat kysymykset]
[JSON-taulukko arvioitavista kursseista]
```

### 1. Järjestelmäkehote

Vakioteksti, joka asettaa LLM:n rooliin ja määrittelee vastausformaatin (JSON).
Tallennetaan tiedostoon `kehoteet/jarjestelma.txt`.

### 2. Arviointikehote

Tutkimuskohtainen teksti, joka kuvaa mitä tutkitaan ja millä kriteereillä.
Tallennetaan tietokantaan (`Tutkimus.Arviointikehote`).

### 3. Tarkentavat kysymykset

Lista `Kysymykset`-taulun riveistä, muotoiltuna esim.:

```
Vastaa jokaiselle kurssille seuraaviin kysymyksiin:
1. Onko kurssi suunnattu tietojenkäsittelytieteen opiskelijoille?
2. Käsitteleekö kurssi verkkoturvallisuutta tai kryptografiaa?
3. Soveltuuko kurssi kyberturvallisuuden ESR-hankkeeseen?
```

Kysymykset haetaan tietokannasta järjestyksessä `KysID ASC`.

### 4. Arvioitavat kurssit (JSON)

```json
[
  {"id": 42, "nimi": "Tietoverkot", "kuvaus": "..."},
  {"id": 57, "nimi": "Ohjelmointi 1", "kuvaus": "..."}
]
```

## Erän koon laskenta

Erän koko sovitetaan niin, että koko viesti mahtuu mallin konteksti-ikkunaan.
Laskentakaava (arvio):

```
vapaa_tokeneja = max_konteksti - jarjestelma_tokenit - arviointikehote_tokenit
                 - kysymykset_tokenit - vastaustila_per_kurssi * max_kurssit
erä_koko = floor(vapaa_tokeneja / kurssi_tokenit_keskiarvo)
```

Käytännössä `kurssi_tokenit_keskiarvo` arvioidaan ensimmäisen haun perusteella
tai käyttäjä voi asettaa sen manuaalisesti.

## Vastauksen rakenne

LLM pakotetaan palauttamaan JSON-taulukko:

```json
[
  {
    "id": 42,
    "vastaukset": ["Kyllä", "Ei", "Kyllä"]
  },
  {
    "id": 57,
    "vastaukset": ["Kyllä", "Ei", "Ei"]
  }
]
```

- `id`: kurssin `KID`
- `vastaukset`: lista vastauksista samassa järjestyksessä kuin kysymykset

Vastaukset tallennetaan `Vastaukset`-tauluun: yksi rivi per (KysID, KID).

## Tietokantakaavio

```
Tutkimus (TID)
  └── Kysymykset (KysID, TID, Kysymys)
        └── Vastaukset (VasID, KysID, KID, Vastaus)
```

## Idempotenssi

Arviointivaiheen uudelleenajo on turvallista: `Vastaukset` käyttää
`ON DUPLICATE KEY UPDATE`, joten olemassa olevat vastaukset ylikirjoitetaan
uusilla arvoilla.
