"use strict";

// Kollaboratiivinen arviointikommentti-muokkain

let _tid = null, _kid = null, _kysid = null;
let _lahetysAjastin = null;
const LAHETYS_VALI_MS = 60;

function luoMuokkausModaali() {
  if (document.getElementById("arviointimuokkaus-modaali")) return;

  const modaali = document.createElement("div");
  modaali.id = "arviointimuokkaus-modaali";
  modaali.className = "modaali piilotettu";
  modaali.innerHTML = `
    <div class="modaali-sisalto arviointimuokkaus-sisalto">
      <button class="modaali-sulje" id="arviointimuokkaus-sulje">&#x2715;</button>
      <h2 id="arviointimuokkaus-otsikko"></h2>
      <div id="arviointimuokkaus-ai-vastaus" class="arviointimuokkaus-ai"></div>
      <div class="arviointimuokkaus-kommentti-alue">
        <label class="arviointimuokkaus-label">Kommentti tekoälyn vastaukseen:</label>
        <div id="arviointimuokkaus-kursori-sailyo" style="position:relative;">
          <textarea id="arviointimuokkaus-tekstialue" rows="5"
            placeholder="Kirjoita kommentti tähän..."></textarea>
          <canvas id="arviointimuokkaus-kursorit" style="
            position:absolute;top:0;left:0;pointer-events:none;"></canvas>
        </div>
        <div id="arviointimuokkaus-muokkaajat"></div>
      </div>
      <div class="modaali-napit">
        <button id="arviointimuokkaus-tallenna" class="nappi-toiminto">Tallenna</button>
        <button id="arviointimuokkaus-peruuta">Peruuta</button>
      </div>
    </div>`;
  document.body.appendChild(modaali);

  document.getElementById("arviointimuokkaus-sulje").addEventListener("click", suljeArviointiMuokkaus);
  document.getElementById("arviointimuokkaus-peruuta").addEventListener("click", suljeArviointiMuokkaus);
  document.getElementById("arviointimuokkaus-tallenna").addEventListener("click", tallenna);

  modaali.addEventListener("click", (e) => {
    if (e.target === modaali) suljeArviointiMuokkaus();
  });

  const ta = document.getElementById("arviointimuokkaus-tekstialue");
  ta.addEventListener("input", () => lahetaTeksti(ta));
  ta.addEventListener("keyup", () => lahetaTeksti(ta));
  ta.addEventListener("click", () => lahetaTeksti(ta));
}

function lahetaTeksti(ta) {
  if (!_tid) return;
  clearTimeout(_lahetysAjastin);
  _lahetysAjastin = setTimeout(() => {
    window.lahetaMuokkausTeksti?.(_tid, _kid, _kysid, ta.value, ta.selectionStart);
  }, LAHETYS_VALI_MS);
}

function tallenna() {
  const ta = document.getElementById("arviointimuokkaus-tekstialue");
  if (!_tid) return;
  window.tallennaMuokkausKommentti?.(_tid, _kid, _kysid, ta.value);
  suljeArviointiMuokkaus();
}

function suljeArviointiMuokkaus() {
  if (_tid !== null) {
    window.poistuMuokkausSessiosta?.(_tid, _kid, _kysid);
  }
  _tid = null; _kid = null; _kysid = null;
  const modaali = document.getElementById("arviointimuokkaus-modaali");
  if (modaali) modaali.classList.add("piilotettu");
}

function kursorinPikseli(ta, sijainti) {
  // Luo peiliElementti textarea:n tekstitilanteen laskemiseksi
  const tyyli = window.getComputedStyle(ta);
  const peili = document.createElement("div");
  peili.style.cssText = `
    position:absolute;visibility:hidden;white-space:pre-wrap;word-wrap:break-word;
    width:${ta.clientWidth}px;
    font:${tyyli.font};
    padding:${tyyli.padding};
    border:${tyyli.border};
    box-sizing:${tyyli.boxSizing};
    line-height:${tyyli.lineHeight};
  `;
  const teksti = ta.value.slice(0, sijainti);
  peili.textContent = teksti;
  const span = document.createElement("span");
  span.textContent = "|";
  peili.appendChild(span);
  document.body.appendChild(peili);
  const rect = span.getBoundingClientRect();
  const taRect = ta.getBoundingClientRect();
  document.body.removeChild(peili);
  return {
    x: rect.left - taRect.left + ta.scrollLeft,
    y: rect.top - taRect.top + ta.scrollTop,
  };
}

