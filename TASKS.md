# TASKS.md — avoimet löydökset

Session-aikana (2026-09-22, tuotannon `asenna`/Caddy/migraatio-työ) havaittuja
asioita jotka mainittiin mutta ei korjattu tai vahvistettu käyttäjän kanssa.
Triagoi: korjaa tai sulje.

## 9. Kapea ikkuna (~520 px): yläpalkin muiden käyttäjien ympyrät menevät logon päälle

Havaittu 2026-09-27 PR #44:n selaintestissä (leveys 520 px): `#muut-ympyrat`
(muiden käyttäjien 24 px profiiliympyrät headerissa) piirtyvät Opserver-logon päälle.
Ei #44:n aiheuttama (vanha layout). Puhelimella/zoomilla sama. Korjaus esim.
flex-wrap/rivitys headerin oikeaan reunaan tai ympyröiden piilotus kapealla.

## 11. Logo Opserver.png 212 kt kilpailee kaistasta hitaalla yhteydellä

PR #39:n mittauksessa (400 kbit/s) logo latautui ~10 s ja jakoi kaistan
datan kanssa. Pienennä (esim. oikean kokoinen PNG/WebP, tai SVG) — muutaman
rivin muutos, mutta ei tehty #39:ssä rajauksen vuoksi.

## 12. Tuotannon /api/tasot 27–75 s ja /api/lukuvuodet 64 s — verkko vai kone? — SELVITETTY

**2026-09-29:** kone, ei verkko. OpsKuvaus (ka. 6,3 kt) mahtui InnoDB-riville →
Kurssi ~250 Mt > 128 Mt buffer pool → jokainen Kurssin läpikäynti luki levyltä
(odottaa/hylätty-listat 9–22 s). Korjattu PR #61 (KurssiKuvaus-taulu, migraatio
025); tuotannossa mitattuna jälkeenpäin kaikki listat/määrät 0,1–0,6 s. Sulje.


2026-09-27 mitattuna klaudekin katkeilevan yhteyden yli tuotannosta: `/api/tasot`
27–75 s (yksi aikakatkaisu), `/api/lukuvuodet` 6–64 s, vaikka vastaukset ovat
alle 400 tavua. Paikallisesti tuotannon kokoisella datalla (Colima, 414 Mt) samat
kutsut <0,4 s kylmänäkin. Todennäköisesti mittaajan verkko, mutta ei vahvistettu:
kone voi olla muistin/levyn rajoittama (kyselyt skannaavat koko `Kurssi`-taulun,
jossa ~8 kt OpsKuvaus/rivi). Tarkistus tuotantokoneella itsellään:
`time curl -s -o /dev/null -u … https://<domain>/api/tasot` (tai mysql:n
`SELECT Taso … GROUP BY Taso` -aika). Jos hidas: kattava indeksi `(Taso)` tai
tasot-välimuistin TTL:n pidennys.

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

## 14. Modaalissa oleva käyttäjä näkymätön, jos hänen HITL-nappiaan ei ole renderöity

PR #50: kun B on HITL-modaalissa ja A samassa suodatinnäkymässä, B:n pallura
osoittaa A:n ruudun reunalta kohti B:n lomakkeen avausnappia (`[data-lomake]`).
Jos nappia ei ole A:n DOMissa lainkaan (eri sivutussivu, `?alku&koko` /
osittainen renderöinti ei vielä ehtinyt, eri välilehti mukana/hylätty), suuntaa
ei tiedetä ja B on A:lle taas näkymätön (`yhteistyo.js` `paivitaKursorit`,
`ponytail:`-kommentti). Päätä: riittääkö, vai esim. pallura reunaan/nurkkaan
"muualla tällä sivulla" -merkinnällä tai sivutusnapin viereen.

## 16. Kannan varmuuskopiot vain tuotantokoneen omalla levyllä (offsite puuttuu)

PR #53 (`varmuuskopio`): dumpit → `/var/backups/opserver/` samalla koneella →
eivät kestä levyn/koneen menetystä eivätkä murtoa (root voi poistaa ne).
Suositus: toinen kone *hakee* dumpit (pull, esim. `rsync` ssh:lla lukuoikeudella),
jolloin tuotantokone ei pääse poistamaan kopioita. Kysytty käyttäjältä
2026-09-28 — kohdekone päättämättä. Harkitse samalla `.env`:n (LLM-avain,
GITHUB_ISSUE_TOKEN) säilytystä muualla.

