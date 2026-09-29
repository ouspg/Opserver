"use strict";

// Reaaliaikainen läsnäolo (WebSocket): uutispalkki, muiden pallurat navissa ja
// yläpalkissa, leijuvat kursorit. Ladataan profiili.js:n jälkeen.

const uutiset = [];
const UUTINEN_MAX = 40;

function lisaaUutinen(teksti, aika) {
  uutiset.unshift({ teksti, aika });
  if (uutiset.length > UUTINEN_MAX) uutiset.length = UUTINEN_MAX;
  const palkki = document.getElementById("uutispalkki");
  if (!palkki) return;
  const item = document.createElement("span");
  item.className = "uutinen-item";
  item.innerHTML = `<span class="uutinen-aika">${escapeHtml(aika)}</span>${escapeHtml(teksti)}`;
  palkki.insertBefore(item, palkki.firstChild);
  palkki.scrollLeft = 0;
}

window.lahetaUutinen = (teksti) => lahetaWs({ tyyppi: "uutinen", teksti });
window.omaNimimerkki = () => omaProfiili?.nimimerkki || "Anonyymi";
window.piirraYmpyra = piirraYmpyra;

// Viesti WebSocketiin, jos yhteys on auki (muuten hiljaa pois: tila lähetetään uudelleen yhdistäessä).
function lahetaWs(viesti) {
  if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify(viesti));
}
window.lahetaWs = lahetaWs;

function sivuNavPolku(sivu) {
  if (!sivu) return null;
  if (sivu === "/" || sivu.startsWith("/korkeakoulut")) return "/korkeakoulut";
  if (sivu.startsWith("/kurssit")) return "/kurssit";
  if (sivu.startsWith("/tutkimukset")) return "/tutkimukset";
  return null;
}

const navindikaattorit = {};       // yläpalkki: käyttäjä-id → canvas
const tutkimusindikaattorit = {};   // tutkimuksen alavalikko: käyttäjä-id → canvas
const NAV_KOKO = 8;
const NAV_VALI = 2;

// Pallurat nav-nappien alle. napit = [[avain, nappi]], avainKayttajalle(k) → avain | null.
// rekisteri pitää canvasit, jotta pallura liukuu napilta toiselle eikä teleporttaa.
// Säiliö peittää koko valikon (CSS), ja jokainen pallura sijoitetaan oman nappinsa
// alareunaan — toimii myös kun valikko rivittyy (zoom, kapea ikkuna).
function piirraNavPallurat(sailyo, napit, avainKayttajalle, rekisteri) {
  const sailyoRect = sailyo.getBoundingClientRect();
  const nappiKeskukset = {};
  for (const [avain, nap] of napit) {
    const r = nap.getBoundingClientRect();
    nappiKeskukset[avain] = { x: r.left - sailyoRect.left + r.width / 2, y: r.bottom - sailyoRect.top + 1 };
  }

  // Ryhmittele käyttäjät nav-napin mukaan
  const perAvain = {};
  for (const k of muutKayttajat) {
    if (!k.profiili) continue;
    const avain = avainKayttajalle(k);
    if (!avain || nappiKeskukset[avain] === undefined) continue;
    (perAvain[avain] ||= []).push(k);
  }

  // Poista pallurat käyttäjiltä, jotka poistuivat tai eivät ole minkään napin kohdalla
  const sijoitetut = new Set(Object.values(perAvain).flat().map((k) => k.id));
  for (const id of Object.keys(rekisteri)) {
    if (!sijoitetut.has(id)) {
      rekisteri[id].remove();
      delete rekisteri[id];
    }
  }

  for (const [avain, kayttajat] of Object.entries(perAvain)) {
    const yhtLeveys = kayttajat.length * NAV_KOKO + Math.max(0, kayttajat.length - 1) * NAV_VALI;
    let x = nappiKeskukset[avain].x - yhtLeveys / 2;
    const y = nappiKeskukset[avain].y;

    for (const k of kayttajat) {
      let canvas = rekisteri[k.id];
      if (!canvas) {
        canvas = luoPallura(k, NAV_KOKO);
        canvas.style.cssText = `position:absolute;top:${y}px;left:${x}px;border-radius:50%;`;
        sailyo.appendChild(canvas);
        rekisteri[k.id] = canvas;
        // Lisää siirtymä vasta ensimmäisen piirron jälkeen (ei teleporttaa sisään)
        requestAnimationFrame(() => {
          canvas.style.transition = "left 0.5s cubic-bezier(0.34,1.56,0.64,1), top 0.5s cubic-bezier(0.34,1.56,0.64,1)";
        });
      } else {
        canvas.style.left = `${x}px`;
        canvas.style.top = `${y}px`;
      }
      piirraYmpyra(canvas, k.profiili, k.taso);
      canvas.title = k.nimimerkki || "?";
      x += NAV_KOKO + NAV_VALI;
    }
  }
}