function piirraKursorit(muokkaajat) {
  const ta = document.getElementById("arviointimuokkaus-tekstialue");
  const canvas = document.getElementById("arviointimuokkaus-kursorit");
  if (!ta || !canvas) return;

  canvas.width = ta.offsetWidth;
  canvas.height = ta.offsetHeight;

  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const omaId = window._omaId;
  for (const m of muokkaajat) {
    if (m.id === omaId || !m.profiili) continue;
    const pos = kursorinPikseli(ta, m.kursori || 0);
    // Piirrä värillinen viiva kursorin kohtaan
    ctx.strokeStyle = m.profiili.taustavari || "#c0392b";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(pos.x, pos.y);
    ctx.lineTo(pos.x, pos.y + 18);
    ctx.stroke();
    // Pieniympyra kursori-viivan yläpuolella
    const offsc = document.createElement("canvas");
    offsc.width = 14; offsc.height = 14;
    window.piirraYmpyra?.(offsc, m.profiili);
    ctx.drawImage(offsc, pos.x - 7, pos.y - 14);
  }
}

function paivitaMuokkaajat(muokkaajat) {
  const div = document.getElementById("arviointimuokkaus-muokkaajat");
  if (!div) return;
  const omaId = window._omaId;
  const muut = muokkaajat.filter((m) => m.id !== omaId);
  if (muut.length === 0) {
    div.textContent = "";
    return;
  }
  div.innerHTML = "Muokkaa nyt myös: " + muut.map((m) => {
    const offsc = document.createElement("canvas");
    offsc.width = 14; offsc.height = 14;
    offsc.className = "vieras-ympyra-pieni";
    window.piirraYmpyra?.(offsc, m.profiili);
    return `<span class="muokkaaja-rivi">${offsc.outerHTML} ${m.nimimerkki || "?"}</span>`;
  }).join(", ");
}

// Kuuntelija muokkaussessio-viesteille (kutsutaan yhteistyo.js:stä)
window.muokkausKuuntelija = function (viesti) {
  if (viesti.tid !== _tid || viesti.kid !== _kid || viesti.kysid !== _kysid) return;
  const ta = document.getElementById("arviointimuokkaus-tekstialue");
  if (!ta) return;
  // Päivitä teksti vain jos muuttui (muuten kursori hyppää)
  if (ta.value !== viesti.teksti) {
    const kursori = ta.selectionStart;
    ta.value = viesti.teksti;
    ta.setSelectionRange(kursori, kursori);
  }
  piirraKursorit(viesti.muokkaajat || []);
  paivitaMuokkaajat(viesti.muokkaajat || []);
};

window.avaaArviointiMuokkaus = function (tid, kid, kysid, kysymys, aiVastaus, nykyinenKommentti) {
  luoMuokkausModaali();
  _tid = tid; _kid = kid; _kysid = kysid;

  document.getElementById("arviointimuokkaus-otsikko").textContent = kysymys;
  document.getElementById("arviointimuokkaus-ai-vastaus").innerHTML =
    `<strong>Tekoälyn vastaus:</strong><br>${aiVastaus || "<em>Ei vastausta</em>"}`;
  document.getElementById("arviointimuokkaus-tekstialue").value = nykyinenKommentti || "";
  document.getElementById("arviointimuokkaus-muokkaajat").textContent = "";

  const modaali = document.getElementById("arviointimuokkaus-modaali");
  modaali.classList.remove("piilotettu");
  document.getElementById("arviointimuokkaus-tekstialue").focus();

  window.liityMuokkausSessioon?.(tid, kid, kysid);
};
