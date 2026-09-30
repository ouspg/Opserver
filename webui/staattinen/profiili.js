"use strict";

// Oma profiili (nimimerkki, värit, 8×8-symboli evästeessä), ympyröiden/pallurien
// piirto ja yläpalkin profiilimuokkain.

const ELAIMET = [
  "Karhu", "Susi", "Hirvi", "Kettu", "Jänis", "Orava", "Siili", "Majava",
  "Ilves", "Peura", "Saukko", "Ahma", "Lumikko", "Näätä", "Mäyrä",
  "Lahna", "Ahven", "Hauki", "Kuha", "Lohi", "Taimen", "Siika", "Muikku",
  "Haahka", "Kurki", "Joutsen", "Kotka", "Haukka", "Pöllö", "Tikka",
  "Varis", "Peippo", "Tiainen", "Naakka", "Käki", "Satakieli", "Korppi",
];

// 8×8 Space Invaders -bitmappit (rivi = tavu, bitti 7 = vasen piksel)
const SPRITET = [
  [0x18, 0x3C, 0x7E, 0xDB, 0xFF, 0x5A, 0x81, 0x42],
  [0x81, 0x42, 0xFF, 0xDB, 0xFF, 0x66, 0x42, 0x81],
  [0x3C, 0x66, 0xFF, 0xDB, 0xFF, 0xBD, 0x81, 0x24],
  [0x3C, 0xFF, 0xDB, 0xFF, 0x66, 0x24, 0x00, 0x00],
  [0x81, 0xC3, 0xE7, 0xFF, 0xDB, 0xE7, 0xC3, 0x81],
  [0x7E, 0xDB, 0xFF, 0xFF, 0xFF, 0xAA, 0xAA, 0x00],
  [0x00, 0x66, 0xFF, 0xFF, 0x7E, 0x3C, 0x18, 0x00],
  [0x42, 0x3C, 0xDB, 0x7E, 0x7E, 0xDB, 0x3C, 0x42],
  [0x18, 0x7E, 0xFF, 0xFF, 0x7E, 0x18, 0x00, 0x00],
  [0x7E, 0x81, 0xA5, 0x81, 0xFF, 0x66, 0x24, 0x24],
  [0x18, 0x3C, 0x66, 0xFF, 0x7E, 0x3C, 0x18, 0x00],
  [0x24, 0x99, 0xFF, 0x66, 0xFF, 0x5A, 0x81, 0x42],
];

const TAUSTAVRIT = [
  "#c0392b", "#8e44ad", "#2980b9", "#16a085", "#27ae60",
  "#d35400", "#2c3e50", "#1a1a6e", "#7f1734", "#0d5473",
  "#5c3317", "#1e6b3a",
];

const ETUALVRIT = [
  "#ffffff", "#f1c40f", "#ecf0f1", "#ffeaa7", "#a29bfe",
  "#fd79a8", "#74b9ff", "#55efc4", "#fdcb6e", "#e17055",
];

function lueEvaste(nimi) {
  const raw = `; ${document.cookie}`;
  const osat = raw.split(`; ${nimi}=`);
  if (osat.length === 2) return osat.pop().split(";").shift();
  return null;
}

function asetaEvaste(nimi, arvo, paivat = 30) {
  const vanhentuu = new Date();
  vanhentuu.setTime(vanhentuu.getTime() + paivat * 86400000);
  document.cookie = `${nimi}=${arvo};expires=${vanhentuu.toUTCString()};path=/;SameSite=Strict`;
}

let omaProfiili = null;

function lataaProfiili() {
  const raw = lueEvaste("opserverKayttaja");
  if (raw) {
    try {
      const p = JSON.parse(decodeURIComponent(raw));
      if (p?.nimimerkki && p?.taustavari && p?.etualavari &&
          Array.isArray(p?.bitmappi) && p.bitmappi.length === 8) {
        return p;
      }
    } catch {}
  }
  return null;
}

function tallennaProfiili() {
  asetaEvaste("opserverKayttaja", encodeURIComponent(JSON.stringify(omaProfiili)));
}

function arvoNimimerkki() {
  const elain = ELAIMET[Math.floor(Math.random() * ELAIMET.length)];
  const nro = Math.floor(Math.random() * 1000);
  return `Anonyymi_${elain}_${nro}`;
}

function arvoUusiProfiili() {
  return {
    nimimerkki: arvoNimimerkki(),
    taustavari: TAUSTAVRIT[Math.floor(Math.random() * TAUSTAVRIT.length)],
    etualavari: ETUALVRIT[Math.floor(Math.random() * ETUALVRIT.length)],
    bitmappi: SPRITET[Math.floor(Math.random() * SPRITET.length)].slice(),
  };
}

