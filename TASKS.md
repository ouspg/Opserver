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
