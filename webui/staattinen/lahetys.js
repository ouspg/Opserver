"use strict";

// Käyttäjän toimenpiteen (napin painallus) pyyntö vikasietoisesti huonolla yhteydellä:
//   - napissa ASCII-animaatio: "Lähetetään |/-\" → lähetetty → "Odotetaan vastausta |/-\"
//   - lähetys tai vastaanotto epäonnistuu (verkkovirhe, aikakatkaisu, 5xx) → automaattinen
//     uudelleenlähetys; napissa rullaa "…odotetaan internetyhteyttä…"
// Uudelleenlähetys on turvallinen, koska palvelimen käsittelijät ovat idempotentteja.
// XHR eikä fetch: vain XHR kertoo milloin pyyntö on lähetetty (upload.onload).
{
  const PYORA = "|/-\\";
  const ODOTUSTEKSTI = " …odotetaan internetyhteyttä… ";
  const RULLAN_LEVEYS = 22;
  const RUUDUN_KESTO_MS = 120;
  const AIKARAJA_MS = 20000;
  const VIIVE_MAX_MS = 15000;

  // Yksi yritys → { status, data }; hylkää verkkovirheessä / aikakatkaisussa.
  function yritys(url, runko, lahetetty) {
    return new Promise((valmis, virhe) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", url);
      xhr.setRequestHeader("Content-Type", "application/json");
      xhr.timeout = AIKARAJA_MS;
      xhr.upload.onload = lahetetty;
      xhr.onload = () => {
        let data = {};
        try { data = JSON.parse(xhr.responseText); } catch (_) { /* ei JSONia */ }
        valmis({ status: xhr.status, data });
      };
      xhr.onerror = xhr.ontimeout = () => virhe(new Error("yhteysvirhe"));
      xhr.send(JSON.stringify(runko));
    });
  }

  // Odota viive — tai vähemmän, jos selain ilmoittaa yhteyden palanneen.
  function odotaYhteytta(ms) {
    return new Promise((valmis) => {
      const ajastin = setTimeout(valmis, ms);
      window.addEventListener("online", () => { clearTimeout(ajastin); valmis(); }, { once: true });
    });
  }

  // Kesken olevien lähetysten määrä: taustapäivitykset (pollaus, nauha) odottavat,
  // etteivät ne korvaa animoitua nappia uudella (klikattavalla) kesken pyynnön.
  window.lahetyksiaKesken = 0;

  // POST JSON napin kautta. Palauttaa vastauksen datan; 4xx → Error(palvelimen syy).
  // Ei luovuta verkkovirheissä: yrittää kunnes onnistuu.
  window.lahetaNapilla = async function (nappi, url, runko) {
    const alkuteksti = nappi.textContent;
    nappi.disabled = true;
    nappi.classList.add("lahetys-kaynnissa");
    window.lahetyksiaKesken++;
    let vaihe = "Lähetetään";
    let ruutu = 0;
    let rulla = ODOTUSTEKSTI;
    const piirra = () => {
      if (vaihe === "yhteys") {
        rulla = rulla.slice(1) + rulla[0];
        nappi.textContent = rulla.slice(0, RULLAN_LEVEYS);
      } else {
        nappi.textContent = `${vaihe} ${PYORA[ruutu++ % PYORA.length]}`;
      }
    };
    piirra();
    const animaatio = setInterval(piirra, RUUDUN_KESTO_MS);
    try {
      for (let kerta = 0; ; kerta++) {
        vaihe = "Lähetetään";
        try {
          const { status, data } = await yritys(url, runko, () => { vaihe = "Odotetaan vastausta"; });
          if (status >= 200 && status < 300) return data;
          if (status < 500 && status !== 408 && status !== 429) {
            const syy = typeof data.detail === "string" ? data.detail : `HTTP ${status}`;
            throw Object.assign(new Error(syy), { lopullinen: true });
          }
        } catch (e) {
          if (e.lopullinen) throw e;
        }
        vaihe = "yhteys";
        await odotaYhteytta(Math.min(1000 * 2 ** kerta, VIIVE_MAX_MS));
      }
    } finally {
      window.lahetyksiaKesken--;
      clearInterval(animaatio);
      nappi.textContent = alkuteksti;
      nappi.disabled = false;
      nappi.classList.remove("lahetys-kaynnissa");
    }
  };
}
