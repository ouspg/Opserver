# TASKS.md — avoimet ominaisuudet ja ympäristötehtävät

Uudet ominaisuudet, ympäristö-/infrastruktuuritehtävät ja avoimet päätökset.
Nykyisen koodin korjaukset (bugit, suorituskyky, lint) ovat GitHub-issueina.

## 13. Tapahtumaloki: tallennus tietokantaan ja näyttäminen

Nykyinen "uutispalkki" (`yhteistyo.js` `lahetaUutinen`/`lisaaUutinen`,
`palvelin.py` `tyyppi == "uutinen"`) on pelkkä WS-välitys: palvelin ei tallenna
mitään, joten myöhemmin liittyvä/uudelleenlataava/yhteyskatkoksessa ollut
käyttäjä ei näe aiempia tapahtumia. Lisäksi asiakas lähettää uutisen itse
tallennuksen jälkeen (pudotetaan hiljaa jos WS ei auki) ja teksti on
vapaamuotoinen → kuka tahansa voi väärentää "uutisen". Uutisia lähtee vain
HITL-korjauksesta ja peukutuksesta (`luokitukset.js` HITL-lomake, `yhteiset.js` `lahetaHyvaksynta`) — ei
arviointi-/raporttimuokkauksista.

Tavoite:
- Palvelin kirjaa tapahtuman itse onnistuneen kirjoittavan API-kutsun
  yhteydessä (HITL, hyväksyntä, arviointi-/raporttimuokkaus) uuteen
  tauluun (`migraatio_NNN.sql`: aika, tutkimus, kurssi, toimija, tyyppi, kuvaus)
  ja broadcastaa sen WS:llä — asiakkaan `uutinen`-viesti poistetaan.
- Idempotentti: `lahetaNapilla`-uudelleenlähetys ei saa tuottaa tuplarivejä.
- Näyttäminen: liittyessä uusimmat N tapahtumaa uutispalkkiin; erillinen
  sivutettu tapahtumalokinäkymä (`?alku&koko`), suodatus tutkimuksen mukaan.

## 16. Kannan varmuuskopiot vain tuotantokoneen omalla levyllä (offsite puuttuu)

PR #53 (`varmuuskopio`): dumpit → `/var/backups/opserver/` samalla koneella →
eivät kestä levyn/koneen menetystä eivätkä murtoa (root voi poistaa ne).
Suositus: toinen kone *hakee* dumpit (pull, esim. `rsync` ssh:lla lukuoikeudella),
jolloin tuotantokone ei pääse poistamaan kopioita. Kysytty käyttäjältä
2026-09-28 — kohdekone päättämättä. Harkitse samalla `.env`:n (LLM-avain,
GITHUB_ISSUE_TOKEN) säilytystä muualla.

## 19. MySQL:n innodb_buffer_pool_size on tuotannossa oletus 128 Mt

2026-09-29 (PR #61:n juurisyy): `docker-compose.yml`:n mysql-palvelu ei aseta
`--innodb-buffer-pool-size`a. Nyt kuuma data mahtuu (Kurssi ~6 Mt, Kurssiluokitus
~10 Mt; KurssiKuvaus ~250 Mt luetaan vain rivi kerrallaan), mutta kun
korkeakouluja/lukuvuosia/tutkimuksia lisätään, sama levyltä-luku-ilmiö palaa
huomaamatta. Tarkista tuotantokoneen RAM (`free -h`) ja harkitse esim. 512 Mt–1 Gt
asetusta compose-komentoriville. Mittari: `Innodb_buffer_pool_reads` kasvaa
tasaisen kuorman alla.

## 25. GDPR: tietosuojailmoitus puuttuu; nimi ja sähköposti tallentuvat pysyvästi

Kartoitettu 2026-09-29 koodista ja perf-kannan API-vastauksista (tekninen arvio,
ei juridinen — rekisterinpitäjän, todennäköisesti Oulun yliopiston, tietosuojavastaava
vahvistaa oikeusperusteen ja ilmoituksen sisällön). **Ei toteuteta nyt.**

**Käsiteltävät henkilötiedot:**
- Korjauslomakkeiden (HITL, arvion korjaus) ja Hyväksy-napin **nimi + sähköposti** →
  `HitlKorjaus`, `Vastaukset`, `Kurssiluokitus`; ei poistoa, varmuuskopioissa 14 vrk.
  Nimi näkyy kaikille käyttäjille ("Korjannut X", 👍-tooltip, perustelupallura);
  sähköposti ei lähde selaimelle eikä sitä käytetä mihinkään. Nimi on osa
  `Vastaukset`-rivin uniikkiavainta (`KysID, KID, KayttajaNimi`).
- Vapaatekstiperustelut (voivat sisältää mitä tahansa).
- Kurssikuvauksissa mahdollisesti opettajien nimiä (julkiset opinto-oppaat) → myös
  LLM-palveluun. Tarkistamatta, perf-kannan data on synteettistä.
- Vain muistissa/selaimessa: nimimerkki + läsnäolo (sivu, hiiren sijainti) WebSocketissa;
  eväste `opserverKayttaja` (30 vrk), localStorage (`hitl_nimi`, `hitl_sahkoposti`,
  `ylapalkki_koottu`). Ei analytiikkaa eikä ulkoisia skriptejä/fontteja. Caddylla ei
  pääsylokia; uvicornin loki näkee Caddyn osoitteen (tuotannon lokeista tarkistamatta).
- Annotoijien nimiä ei lähetetä LLM:lle (vain raportin muutostiivisteessä).

**Tarvitaan:**
1. Tietosuojailmoitus (art. 13) keräyshetkellä: linkki HITL-/arviolomakkeisiin ja
   infomodaaliin (esim. `Tietosuoja.md` samalla mekanismilla kuin `Opserver.md`).
   Sisältö: rekisterinpitäjä + yhteystiedot + tietosuojavastaava, tarkoitus,
   oikeusperuste, nimen näkyminen muille, säilytysaika, oikeudet, valitusoikeus.
2. Oikeusperuste: todennäköisesti yleinen etu / tieteellinen tutkimus (6.1 e,
   tietosuojalaki 4 §) → suostumusta ei tarvita. Rekisterinpitäjän päätös.
3. Evästebanneria/suostumusta EI tarvita: tallenteet ovat palvelun toiminnan kannalta
   välttämättömiä (sähköisen viestinnän palvelulaki 205 §); mainitaan ilmoituksessa.
4. Organisaation seloste käsittelytoimista (art. 30); DPIA todennäköisesti ei tarpeen.
5. Käsittelijäsopimukset: tuotantopalvelimen ylläpitäjä; LLM-palveluntarjoaja (sijainti /
   EU:n ulkopuolinen siirto, ei käyttöä koulutukseen) jos kuvauksissa on nimiä.
6. Säilytysaika määriteltävä; oikaisu-/poistopyyntöjen käsin tehtävä prosessi dokumentoitava.

**Minimointi (suositus):** poista sähköpostikenttä (ei käyttöä) ja korvaa nimikenttä
profiilin nimimerkillä kuten Hyväksy-napissa → kantaan vain satunnaiset nimimerkit.
Ne ovat silti pseudonyymejä (käyttäjä voi vaihtaa nimimerkin omaksi nimekseen; pienessä
sessiossa tunnistettavissa), joten lyhyt ilmoitus tarvitaan yhä, mutta velvoitteet
kevenevät. Päätettävä samalla kannassa jo olevien nimien/sähköpostien käsittely
(jätetään / sähköpostit NULLiksi / nimet nimimerkeiksi) — muutos migraationa.
