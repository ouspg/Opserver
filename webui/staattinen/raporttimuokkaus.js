"use strict";

// Kollaboratiivinen raporttiosion muokkain (modaali, kuten arviointimuokkaus)

let _rtid = null, _ravain = null;
let _rLahetysAjastin = null;
const RAPORTTI_LAHETYS_VALI_MS = 60;

function luoRaporttiModaali() {
  if (document.getElementById("raporttimuokkaus-modaali")) return;

  const modaali = document.createElement("div");
  modaali.id = "raporttimuokkaus-modaali";
  modaali.className = "modaali piilotettu";
  modaali.innerHTML = `
    <div class="modaali-sisalto arviointimuokkaus-sisalto">
      <button class="modaali-sulje" id="raporttimuokkaus-sulje">&#x2715;</button>
      <h2 id="raporttimuokkaus-otsikko"></h2>
      <div class="arviointimuokkaus-kommentti-alue">
        <div id="raporttimuokkaus-kursori-sailyo" style="position:relative;">
          <textarea id="raporttimuokkaus-tekstialue" rows="12"
            placeholder="Osion teksti..."></textarea>
          <canvas id="raporttimuokkaus-kursorit" style="
            position:absolute;top:0;left:0;pointer-events:none;"></canvas>
        </div>
        <div id="raporttimuokkaus-muokkaajat"></div>
      </div>
      <div class="modaali-napit">
        <button id="raporttimuokkaus-tallenna" class="nappi-toiminto">Tallenna</button>
        <button id="raporttimuokkaus-peruuta">Peruuta</button>
      </div>
    </div>`;
  document.body.appendChild(modaali);

  document.getElementById("raporttimuokkaus-sulje").addEventListener("click", suljeRaporttiMuokkaus);
  document.getElementById("raporttimuokkaus-peruuta").addEventListener("click", suljeRaporttiMuokkaus);
  document.getElementById("raporttimuokkaus-tallenna").addEventListener("click", tallenna);

  modaali.addEventListener("click", (e) => {
    if (e.target === modaali) suljeRaporttiMuokkaus();
  });

  const ta = document.getElementById("raporttimuokkaus-tekstialue");
  ta.addEventListener("input", () => lahetaTeksti(ta));
  ta.addEventListener("keyup", () => lahetaTeksti(ta));
  ta.addEventListener("click", () => lahetaTeksti(ta));
}

function lahetaTeksti(ta) {
  if (_rtid === null) return;
  clearTimeout(_rLahetysAjastin);
  _rLahetysAjastin = setTimeout(() => {
    window.lahetaRaporttiTeksti?.(_rtid, _ravain, ta.value, ta.selectionStart);
  }, RAPORTTI_LAHETYS_VALI_MS);
}

function tallenna() {
  const ta = document.getElementById("raporttimuokkaus-tekstialue");
  if (_rtid === null) return;
  const teksti = ta.value;
  window.tallennRaporttiOsio?.(_rtid, _ravain, teksti);

  // Päivitä osion teksti näkymässä heti
  const osioDiv = document.querySelector(`.raportti-osio[data-avain="${_ravain}"]`);
  if (osioDiv) {
    const tekstiDiv = osioDiv.querySelector(".raportti-osio-teksti");
    if (tekstiDiv) {
      tekstiDiv.innerHTML = teksti ? teksti.replace(/\n/g, "<br>") : '<em class="tulossa">Tämä osio puuttuu raportista.</em>';
    }
  }
  suljeRaporttiMuokkaus();
}

function suljeRaporttiMuokkaus() {
  if (_rtid !== null) {
    window.poistuRaporttiSessiosta?.(_rtid, _ravain);
  }
  _rtid = null; _ravain = null;
  const modaali = document.getElementById("raporttimuokkaus-modaali");
  if (modaali) modaali.classList.add("piilotettu");
}

function kursorinPikseli(ta, sijainti) {
  const tyyli = window.getComputedStyle(ta);
  const peili = document.createElement("div");
  peili.style.cssText = `
    position:absolute;top:-9999px;left:-9999px;visibility:hidden;
    white-space:pre-wrap;word-wrap:break-word;overflow:hidden;
    width:${ta.offsetWidth}px;
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
  const peiliRect = peili.getBoundingClientRect();
  const spanRect = span.getBoundingClientRect();
  document.body.removeChild(peili);
  return {
    x: spanRect.left - peiliRect.left,
    y: spanRect.top - peiliRect.top + ta.scrollTop,
  };
}

function piirraKursorit(muokkaajat) {
  const ta = document.getElementById("raporttimuokkaus-tekstialue");
  const canvas = document.getElementById("raporttimuokkaus-kursorit");
  if (!ta || !canvas) return;

  canvas.width = ta.offsetWidth;
  canvas.height = ta.offsetHeight;
  canvas.style.top = ta.offsetTop + "px";
  canvas.style.left = ta.offsetLeft + "px";

  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const omaId = window._omaId;
  for (const m of muokkaajat) {
    if (m.id === omaId || !m.profiili) continue;
    const pos = kursorinPikseli(ta, m.kursori || 0);
    ctx.strokeStyle = m.profiili.taustavari || "#c0392b";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(pos.x, pos.y);
    ctx.lineTo(pos.x, pos.y + 18);
    ctx.stroke();
    const offsc = document.createElement("canvas");
    offsc.width = 14; offsc.height = 14;
    window.piirraYmpyra?.(offsc, m.profiili);
    ctx.drawImage(offsc, pos.x - 7, pos.y - 14);
  }
}

function paivitaMuokkaajat(muokkaajat) {
  const div = document.getElementById("raporttimuokkaus-muokkaajat");
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

// Kuuntelija raportti-sessio-viesteille (kutsutaan yhteistyo.js:stä)
window.raporttisessioKuuntelija = function (viesti) {
  if (viesti.tid !== _rtid || viesti.avain !== _ravain) return;
  const ta = document.getElementById("raporttimuokkaus-tekstialue");
  if (!ta) return;
  if (ta.value !== viesti.teksti) {
    const kursori = ta.selectionStart;
    ta.value = viesti.teksti;
    ta.setSelectionRange(kursori, kursori);
  }
  piirraKursorit(viesti.muokkaajat || []);
  paivitaMuokkaajat(viesti.muokkaajat || []);
};

window.avaaRaporttiMuokkaus = function (tid, avain, otsikko, nykyinenTeksti) {
  luoRaporttiModaali();
  _rtid = tid; _ravain = avain;

  document.getElementById("raporttimuokkaus-otsikko").textContent = otsikko;
  document.getElementById("raporttimuokkaus-tekstialue").value = nykyinenTeksti || "";
  document.getElementById("raporttimuokkaus-muokkaajat").textContent = "";

  const modaali = document.getElementById("raporttimuokkaus-modaali");
  modaali.classList.remove("piilotettu");
  document.getElementById("raporttimuokkaus-tekstialue").focus();

  window.liityRaporttiSessioon?.(tid, avain);
};