// taso (läsnäolo): aktiivinen = värillinen, passiivinen = harmaa, nukkuva = harmaa + zZz,
// kummitus = läpinäkyvä harmaa + zZz.
function piirraYmpyra(canvas, profiili, taso = "aktiivinen") {
  const ctx = canvas.getContext("2d");
  const w = canvas.width, h = canvas.height;
  const cx = w / 2, cy = h / 2;
  const r = Math.min(w, h) / 2 - 0.5;
  const epaaktiivinen = taso !== "aktiivinen";

  ctx.clearRect(0, 0, w, h);
  ctx.globalAlpha = taso === "kummitus" ? 0.35 : 1;
  ctx.save();
  ctx.beginPath();
  ctx.arc(cx, cy, r, 0, Math.PI * 2);
  ctx.clip();

  ctx.fillStyle = epaaktiivinen ? "#777" : profiili.taustavari;
  ctx.fillRect(0, 0, w, h);

  const koko = (r * 2 - 4) / 8;
  const x0 = cx - r + 2;
  const y0 = cy - r + 2;
  ctx.fillStyle = epaaktiivinen ? "#bbb" : profiili.etualavari;

  for (let rivi = 0; rivi < 8; rivi++) {
    const tavu = profiili.bitmappi[rivi] || 0;
    for (let sarake = 0; sarake < 8; sarake++) {
      if (tavu & (0x80 >> sarake)) {
        ctx.fillRect(x0 + sarake * koko, y0 + rivi * koko, koko, koko);
      }
    }
  }
  ctx.restore();

  if (taso === "nukkuva" || taso === "kummitus") {
    // zzZ portaana oikeaan yläkulmaan: kirjaimet kasvavat ylös oikealle.
    ctx.textAlign = "right";
    ctx.textBaseline = "top";
    ctx.strokeStyle = "#222";
    ctx.fillStyle = "#fff";
    [["z", 0.4, 0.95, 0.6], ["z", 0.5, 0.5, 0.3], ["Z", 0.65, 0, -0.05]].forEach(([k, koko, dx, dy]) => {
      const fs = Math.max(4, Math.round(r * koko * 1.4));
      ctx.font = `bold ${fs}px sans-serif`;
      ctx.lineWidth = Math.max(1, fs / 4);
      ctx.strokeText(k, w - 1 - dx * r, dy * r);
      ctx.fillText(k, w - 1 - dx * r, dy * r);
    });
  }
}

// Käyttäjän pallura (canvas) annetussa koossa; title = nimimerkki.
function luoPallura(k, koko, luokka = "") {
  const c = document.createElement("canvas");
  c.width = c.height = koko;
  c.className = luokka;
  // Tooltip (nimimerkki) data-tooltipista, ei titlestä: pallura-kerrokset ovat
  // pointer-events: none (kytkeTooltipit).
  c.dataset.tooltip = k.nimimerkki || "?";
  c.setAttribute("role", "img");
  c.setAttribute("aria-label", c.dataset.tooltip);
  piirraYmpyra(c, k.profiili, k.taso);
  return c;
}
window.luoPallura = luoPallura;
// Muun käyttäjän pikkupallura napin sisään (välilehti, sivutuksen sivunumero).
window.luoPikkupallura = (k) => luoPallura(k, 10, "nakyma-pallura");

function luoHeaderElementit() {
  const h1 = document.querySelector("header h1");

  const alue = document.createElement("div");
  alue.id = "yhteistyo-alue";
  alue.innerHTML = `
    <div id="muut-ympyrat"></div>
    <div id="oma-alue">
      <canvas id="oma-ympyra" width="32" height="32" title="Muokkaa profiilia"></canvas>
      <span class="nimimerkki-ohje">Nimimerkkisi:</span>
      <input type="text" id="nimimerkki-kentta" autocomplete="off" spellcheck="false" maxlength="40">
      <button id="nollaa-nimimerkki" title="Arvo uusi nimimerkki">↺ Nollaa</button>
    </div>`;
  document.querySelector("header").appendChild(alue);

  const uutispalkki = document.createElement("div");
  uutispalkki.id = "uutispalkki";
  const paanav = document.getElementById("paanav");
  paanav.parentNode.insertBefore(uutispalkki, paanav);

  const tooltip = document.createElement("div");
  tooltip.id = "nimis-tooltip";
  tooltip.className = "piilotettu";
  document.body.appendChild(tooltip);

  const indikaattorit = document.createElement("div");
  indikaattorit.id = "nav-indikaattorit";
  document.getElementById("paanav").appendChild(indikaattorit);

  const tutkimusIndikaattorit = document.createElement("div");
  tutkimusIndikaattorit.id = "tutkimus-nav-indikaattorit";
  document.getElementById("tutkimus-nav").appendChild(tutkimusIndikaattorit);

  const muokkaus = document.createElement("div");
  muokkaus.id = "profiili-muokkaus";
  muokkaus.className = "piilotettu";
  muokkaus.innerHTML = `
    <div class="profiili-esikatselu-rivi">
      <canvas id="profiili-esikatselu" width="48" height="48"></canvas>
    </div>
    <div class="vari-otsikko">Taustaväri</div>
    <div id="tausta-varit" class="vari-ruudukko"></div>
    <div class="vari-otsikko">Etualaväri</div>
    <div id="etuala-varit" class="vari-ruudukko"></div>
    <div class="profiili-napit">
      <button id="arvo-uusi-symboli">↺ Uusi symboli</button>
      <button id="sulje-muokkaus">✕ Sulje</button>
    </div>`;
  document.body.appendChild(muokkaus);

  const kerros = document.createElement("div");
  kerros.id = "kursori-kerros";
  document.body.appendChild(kerros);
}