// Tutkimuksen alavalikon napin avain käyttäjälle: saman tutkimuksen alasivu
// (tiedot/kurssit/arvioinnit/raportti), kurssisivulla tilasivu (kurssit-valittu/-odottaa/-hylatty)
// kun ne näkyvät alavalikossa. Muut tutkimukset näkyvät jo yläpalkin Tutkimukset-napilla.
function tutkimusNavAvain(k, slug, tilatNakyvissa) {
  const osat = (k.sivu || "").split("/").filter(Boolean);
  if (osat[0] !== "tutkimukset" || osat[1] !== slug) return null;
  const alasivu = osat[2] || "tiedot";
  if (alasivu.startsWith("kurssit")) return `alasivu:${tilatNakyvissa ? alasivu : "kurssit"}`;
  return `alasivu:${alasivu}`;
}

function paivitaNavIndikaattorit() {
  const sailyo = document.getElementById("nav-indikaattorit");
  const nav = document.getElementById("paanav");
  if (sailyo && nav) {
    piirraNavPallurat(sailyo, [...nav.querySelectorAll("button[data-polku]")].map((n) => [n.dataset.polku, n]),
                      (k) => sivuNavPolku(k.sivu), navindikaattorit);
  }

  const tnav = document.getElementById("tutkimus-nav");
  const tsailyo = document.getElementById("tutkimus-nav-indikaattorit");
  if (!tnav || !tsailyo) return;
  const osat = location.pathname.split("/").filter(Boolean);
  const slug = osat[0] === "tutkimukset" && !tnav.classList.contains("piilotettu") ? osat[1] : null;
  const tilatNakyvissa = !document.getElementById("tutkimus-nav-tila").classList.contains("piilotettu");
  const napit = [...tnav.querySelectorAll("button[data-tutkimus-alasivu]")]
    .map((n) => [`alasivu:${n.dataset.tutkimusAlasivu}`, n]);
  if (tilatNakyvissa) {
    napit.push(...[...tnav.querySelectorAll(".tila-nappi-nav")].map((n) => [`alasivu:${n.dataset.alasivu}`, n]));
  }
  piirraNavPallurat(tsailyo, slug ? napit : [], (k) => tutkimusNavAvain(k, slug, tilatNakyvissa),
                    tutkimusindikaattorit);
}

let ws = null;
let omaId = null;
let lahetysAjastin = null;
let viimeisinAktiivisuus = Date.now();
let hiiri = { x: 0.5, y: 0.5 };
let muutKayttajat = [];
let ympyraAvain = "", navAvain = "";

// Läsnäolotaso ajasta viimeisestä hiiren/näppäimistön käytöstä; yli 30 min = kummitus.
const AKTIIVISUUS_TASOT = [[60_000, "aktiivinen"], [10 * 60_000, "passiivinen"], [30 * 60_000, "nukkuva"]];
const LAHETYS_VALI_MS = 80;
const SYDANLYONTI_VALI_MS = 3_000;

function omaTaso() {
  const kulunut = Date.now() - viimeisinAktiivisuus;
  return AKTIIVISUUS_TASOT.find(([raja]) => kulunut < raja)?.[1] ?? "kummitus";
}

