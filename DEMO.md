# Demo-opas — WebUI:n esittely yleisölle

WebUI (`http://localhost:12121`) on tarkoitettu tulosten esittelyyn ja
yhteisölliseen HITL-annotointiin. Tämä opas kattaa kaksi käyttöskenaariota ja
niiden suojauksen.

## Ennen demoa

1. Kontit pystyyn: `docker compose up -d`
2. Aseta jaetut demo-tunnukset `.env`:iin (aktivoi HTTP Basic Authin):
   ```
   WEBUI_AUTH_KAYTTAJA=demo
   WEBUI_AUTH_SALASANA=<vahva-kertakäyttöinen-salasana>
   ```
3. **Rakenna webui uudelleen muutosten jälkeen** (compose välittää muuttujat konttiin):
   ```
   docker compose build webui && docker compose up -d webui
   ```
4. Tarkista että suojaus on päällä: `curl http://localhost:12121/api/tutkimukset`
   → **HTTP 401** ilman tunnuksia, 200 oikeilla (`curl -u demo:salasana ...`).

Jos `WEBUI_AUTH_*` jätetään tyhjäksi, autentikointi on pois päältä (LAN-oletus).

## Skenaario 1 — Seminaari (lähiverkko)

- Liitä palvelinkone seminaarin Wi-Fiin; jaa osallistujille koneen
  paikallisverkko-osoite (`http://<ip>:12121`) sekä tunnus + salasana.
- **Varoitus:** paikallisverkossa liikenne on salaamatonta HTTP:tä → Basic Authin
  tunnukset kulkevat **selväkielisinä** ja ovat kaapattavissa samasta Wi-Fistä.
  Tämä on hyväksyttävää, koska data on julkista (opinto-oppaiden kurssitiedot +
  tekoälyn arviot, ei henkilötietoja) ja yleisö = tarkoitettu käyttäjä.
- **Suositus:** jos salissa on nettiyhteys, käytä silti Tailscale Funnelia
  (ks. alla) — silloin saat HTTPS:n ja tunnukset eivät kulje selväkielisinä.

## Skenaario 2 — Etäkokous (Tailscale Funnel) — SUOSITELTU TAPA

Tailscale Funnel altistaa palvelimen julkiseen internetiin **HTTPS:n yli**
(Funnel päättää TLS:n). Osallistujat eivät tarvitse Tailscalea — pelkkä linkki
riittää. Basic Auth on tällöin turvallinen.

CLI on macOS-sovelluksen sisällä; tee kerran kätevä symlinkki (valinnainen):
```
sudo ln -s /Applications/Tailscale.app/Contents/MacOS/Tailscale /usr/local/bin/tailscale
```

Avaa pääsy (tulostaa julkisen `https://…ts.net`-URLin):
```
tailscale funnel --bg 12121
tailscale funnel status
```
Jaa osallistujille tuo URL **sekä** tunnus + salasana.

Sulje altistus heti demon jälkeen:
```
tailscale funnel reset
```

Ensimmäisellä kerralla Funnel voi vaatia kytkemisen päälle tilin hallinnasta
(HTTPS-sertit + Funnel-attribuutti); komento tulostaa tarvittaessa suoran linkin.

## Suositus: tarvitaanko Basic Authia parempaa?

**Ei näihin demoihin.** Data on julkista ja altistus lyhyt + ohjattu. Per-käyttäjä-
tilit / OAuth olisivat ylimitoitettuja. Tärkein teko ei ole vahvempi auth vaan
**aja aina Funnelin (HTTPS) kautta**, niin tunnukset eivät koskaan kulje
selväkielisinä.

Hyvät käytännöt:
- **Vahva, kertakäyttöinen demo-salasana**; vaihda demon jälkeen (Funnel on julkinen).
- Sulje altistus (`funnel reset`) heti kun demo loppuu.

**Vahvempi ratkaisu (per-käyttäjä-tilit + TLS myös LAN:issa) tarvitaan vain jos:**
dataan tulee henkilötietoja/arkaluonteista, altistus on pitkäkestoinen/jatkuva, tai
tarvitaan todennettu kuka-teki-mitä-vastuullisuus (nyt HITL-annotointien nimi/sähköposti
ovat itse ilmoitettuja, ei todennettuja).
