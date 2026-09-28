# TASKS.md — avoimet löydökset

Session-aikana (2026-09-22, tuotannon `asenna`/Caddy/migraatio-työ) havaittuja
asioita jotka mainittiin mutta ei korjattu tai vahvistettu käyttäjän kanssa.
Triagoi: korjaa tai sulje.

## 1. savutesti.sh ei tarkista caddy-konttia

`testit/savutesti.sh:133-134` tarkistaa vain `mysql`- ja `webui`-palvelut:

```
tarkista_kontti "MySQL-kontti käynnissä"  "mysql"
tarkista_kontti "WebUI-kontti käynnissä"  "webui"
```

`caddy` (lisätty PR #10:ssä, tuotannon HTTPS-käänteisproxy) puuttuu kokonaan.
Jos caddy kaatuu mutta mysql+webui ovat pystyssä, HTTP-tarkistukset
epäonnistuvat mutta mikään ei suoraan kerro caddyn olevan syypää. Lisää:
`tarkista_kontti "Caddy-kontti käynnissä" "caddy"`.

## 2. DEMO.md vanhentunut: webui ei enää julkaise porttia 12121 suoraan

PR #10 (Caddy 443:een) muutti `webui`-palvelun `ports:` → `expose:` — portti
12121 ei enää näy hostiin, vain sisäverkkoon. `DEMO.md`:n ohjeet
(`curl http://localhost:12121/...`, `tailscale funnel --bg 12121`) olettavat
että 12121 on julkaistu hostiin. Tuotannossa (Caddy edessä, 443 jo HTTPS)
Funnelia ei enää tarvita — DEMO.md pitäisi päivittää erottamaan
paikalliskehitys (12121 voi olla auki riippuen compose-asetuksista) ja
tuotanto (443 Caddyn kautta, ei Funnelia) toisistaan.

## 3. vahtikoira: ei tauko-mekanismia manuaalista debuggausta varten

Havaittu tuotannossa (esr-project): vahtikoiran 10 min -kärsivällisyyskynnys
(PR #13) EI nollaudu kun operaattori käynnistää kontin käsin — se laskee
kumulatiivisesta "epäkunnossa"-ajasta ensimmäisestä havainnosta, ei
viimeisimmästä käsin tehdystä käynnistyksestä. Tämä keskeytti käyttäjän
Caddy/ACME-debuggauksen kesken kahdesti saman session aikana (operaattori
joutui poistamaan cron-rivin käsin väliaikaisesti selvitäkseen).

Ehdotettu korjaus (tarjottu, käyttäjä ei ehtinyt vastata "sopiiko?"):
`vahtikoira` tarkistaa ensimmäisenä `.vahtikoira_pysahdyksissa`-tiedoston
olemassaolon ja poistuu heti jos se löytyy — operaattori voi `touch`ata sen
ennen manuaalista debuggausta ja poistaa jälkeenpäin.

## 4. Tuotannon caddy jäi `Restarting`-tilaan asennusajon lopussa — SELVITETTY

`Restarting` on pelkkä `docker compose restart caddy` -komennon tuloste.
Todellinen vika (2026-09-27): `asenna`:n lopputarkistus ("WebUI ei vastannut
60 s") epäonnistui aina, koska vahtikoira curlasi `https://localhost/` ja
Caddylla on sertti vain domainille (TLS exit 35). Korjattu PR #34:ssä. Sulje,
kun #34 on yhdistetty — ks. kohta 6.

## 5. Monilauseinen migraatio katkeaa ensimmäiseen duplikaattiin — loput lauseet jäävät hiljaa ajamatta

`asenna`:n migraatioajuri tulkitsee duplikaattiluokan virheen "jo
sovellettu" -tilanteeksi ja merkitsee tiedoston tehdyksi. `mysql` kuitenkin
pysähtyy ensimmäiseen virheeseen, joten saman tiedoston myöhemmät lauseet
jäävät ajamatta vaikka ne olisivat oikeasti tarpeen. Tämä nähtiin
2026-09-22 tuotannossa (esim. migraatio_004, 008-010, 016-017 ohitettiin).
Seuraukset havaitaan nyt `./testit/skeematarkistus.sh`:lla, mutta itse ansaa
ei ole poistettu. Vaihtoehto: aja migraatiot `mysql --force`:lla ja päätä
vasta kaikkien lauseiden virheistä, onko tiedosto oikeasti sovellettu.

## 6. Tarkista tuotannon vahtikoira.log: restartoiko cron caddy+webui 10 min välein?

Ennen PR #34:ää vahtikoiran terveystarkistus (`https://localhost/`) ei voinut
koskaan onnistua, joten cronin pitäisi olla tehnyt kova restart caddylle ja
webuille ~10 min välein asennuksesta lähtien (katkoksia käyttäjille, turhia
Caddy-restartteja). Ei vahvistettu. Tarkistus tuotannossa:
`grep -c restart ~/Opserver/vahtikoira.log`. #34:n jälkeen rivejä ei pitäisi
enää tulla.

## 7. pura_vastaus: jäljellä olevat jäsennysaukot (hypoteesi, ei havaittu)

Tuotannon raaka-JSON-rivit (esr_kyber) korjattiin 2026-09-27 (PR #31 + #35,
viimeiset 6 päättyivät `},`). Kaksi mahdollista aukkoa jäi, dataa ei nähty:
- `vapaa_teksti`-kysymys, jolle malli palauttaa objektin → `str(raw)` tallentaa
  Python-reprin (`{'perustelu': ...}`), joka ei ole JSONia eikä korjaannu.
- `hae_raakana_tallennetut_vastaukset` hakee `LIKE '{%'`, joten tyhjällä tai
  ```` ```json ````-aidalla alkava rivi ei löydy korjaustoiminnolle.
Tarkistus: `./db "... WHERE v.Vastaus LIKE '%perustelu%'"` (ks. #35:n keskustelu).
Jos rivejä löytyy, korjaa `pura_vastaus` + testi.

## 8. Tiedostokokoraja ylittyy: sovellus.js 1577 riviä (raja ~500)

CLAUDE.md: "jokaisen tiedoston täytyy olla niin pieni, että Claude pystyy
lukemaan sen kerralla (~500 riviä)". Tilanne 2026-09-27: `webui/staattinen/sovellus.js`
1577, `tietokanta/mallit.py` 1259, `webui/palvelin.py` 871, `webui/staattinen/yhteistyo.js`
638 riviä. `sovellus.js`:n luku vaatii jo kaksi osaa, ja kasvu jatkuu jokaisen
WebUI-ominaisuuden myötä. Ehdotus: jaa `sovellus.js` näkymittäin (korkeakoulut/kurssit,
tutkimuksen kurssit + HITL, arvioinnit, raportti) omiin tiedostoihinsa (lohkoon
käärittyinä, ks. globaalien törmäystesti) ja `mallit.py` aihepiireittäin.

## 9. Kapea ikkuna (~520 px): yläpalkin muiden käyttäjien ympyrät menevät logon päälle

Havaittu 2026-09-27 PR #44:n selaintestissä (leveys 520 px): `#muut-ympyrat`
(muiden käyttäjien 24 px profiiliympyrät headerissa) piirtyvät Opserver-logon päälle.
Ei #44:n aiheuttama (vanha layout). Puhelimella/zoomilla sama. Korjaus esim.
flex-wrap/rivitys headerin oikeaan reunaan tai ympyröiden piilotus kapealla.

## 10. Modaalin avaamisen jälkeen heti kirjoitettu teksti voi korvautua (WS-liittymisen kilpailutilanne)

Havaittu 2026-09-27 selaintestissä: raporttimodaalissa (`raporttimuokkaus.js`)
heti avaamisen jälkeen kirjoitettu teksti ylikirjoittui, kun WebSocket-session
liittymisvastaus (osion teksti palvelimelta) saapui perässä. Sama rakenne on
jaetussa korjauslomakkeessa (`lomakesessio.js`): ensimmäinen `lomake-sessio`-vastaus
asettaa kaikki kentät palvelimen arvoihin, joten ennen vastausta (hitaalla
yhteydellä sekunteja) kirjoitetut merkit katoavat. Ihminen ehtii harvoin
kirjoittaa ennen vastausta hyvällä yhteydellä, mutta huonolla kyllä. Korjaus: älä
ylikirjoita kenttää, jota käyttäjä on jo muuttanut ennen ensimmäistä vastausta
(lähetä muutos sen sijaan), tai lukitse kentät kunnes sessio on alustettu.

## 11. Logo Opserver.png 212 kt kilpailee kaistasta hitaalla yhteydellä

PR #39:n mittauksessa (400 kbit/s) logo latautui ~10 s ja jakoi kaistan
datan kanssa. Pienennä (esim. oikean kokoinen PNG/WebP, tai SVG) — muutaman
rivin muutos, mutta ei tehty #39:ssä rajauksen vuoksi.

## 12. Tuotannon /api/tasot 27–75 s ja /api/lukuvuodet 64 s — verkko vai kone?

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
HITL-korjauksesta ja peukutuksesta (`sovellus.js` ~792, ~809) — ei
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

## 15. Yläpalkin piilotustila ei säily uudelleenlatauksessa

PR #46: yläpalkin ^/☰-piilotus on pelkkä `header.koottu`-luokka; sivun
uudelleenlataus palauttaa valikon näkyviin. Tarjottu (ei vastausta):
`localStorage`-muisti, yksi rivi (`sovellus.js`, `valikkovihje`-kuuntelija +
alustus). Päätä tarvitaanko.