// Tason laskut kulkevat sydänlyönnin mukana; herääminen lähetetään heti.
function merkitseAktiiviseksi() {
  const heraa = omaTaso() !== "aktiivinen";
  viimeisinAktiivisuus = Date.now();
  if (heraa) lahetaTila();
}

function lahetaTila() {
  if (!omaProfiili) return;
  lahetaWs({
    nimimerkki: omaProfiili.nimimerkki,
    profiili: {
      taustavari: omaProfiili.taustavari,
      etualavari: omaProfiili.etualavari,
      bitmappi: omaProfiili.bitmappi,
    },
    sijainti: hiiri,
    taso: omaTaso(),
    sivu: location.pathname,
    nakyma: window.omaNakyma?.() ?? null,
    sivunumero: window.omaSivunumero?.() ?? null,  // valittujen kurssien sivutussivu
    lomake: window.omaLomake?.() ?? null,  // avoin korjauslomake (lomakesessio.js)
  });
}

window.lahetaTilaNyt = () => lahetaTila();

function yhdista() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  ws = new WebSocket(`${proto}//${location.host}/ws`);

  ws.addEventListener("message", (e) => {
    const viesti = JSON.parse(e.data);
    if (viesti.tyyppi === "oma-id") {
      omaId = viesti.id;
      window._omaId = omaId;
      lahetaTila();
      window.lomakeUudelleenliity?.();
    } else if (viesti.tyyppi === "uutinen") {
      lisaaUutinen(viesti.teksti, viesti.aika);
    } else if (viesti.tyyppi === "kayttajat") {
      muutKayttajat = viesti.data.filter((k) => k.id !== omaId);
      // Viesti tulee jokaisesta hiiren liikkeestä: ympyrät ja nav-pallurat (asettelun
      // luku) vain kun niihin vaikuttava tieto muuttuu. Sydänlyönti piirtää navin aina.
      const ymp = JSON.stringify(muutKayttajat.map((k) => [k.id, k.taso, k.nimimerkki, k.profiili]));
      if (ymp !== ympyraAvain) { ympyraAvain = ymp; paivitaMuutYmpyrat(); }
      const nav = JSON.stringify([ymp, muutKayttajat.map((k) => k.sivu)]);
      if (nav !== navAvain) { navAvain = nav; paivitaNavIndikaattorit(); }
      paivitaKursorit();
      window.paivitaNakymaPallurat?.(muutKayttajat);
      window.paivitaSivutusPallurat?.(muutKayttajat);
      window.paivitaLomakePallurat?.(muutKayttajat);
    } else if (viesti.tyyppi === "nakymat") {
      window.nakymatKuuntelija?.(viesti.data);
    } else if (viesti.tyyppi === "lomake-sessio" || viesti.tyyppi === "lomake-tallennettu") {
      window.lomakeKuuntelija?.(viesti);
    }
  });

  ws.addEventListener("close", () => setTimeout(yhdista, 3000));
  ws.addEventListener("error", () => ws.close());
}

function paivitaMuutYmpyrat() {
  const div = document.getElementById("muut-ympyrat");
  if (!div) return;
  while (div.firstChild) div.removeChild(div.firstChild);
  for (const k of muutKayttajat) {
    if (!k.profiili) continue;
    div.appendChild(luoPallura(k, 24, "vieras-ympyra-pieni"));
  }
}

const kursorielementit = {};
const KURSORI_REUNA = 30;  // px: pallura (28) + nuoli mahtuvat ruutuun

