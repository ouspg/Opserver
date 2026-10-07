"use strict";

// Yhteysilmoitus: yksi käyttöä estämätön palkki alareunassa kaikille yhteyskatkoille
// (haeJson, lahetaNapilla, WebSocket) ja päivityksen jälkeiselle uudelle versiolle.
//   - yhteysKatkennut(avain, syy) / yhteysPalautui(avain): katkolähteet avaimittain;
//     palkki näkyy, kun yksikin lähde on katki (syy "huolto" = palvelin päivittyy).
//   - tarkistaVersio(): ensimmäinen kutsu muistaa latausaikaisen version (/api/info),
//     myöhemmät vertaavat siihen. Uusi versio → automaattinen uudelleenlataus vain, jos
//     mikään modaali, jaettu lomake tai lähetys ei ole kesken; muuten ilmoitus + Lataa.
{
  // Ajastimet; selaintestit lyhentävät ne asettamalla window.YHTEYS ennen latausta.
  window.YHTEYS = Object.assign({
    elpymisAikaMs: 120_000,   // haeJson yrittää katkossa (503 / verkkovirhe) näin kauan
    viiveMaxMs: 10_000,       // yritysten välinen viive enintään (myös Retry-After)
    wsIlmoitusViiveMs: 4_000, // katkennut WebSocket näytetään vasta tämän jälkeen
    wsUudelleenMs: 3_000,     // WebSocketin uudelleenyhdistysväli (yhteistyo.js)
  }, window.YHTEYS);

  const TEKSTIT = {
    huolto: "Palvelinta päivitetään – yhdistetään uudelleen…",
    yhteys: "Yhteys palvelimeen katkesi – yhdistetään uudelleen…",
  };
  const katkot = new Map();  // avain → syy (lisäysjärjestys: uusin syy näytetään)
  let uusiVersio = false;
  let latausVersio = null;

  function piirra() {
    let palkki = document.getElementById("yhteysilmoitus");
    if (!palkki) {
      palkki = document.createElement("div");
      palkki.id = "yhteysilmoitus";
      palkki.setAttribute("role", "status");
      document.body.appendChild(palkki);
    }
    const syy = [...katkot.values()].pop();
    palkki.className = syy ? "katko" : uusiVersio ? "uusi-versio" : "piilotettu";
    if (syy) {
      palkki.textContent = TEKSTIT[syy];
    } else if (uusiVersio) {
      palkki.innerHTML = 'Uusi versio saatavilla <button type="button">Lataa</button>';
      palkki.querySelector("button").addEventListener("click", () => location.reload());
    }
  }

  window.yhteysKatkennut = (avain, syy = "yhteys") => {
    if (katkot.get(avain) === syy) return;
    katkot.delete(avain);  // uusin syy viimeiseksi
    katkot.set(avain, syy);
    piirra();
  };

  // Katko ohi → tarkista versio (palvelin on ehkä päivittynyt katkon aikana).
  // Palauttaa true, jos avain oli katki (versio tarkistettiin).
  window.yhteysPalautui = (avain) => {
    if (!katkot.delete(avain)) return false;
    piirra();
    tarkistaVersio();
    return true;
  };

  const kesken = () => document.querySelector(".modaali:not(.piilotettu), #profiili-muokkaus:not(.piilotettu)")
    || window.omaLomake?.() || window.lahetyksiaKesken > 0;

  // Suora fetch (ei haeJson): epäonnistuminen ohitetaan, seuraava toipuminen tarkistaa uudelleen.
  async function tarkistaVersio() {
    let versio;
    try {
      const r = await fetch("/api/info", { cache: "no-store" });
      if (!r.ok) return;
      versio = (await r.json()).versio;
    } catch (_) {
      return;
    }
    if (latausVersio === null) {
      latausVersio = versio;
    } else if (versio !== latausVersio && !uusiVersio) {
      if (!kesken()) { location.reload(); return; }
      uusiVersio = true;
      piirra();
    }
  }
  window.tarkistaVersio = tarkistaVersio;
  window.latausVersio = () => latausVersio;
  tarkistaVersio();
}
