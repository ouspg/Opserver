"use strict";

// --- Vakiot ---

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

// --- Evästeet ---

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

// --- Profiili ---

let omaProfiili = null;

function lataaProfiili() {
  const raw = lueEvaste("kyberesrKayttaja");
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
  asetaEvaste("kyberesrKayttaja", encodeURIComponent(JSON.stringify(omaProfiili)));
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

// --- Canvas-piirto ---

function piirraYmpyra(canvas, profiili, epaaktiivinen = false) {
  const ctx = canvas.getContext("2d");
  const w = canvas.width, h = canvas.height;
  const cx = w / 2, cy = h / 2;
  const r = Math.min(w, h) / 2 - 0.5;

  ctx.clearRect(0, 0, w, h);
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

  if (epaaktiivinen) {
    const fs = Math.max(6, Math.round(r * 0.38));
    ctx.font = `bold ${fs}px monospace`;
    ctx.textAlign = "right";
    ctx.textBaseline = "top";
    ctx.fillStyle = profiili.etualavari || "#eee";
    ctx.fillText("zZ", w - 1, 0);
  }
}

// --- Header-elementit ---

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
  h1.insertAdjacentElement("afterend", alue);

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

// --- Profiilimuokkaus ---

function rakennaTaustaVarit() {
  const div = document.getElementById("tausta-varit");
  div.innerHTML = "";
  for (const vari of TAUSTAVRIT) {
    const nap = document.createElement("button");
    nap.className = "vari-nappula" + (vari === omaProfiili.taustavari ? " valittu" : "");
    nap.style.background = vari;
    nap.title = vari;
    nap.addEventListener("click", (e) => {
      e.stopPropagation();
      omaProfiili.taustavari = vari;
      tallennaProfiili();
      paivitaOmaYmpyra();
      rakennaTaustaVarit();
      piirraYmpyra(document.getElementById("profiili-esikatselu"), omaProfiili);
      lahetaTila();
    });
    div.appendChild(nap);
  }
}

function rakennaEtualaVarit() {
  const div = document.getElementById("etuala-varit");
  div.innerHTML = "";
  for (const vari of ETUALVRIT) {
    const nap = document.createElement("button");
    nap.className = "vari-nappula" + (vari === omaProfiili.etualavari ? " valittu" : "");
    nap.style.background = vari;
    nap.title = vari;
    nap.addEventListener("click", (e) => {
      e.stopPropagation();
      omaProfiili.etualavari = vari;
      tallennaProfiili();
      paivitaOmaYmpyra();
      rakennaEtualaVarit();
      piirraYmpyra(document.getElementById("profiili-esikatselu"), omaProfiili);
      lahetaTila();
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
  rakennaTaustaVarit();
  rakennaEtualaVarit();
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
    tallennaProfiili();
    paivitaOmaYmpyra();
    piirraYmpyra(document.getElementById("profiili-esikatselu"), omaProfiili);
    lahetaTila();
  });

  document.getElementById("sulje-muokkaus").addEventListener("click", suljeProfiiliMuokkaus);

  document.addEventListener("click", (e) => {
    const muokkaus = document.getElementById("profiili-muokkaus");
    if (!muokkaus.classList.contains("piilotettu") && !muokkaus.contains(e.target)) {
      suljeProfiiliMuokkaus();
    }
  });
}

// --- WebSocket ---

let ws = null;
let omaId = null;
let lahetysAjastin = null;
let aktiivisuusAjastin = null;
let oliAktiivinen = true;
let hiiri = { x: 0.5, y: 0.5 };
let muutKayttajat = [];

const AKTIIVISUUS_TIMEOUT_MS = 30_000;
const LAHETYS_VALI_MS = 80;
const SYDANLYONTI_VALI_MS = 3_000;

function merkitseAktiiviseksi() {
  oliAktiivinen = true;
  clearTimeout(aktiivisuusAjastin);
  aktiivisuusAjastin = setTimeout(() => {
    oliAktiivinen = false;
    lahetaTila();
    paivitaMuutYmpyrat();
  }, AKTIIVISUUS_TIMEOUT_MS);
}

function lahetaTila() {
  if (!ws || ws.readyState !== WebSocket.OPEN || !omaProfiili) return;
  ws.send(JSON.stringify({
    nimimerkki: omaProfiili.nimimerkki,
    profiili: {
      taustavari: omaProfiili.taustavari,
      etualavari: omaProfiili.etualavari,
      bitmappi: omaProfiili.bitmappi,
    },
    sijainti: hiiri,
    aktiivinen: oliAktiivinen,
    sivu: location.pathname,
  }));
}

function yhdista() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  ws = new WebSocket(`${proto}//${location.host}/ws`);

  ws.addEventListener("message", (e) => {
    const viesti = JSON.parse(e.data);
    if (viesti.tyyppi === "oma-id") {
      omaId = viesti.id;
      lahetaTila();
    } else if (viesti.tyyppi === "kayttajat") {
      muutKayttajat = viesti.data.filter((k) => k.id !== omaId);
      paivitaMuutYmpyrat();
      paivitaKursorit();
    }
  });

  ws.addEventListener("close", () => setTimeout(yhdista, 3000));
  ws.addEventListener("error", () => ws.close());
}

// --- Muiden ympyrät headerissa ---

function paivitaMuutYmpyrat() {
  const div = document.getElementById("muut-ympyrat");
  if (!div) return;
  while (div.firstChild) div.removeChild(div.firstChild);
  for (const k of muutKayttajat) {
    if (!k.profiili) continue;
    const canvas = document.createElement("canvas");
    canvas.width = 24;
    canvas.height = 24;
    canvas.className = "vieras-ympyra-pieni";
    canvas.title = k.nimimerkki || "?";
    piirraYmpyra(canvas, k.profiili, !k.aktiivinen);
    div.appendChild(canvas);
  }
}

// --- Leijuvat kursorit ---

const kursorielementit = {};

function paivitaKursorit() {
  const kerros = document.getElementById("kursori-kerros");
  if (!kerros) return;

  const nytIdt = new Set(muutKayttajat.map((k) => k.id));
  for (const id of Object.keys(kursorielementit)) {
    if (!nytIdt.has(id)) {
      kerros.removeChild(kursorielementit[id]);
      delete kursorielementit[id];
    }
  }

  for (const k of muutKayttajat) {
    if (!k.profiili || !k.sijainti) continue;

    let el = kursorielementit[k.id];
    if (!el) {
      el = document.createElement("div");
      el.className = "vieras-kursori";
      const canvas = document.createElement("canvas");
      canvas.width = 28;
      canvas.height = 28;
      el.appendChild(canvas);
      kerros.appendChild(el);
      kursorielementit[k.id] = el;
    }

    piirraYmpyra(el.querySelector("canvas"), k.profiili, !k.aktiivinen);
    el.title = k.nimimerkki || "?";
    el.style.left = `${k.sijainti.x * window.innerWidth}px`;
    el.style.top = `${k.sijainti.y * window.innerHeight}px`;
  }
}

// --- Syötetapahtumat ---

document.addEventListener("mousemove", (e) => {
  hiiri = { x: e.clientX / window.innerWidth, y: e.clientY / window.innerHeight };
  merkitseAktiiviseksi();
  if (!lahetysAjastin) {
    lahetysAjastin = setTimeout(() => {
      lahetysAjastin = null;
      lahetaTila();
    }, LAHETYS_VALI_MS);
  }
});

document.addEventListener("keydown", merkitseAktiiviseksi);
document.addEventListener("click", merkitseAktiiviseksi);

setInterval(() => { lahetaTila(); paivitaKursorit(); }, SYDANLYONTI_VALI_MS);

// --- Käynnistys ---

luoHeaderElementit();
omaProfiili = lataaProfiili() || arvoUusiProfiili();
tallennaProfiili();
document.getElementById("nimimerkki-kentta").value = omaProfiili.nimimerkki;
paivitaOmaYmpyra();
alustaHeaderTapahtumat();
merkitseAktiiviseksi();
yhdista();