## 18. paivittaja käsin ajettuna: hiljainen exit 0 ei kerro syytä

Tuotannossa 2026-09-28 (`ubuntu@esr-project`): `sudo ./paivittaja` → `exit 0`,
`paivittaja.log` tyhjä. Hiljaisia poistumisia on neljä (lukko, `cliui.valikko`
käynnissä, HEAD == origin/main, versio `.paivitys_epaonnistui`:ssa) — cronille
oikein (ei lokispämmiä 5 min välein), mutta käsin testaava ei näe miksi.
Syy jäi todentamatta (todennäköisesti HEAD == origin/main; ohjeeksi annettu
`sudo bash -x ./paivittaja 2>&1 | tail -15`). Ehdotus: jos `[[ -t 1 ]]`
(pääte), tulosta poistumisen syy; cronissa pysyy hiljaisena.

## 19. MySQL:n innodb_buffer_pool_size on tuotannossa oletus 128 Mt

2026-09-29 (PR #61:n juurisyy): `docker-compose.yml`:n mysql-palvelu ei aseta
`--innodb-buffer-pool-size`a. Nyt kuuma data mahtuu (Kurssi ~6 Mt, Kurssiluokitus
~10 Mt; KurssiKuvaus ~250 Mt luetaan vain rivi kerrallaan), mutta kun
korkeakouluja/lukuvuosia/tutkimuksia lisätään, sama levyltä-luku-ilmiö palaa
huomaamatta. Tarkista tuotantokoneen RAM (`free -h`) ja harkitse esim. 512 Mt–1 Gt
asetusta compose-komentoriville. Mittari: `Innodb_buffer_pool_reads` kasvaa
tasaisen kuorman alla.

## 20. Syvä sivutus hidas: hylätty sivu 301/318 = 1,6 s

2026-09-29 tuotannossa: `/luokitukset?tila=hylätty&sivu=300&koko=100` 1,6 s
(sivu 0: 0,4 s). `ORDER BY k.KurssiNimi LIMIT 100 OFFSET 30000` järjestää ja
ohittaa ~30 k riviä. Uusi sivunumerovalitsin (PR #56) tekee viimeisille sivuille
hyppäämisestä helppoa. Jos haittaa: keyset-sivutus (WHERE KurssiNimi > viimeinen)
tai kattava indeksi `(KKID, VuosiAlku, VuosiLoppu, KurssiNimi)`.

## 22. Nukkuvan/kummituksen zzZ ei erotu 8–10 px pallurissa

PR #57: zzZ piirretään canvasin sisään; 24–28 px pallurissa luettava, mutta
alavalikon (8 px), välilehti- ja sivutuspallurissa (10 px) se on valkoinen
läiskä. Harmaa väri ja kummituksen läpinäkyvyys erottuvat silti. Jos haittaa:
pieniin pallurihin pelkkä "z" tai CSS-merkki canvasin viereen.

## 23. Tuotannon automaattipäivityksen toipuminen #74:n jälkeen todentamatta

Issuet #63/#68/#72: webui-kontti jäi ajamaan poistettua kuvaa (containerd antaa
rebuildissa uuden ID:n, compose ei luonut konttia uudelleen) → savutestin
kuvatuoreus FAIL esti päivitykset. PR #74 korjaa `asenna`:n, mutta päivittäjän
esitarkistus kaatuu yhä vanhaan konttiin, joten tuotannossa tarvitaan kerran
`cd ~/Opserver && sudo docker compose up -d --force-recreate webui`. Todenna:
`sudo docker compose ps` (webui IMAGE = `opserver-webui`, ei `sha256:…`),
`tail paivittaja.log` ("päivitetty: …" uusimpaan mainiin) ja ettei uusia
"Automaattipäivitys epäonnistui" -issueita synny. Uudet issuet sisältävät nyt
ajon lokin (#70).

## 24. pyflakes: f-merkkijono ilman muuttujia

`cliui/luokittelunaytto.py` (n. rivi 356, ennen #78:n jakoa) ja
`raportti/_kehotteet.py` (rivit 17 ja 39): `f"..."` ilman `{}`-kenttiä. Harmiton,
mutta kohinaa lint-ajoissa; poista `f`-etuliite.

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
