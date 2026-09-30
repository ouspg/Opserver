"use strict";

// Lohko rajaa funktiot tiedoston sisään (vain window.* näkyy ulos). Ilman sitä
// arviointimuokkaus.js:n samannimiset globaalit (tallenna, …) ylikirjoittavat
// nämä, ja esim. "Tallenna"-nappi kutsuu väärän tiedoston funktiota.
{

// Raporttiosion yhteismuokkain. Jaettu lomake (lomakesessio.js) kuten HITL-modaalit:
// saman osion avanneet näkevät saman tekstin, toistensa pallurat ja tekstikursorit,
// ja Muokkaa-napin vieressä näkyy kuka osiota muokkaa (data-lomake).

let _slug = null, _avain = null;

function luoRaporttiModaali() {
  if (document.getElementById("raporttimuokkaus-modaali")) return;

  const modaali = document.createElement("div");
  modaali.id = "raporttimuokkaus-modaali";
  modaali.className = "modaali piilotettu";
  modaali.innerHTML = `
    <div class="modaali-sisalto arviointimuokkaus-sisalto">
      <button class="modaali-sulje">&#x2715;</button>
      <h2 id="raporttimuokkaus-otsikko"></h2>
      <div class="arviointimuokkaus-kommentti-alue">
        <textarea id="raporttimuokkaus-tekstialue" rows="12" data-jaettu="teksti"></textarea>
      </div>
      <div class="modaali-napit">
        <button id="raporttimuokkaus-tallenna" class="nappi-toiminto">Tallenna</button>
        <button id="raporttimuokkaus-peruuta">Peruuta</button>
      </div>
    </div>`;
  document.body.appendChild(modaali);

  kytkeSulkeminen(modaali, suljeRaporttiMuokkaus);
  document.getElementById("raporttimuokkaus-peruuta").addEventListener("click", suljeRaporttiMuokkaus);
  document.getElementById("raporttimuokkaus-tallenna").addEventListener("click", tallenna);
}

// Osion teksti näkymään heti (tallentaja ja muut saman lomakkeen muokkaajat).
function paivitaOsio(avain, teksti) {
  const el = document.querySelector(`.raportti-osio[data-avain="${CSS.escape(avain)}"] .raportti-osio-teksti`);
  if (el) el.innerHTML = raporttiOsioHtml(teksti);
}

async function tallenna() {
  if (_avain === null) return;
  const nappi = document.getElementById("raporttimuokkaus-tallenna");
  const teksti = document.getElementById("raporttimuokkaus-tekstialue").value;
  const avain = _avain;
  try {
    await lahetaNapilla(nappi, `/api/tutkimukset/${_slug}/raportti/${avain}`, { teksti });
  } catch (e) {
    nappi.textContent = `Virhe: ${e.message}`;
    return;
  }
  window.lomakeTallennettu?.();
  paivitaOsio(avain, teksti);
  suljeRaporttiMuokkaus();
}

function suljeRaporttiMuokkaus() {
  window.suljeLomakesessio?.();
  _avain = null;
  document.getElementById("raporttimuokkaus-modaali")?.classList.add("piilotettu");
}

window.avaaRaporttiMuokkaus = async function (tid, slug, avain, otsikko) {
  luoRaporttiModaali();
  _slug = slug; _avain = avain;
  const modaali = document.getElementById("raporttimuokkaus-modaali");
  const ta = document.getElementById("raporttimuokkaus-tekstialue");
  document.getElementById("raporttimuokkaus-otsikko").textContent = otsikko;
  Object.assign(ta, { value: "", disabled: true, placeholder: "Ladataan osion tekstiä…" });
  modaali.classList.remove("piilotettu");

  // Tuore teksti kannasta: sivun kopio voi olla pollausvälin (15 s) vanha, ja
  // ensimmäisen avaajan arvo alustaa jaetun lomakkeen kaikille liittyjille.
  let osiot;
  try {
    ({ osiot } = await haeJson(`/api/tutkimukset/${slug}/raportti`));
  } catch (_) {
    ta.placeholder = "Tekstin lataus epäonnistui — sulje ja yritä uudelleen.";
    return;
  }
  if (_avain !== avain) return;  // suljettiin latauksen aikana
  Object.assign(ta, { value: osiot[avain] || "", disabled: false, placeholder: "Osion teksti..." });
  ta.focus();
  window.avaaLomakesessio?.(`raportti:${tid}:${avain}`, modaali, {
    kuvaus: `Muokkaa raporttia tutkimuksessa "${lyhenna(tutkimusNimi())}"`,
    // Joku muu tallensi: hänen tekstinsä näkymään heti ja oma modaali kiinni.
    tallennettu: (viesti) => {
      paivitaOsio(avain, viesti.arvot?.teksti ?? ta.value);
      suljeRaporttiMuokkaus();
    },
  });
};
}