function paivitaKursorit() {
  const kerros = document.getElementById("kursori-kerros");
  if (!kerros) return;

  // Sama sivu ja suodatinnäkymä (välilehti); muut näkyvät välilehden pallurana.
  // Sama korjauslomake (tai ei lomaketta): pallura hiiren kohdalla. Muu lomakkeessa oleva,
  // kun itse ei ole lomakkeessa: pikkupallura avausnapin vieressä (lomakesessio.js) — ja
  // jos nappi on ruudun ulkopuolella, iso pallura reunassa nuoli napin suuntaan.
  const omaNakyma = window.omaNakyma?.() ?? null;
  const omaLomake = window.omaLomake?.() ?? null;
  const omaSivunumero = window.omaSivunumero?.() ?? null;
  const leveys = document.documentElement.clientWidth, korkeus = document.documentElement.clientHeight;
  const naytettavat = [];
  for (const k of muutKayttajat) {
    if (!k.profiili || k.sivu !== location.pathname || (k.nakyma ?? null) !== omaNakyma) continue;
    if ((k.sivunumero ?? null) !== omaSivunumero) continue;  // eri sivutussivulla → pallura sivunumerossa
    const lomake = k.lomake ?? null;
    let vx, vy;
    if (lomake === omaLomake && k.sijainti) {
      vx = k.sijainti.x - window.scrollX; vy = k.sijainti.y - window.scrollY;
    } else if (lomake && !omaLomake) {
      const nappi = document.querySelector(`[data-lomake="${CSS.escape(lomake)}"]`);
      if (!nappi) continue;  // ponytail: nappi ei renderöity (esim. eri sivutussivulla) → ei suuntaa
      const r = nappi.getBoundingClientRect();
      vx = r.left + r.width / 2; vy = r.top + r.height / 2;
    } else continue;
    // Ruudun ulkopuolella: pallura jää reunaan ja nuoli osoittaa todelliseen suuntaan.
    const x = Math.min(Math.max(vx, KURSORI_REUNA), leveys - KURSORI_REUNA);
    const y = Math.min(Math.max(vy, KURSORI_REUNA), korkeus - KURSORI_REUNA);
    const ulkona = x !== vx || y !== vy;
    if (lomake !== omaLomake && !ulkona) continue;  // nappi näkyvissä → riittää pikkupallura
    naytettavat.push({ k, x, y, ulkona, kulma: Math.atan2(vy - y, vx - x) });
  }

  const nytIdt = new Set(naytettavat.map((n) => n.k.id));
  for (const id of Object.keys(kursorielementit)) {
    if (!nytIdt.has(id)) {
      kerros.removeChild(kursorielementit[id]);
      delete kursorielementit[id];
    }
  }

  for (const { k, x, y, ulkona, kulma } of naytettavat) {
    let el = kursorielementit[k.id];
    if (!el) {
      el = document.createElement("div");
      el.className = "vieras-kursori";
      el.appendChild(luoPallura(k, 28));
      const nuoli = document.createElement("div");
      nuoli.className = "kursori-nuoli";
      el.appendChild(nuoli);
      kerros.appendChild(el);
      kursorielementit[k.id] = el;
    }

    piirraYmpyra(el.querySelector("canvas"), k.profiili, k.taso);
    el.title = k.nimimerkki || "?";
    el.classList.toggle("ulkona", ulkona);
    if (ulkona) el.style.setProperty("--kulma", `${kulma}rad`);
    el.style.left = `${x}px`;
    el.style.top = `${y}px`;
  }
}

// capture: myös taulukon oma (vaaka)vieritys, jotta lomakenappien suunta päivittyy.
document.addEventListener("scroll", () => paivitaKursorit(), { passive: true, capture: true });
window.addEventListener("resize", () => paivitaKursorit());

document.addEventListener("mousemove", (e) => {
  hiiri = { x: e.pageX, y: e.pageY };
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

setInterval(() => {
  lahetaTila(); paivitaKursorit(); paivitaNavIndikaattorit();
  window.paivitaLomakePallurat?.(muutKayttajat);  // taulukon uudelleenpiirto (pollaus) poistaa merkit
}, SYDANLYONTI_VALI_MS);

luoHeaderElementit();
omaProfiili = lataaProfiili() || arvoUusiProfiili();
tallennaProfiili();
document.getElementById("nimimerkki-kentta").value = omaProfiili.nimimerkki;
paivitaOmaYmpyra();
alustaHeaderTapahtumat();
merkitseAktiiviseksi();
yhdista();