// Oma profiili muuttui: tallenna, piirrä omat ympyrät ja kerro muille.
function profiiliMuuttui() {
  tallennaProfiili();
  paivitaOmaYmpyra();
  piirraYmpyra(document.getElementById("profiili-esikatselu"), omaProfiili);
  lahetaTila();
}

// Väripaletti (tausta/etuala): valittu korostettuna, klikkaus vaihtaa profiilin värin.
function rakennaVarit(divId, varit, kentta) {
  const div = document.getElementById(divId);
  div.innerHTML = "";
  for (const vari of varit) {
    const nap = document.createElement("button");
    nap.className = "vari-nappula" + (vari === omaProfiili[kentta] ? " valittu" : "");
    nap.style.background = vari;
    nap.title = vari;
    nap.addEventListener("click", (e) => {
      e.stopPropagation();
      omaProfiili[kentta] = vari;
      profiiliMuuttui();
      rakennaVarit(divId, varit, kentta);
    });
    div.appendChild(nap);
  }
}

function avaaProfiiliMuokkaus() {
  const muokkaus = document.getElementById("profiili-muokkaus");
  const ympyra = document.getElementById("oma-ympyra");
  const rect = ympyra.getBoundingClientRect();
  let vasen = rect.left;
  if (vasen + 230 > window.innerWidth) vasen = window.innerWidth - 238;
  muokkaus.style.top = (rect.bottom + 6) + "px";
  muokkaus.style.left = vasen + "px";
  muokkaus.classList.remove("piilotettu");
  piirraYmpyra(document.getElementById("profiili-esikatselu"), omaProfiili);
  rakennaVarit("tausta-varit", TAUSTAVRIT, "taustavari");
  rakennaVarit("etuala-varit", ETUALVRIT, "etualavari");
}

function suljeProfiiliMuokkaus() {
  document.getElementById("profiili-muokkaus").classList.add("piilotettu");
}

function paivitaOmaYmpyra() {
  piirraYmpyra(document.getElementById("oma-ympyra"), omaProfiili);
}

function alustaHeaderTapahtumat() {
  document.getElementById("oma-ympyra").addEventListener("click", (e) => {
    e.stopPropagation();
    const muokkaus = document.getElementById("profiili-muokkaus");
    if (muokkaus.classList.contains("piilotettu")) {
      avaaProfiiliMuokkaus();
    } else {
      suljeProfiiliMuokkaus();
    }
  });

  document.getElementById("nimimerkki-kentta").addEventListener("input", (e) => {
    omaProfiili.nimimerkki = e.target.value;
    tallennaProfiili();
    lahetaTila();
  });

  document.getElementById("nollaa-nimimerkki").addEventListener("click", () => {
    const uusi = arvoNimimerkki();
    omaProfiili.nimimerkki = uusi;
    document.getElementById("nimimerkki-kentta").value = uusi;
    tallennaProfiili();
    lahetaTila();
  });

  document.getElementById("arvo-uusi-symboli").addEventListener("click", (e) => {
    e.stopPropagation();
    omaProfiili.bitmappi = SPRITET[Math.floor(Math.random() * SPRITET.length)].slice();
    profiiliMuuttui();
  });

  document.getElementById("sulje-muokkaus").addEventListener("click", suljeProfiiliMuokkaus);

  document.addEventListener("click", (e) => {
    const muokkaus = document.getElementById("profiili-muokkaus");
    if (!muokkaus.classList.contains("piilotettu") && !muokkaus.contains(e.target)) {
      suljeProfiiliMuokkaus();
    }
  });

  kytkeTooltipit();
}

// Kaikkien pallurojen tooltip (canvas[data-tooltip]: yläpalkki, leijuvat kursorit, nav,
// välilehdet, sivutus, lomakkeet). Osuma lasketaan geometriasta, koska kursori- ja
// nav-kerrokset ovat pointer-events: none — pallurat eivät saa estää alla olevan napin
// klikkausta. Modaalin ollessa auki vain modaalin omat pallurat ja leijuvat kursorit.
function kytkeTooltipit() {
  const tt = document.getElementById("nimis-tooltip");
  document.addEventListener("mousemove", (e) => {
    const modaali = document.querySelector(".modaali:not(.piilotettu)");
    const osuma = [...document.querySelectorAll("canvas[data-tooltip]")].find((c) => {
      if (modaali && !modaali.contains(c) && !c.closest("#kursori-kerros")) return false;
      const r = c.getBoundingClientRect();
      return r.width > 0 && e.clientX >= r.left && e.clientX <= r.right && e.clientY >= r.top && e.clientY <= r.bottom;
    });
    tt.classList.toggle("piilotettu", !osuma);
    if (!osuma) return;
    tt.textContent = osuma.dataset.tooltip;
    tt.style.left = (e.clientX + 10) + "px";
    tt.style.top = (e.clientY - 30) + "px";
  }, { passive: true });
}
