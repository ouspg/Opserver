"use strict";

// Yhteysilmoitus: yksi käyttöä estämätön palkki alareunassa kaikille yhteyskatkoille
// (haeJson, lahetaNapilla, WebSocket).
//   - yhteysKatkennut(avain, syy) / yhteysPalautui(avain): katkolähteet avaimittain;
//     palkki näkyy, kun yksikin lähde on katki (syy "huolto" = palvelin päivittyy).
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

  function piirra() {
    let palkki = document.getElementById("yhteysilmoitus");
    if (!palkki) {
      palkki = document.createElement("div");
      palkki.id = "yhteysilmoitus";
      palkki.setAttribute("role", "status");
      document.body.appendChild(palkki);
    }
    const syy = [...katkot.values()].pop();
    palkki.className = syy ? "katko" : "piilotettu";
    if (syy) palkki.textContent = TEKSTIT[syy];
  }

  window.yhteysKatkennut = (avain, syy = "yhteys") => {
    if (katkot.get(avain) === syy) return;
    katkot.delete(avain);  // uusin syy viimeiseksi
    katkot.set(avain, syy);
    piirra();
  };

  // Palauttaa true, jos avain oli katki.
  window.yhteysPalautui = (avain) => {
    if (!katkot.delete(avain)) return false;
    piirra();
    return true;
  };
}
