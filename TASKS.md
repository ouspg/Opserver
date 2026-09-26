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

## 4. Tuotannon caddy jäi `Restarting`-tilaan asennusajon lopussa

Havaittu esr-projectilla 2026-09-22 onnistuneen `./asenna`-ajon lopussa:
tuloste päättyi riviin `⠇ Container opserver-caddy-1 Restarting`. Käyttäjä ei
vahvistanut tilannetta jälkikäteen, joten on auki jäikö caddy kiertämään
restart-silmukkaan (ks. [[Caddy-ACME-ansa]], PR #13). Tarkistus:
`sudo docker compose ps` + `sudo docker compose logs caddy`. Jos WebUI vastaa
HTTPS:llä, tämä voi olla pelkkä ohimenevä tila asennuksen restart-komennosta.

## 5. Monilauseinen migraatio katkeaa ensimmäiseen duplikaattiin — loput lauseet jäävät hiljaa ajamatta

`asenna`:n migraatioajuri tulkitsee duplikaattiluokan virheen "jo
sovellettu" -tilanteeksi ja merkitsee tiedoston tehdyksi. `mysql` kuitenkin
pysähtyy ensimmäiseen virheeseen, joten saman tiedoston myöhemmät lauseet
jäävät ajamatta vaikka ne olisivat oikeasti tarpeen. Tämä nähtiin
2026-09-22 tuotannossa (esim. migraatio_004, 008-010, 016-017 ohitettiin).
Seuraukset havaitaan nyt `./testit/skeematarkistus.sh`:lla, mutta itse ansaa
ei ole poistettu. Vaihtoehto: aja migraatiot `mysql --force`:lla ja päätä
vasta kaikkien lauseiden virheistä, onko tiedosto oikeasti sovellettu.

## 6. Migraationumero 021 jää väliin (020 → 022)

PR #30 toi `migraatio_020.sql`, PR #32 `migraatio_022.sql` (numeroitiin 022:ksi,
koska 020–021 olivat tuolloin varattuina yhdistämättömässä haarassa; 021 ei
lopulta mergeytynyt). Runner ajaa nimijärjestyksessä, joten aukko ei riko
mitään — mutta se hämää ("puuttuuko 021?"). Tarjottu nimeäminen 022 → 021
ennen #32:n mergeä; käyttäjä ei vastannut. Jos #32 on jo mergetty, jätä
aukko (uudelleennimeäminen mergen jälkeen rikkoisi `_migraatiot`-seurannan
kannoissa, joihin 022 on jo ajettu).

## 7. `api_arvio_korjaus` ei validoi lista-tyypin `max_kohdat`-rajaa palvelinpäässä

`webui/palvelin.py` `api_arvio_korjaus` (PR #32) tarkistaa luokittelun
sallitut luokat ja asteikon rajat, mutta lista-tyypin kohtien enimmäismäärä
(`LuokitteluMaarittely.max_kohdat`) rajoitetaan vain frontissa
(`arviointimuokkaus.js` `lisaaKohta`). Suora API-kutsu voi tallentaa
pidemmän listan kuin kysymys sallii → raporttitilastot vinoutuvat hiljaa.
Yksi tarkistus + 400-vastaus, samaan tapaan kuin luokka/pisteet.

## 8. Migraatiotestin "edellinen skeema" -skenaario ajaa migraatiot tyhjään kantaan

PR #32:n lisäämä skenaario alustaa kannan merge-base-mainin `alustus.sql`:stä
ilman rivejä. Datariippuvat migraatiolauseet (esim. 022:n
`UPDATE … SET TID` + `MODIFY … NOT NULL`, joka kaatuisi jos jokin rivi jäisi
NULLiksi) eivät siis tule testatuiksi datalla. Harkitse pientä siemenriviä
per taulu (Tutkimus, Kysymykset, Kurssi, Vastaukset) skenaarioon.
