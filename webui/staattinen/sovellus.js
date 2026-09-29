"use strict";

// XSS-suojaus: enkoodaa arvo turvalliseksi HTML-kontekstiin (innerHTML-sinkit).
// Jaettu globaali; yhteistyo.js ja arviointimuokkaus.js käyttävät samaa.
function escapeHtml(arvo) {
  return String(arvo ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
window.escapeHtml = escapeHtml;

// Opinto-oppaan rikas teksti (Sisu: HTML, Peppi: teksti): vain sallitut tagit ilman
// attribuutteja; muut tagit puretaan tekstiksi. DOMParser ei aja skriptejä.
const SALLITUT_TAGIT = new Set(["P", "BR", "B", "STRONG", "I", "EM", "U", "UL", "OL", "LI",
  "H1", "H2", "H3", "H4", "H5", "H6", "DIV", "SPAN", "SUB", "SUP", "HR"]);
function puhdistaHtml(html) {
  const runko = new DOMParser().parseFromString(`<body>${html}`, "text/html").body;
  for (const el of [...runko.querySelectorAll("*")]) {
    if (!SALLITUT_TAGIT.has(el.tagName)) el.replaceWith(...el.childNodes);
    else for (const a of [...el.attributes]) el.removeAttribute(a.name);
  }
  return runko.innerHTML;
}

// Rivinvaihdot <br>:ksi escapoidusta tekstistä (raporttiosiot, myös raporttimuokkaus.js).
function tekstiHtml(teksti) {
  return escapeHtml(teksti).replace(/\n/g, "<br>");
}

// --- Vikasietoinen haku (huono/katkeileva yhteys) ---

// Ilman aikarajaa jumiin jäänyt yhteys pysäyttäisi automaattipäivityksen (paivitys_kaynnissa).
const HAKU_AIKARAJA_MS = 20000;

// fetch + JSON; verkkovirhe, aikakatkaisu tai 5xx → uusi yritys kasvavalla viiveellä.
async function haeJson(url, yrityksia = 4) {
  for (let yritys = 1; ; yritys++) {
    try {
      const r = await fetch(url, { signal: AbortSignal.timeout(HAKU_AIKARAJA_MS) });
      if (r.ok) return await r.json();
      if (r.status < 500) throw Object.assign(new Error(`HTTP ${r.status}`), { lopullinen: true });
      throw new Error(`HTTP ${r.status}`);
    } catch (e) {
      if (e.lopullinen || yritys >= yrityksia) throw e;
    }
    await new Promise((valmis) => setTimeout(valmis, 1000 * yritys));
  }
}

// --- Otsikon sovitus yhdelle riville ---

// Pienennä otsikon fonttia kunnes se mahtuu yhdelle riville; alaraja 16px.
function sovitaOtsikko(el) {
  if (!el || !el.textContent.trim()) return;
  el.style.whiteSpace = "nowrap";
  el.style.fontSize = "";
  let koko = parseFloat(getComputedStyle(el).fontSize) || 24;
  // Arvio suoraan leveyssuhteesta (yksi asettelu), sitten hienosäätö 1 px kerrallaan.
  if (el.scrollWidth > el.clientWidth) koko = Math.max(16, Math.floor(koko * el.clientWidth / el.scrollWidth));
  el.style.fontSize = koko + "px";
  while (koko > 16 && el.scrollWidth > el.clientWidth) {
    koko -= 1;
    el.style.fontSize = koko + "px";
  }
}

function sovitaAktiivisetOtsikot() {
  document.querySelectorAll(".nakyma.aktiivinen h2").forEach(sovitaOtsikko);
}
window.addEventListener("resize", sovitaAktiivisetOtsikot);

// --- Taulukoiden järjestäminen (sarakeotsikoiden ▲/▼-napit) ---

const KURSSI_SARAKKEET = {
  nimi:     { avain: "KurssiNimi",    tyyppi: "teksti" },
  koodi:    { avain: "Koodi",         tyyppi: "teksti" },
  taso:     { avain: "Taso",          tyyppi: "teksti" },
  oppiaine: { avain: "Oppiaine",      tyyppi: "teksti" },
  op:       { avain: "Opintopisteet", tyyppi: "numero" },
};

// localeCompare(…, "fi") rakentaisi lajittelusäännöt joka vertailussa (~10 000 riviä).
const LAJITTELIJA = new Intl.Collator("fi");

// Vertailufunktio kurssiobjekteille valitun sarakkeen ja suunnan mukaan.
function vertaaKursseja(sarake, suunta) {
  const s = KURSSI_SARAKKEET[sarake];
  const kerroin = suunta === "laskeva" ? -1 : 1;
  return (a, b) => {
    if (s.tyyppi === "numero") {
      const av = a[s.avain] ?? -Infinity, bv = b[s.avain] ?? -Infinity;
      return (av - bv) * kerroin;
    }
    return LAJITTELIJA.compare(String(a[s.avain] ?? ""), String(b[s.avain] ?? "")) * kerroin;
  };
}

// Lisää (kerran) ja aktivoi ▲▼-napit sarakeotsikoihin (th[data-jarjesta]).
// tila-objektia ({ sarake, suunta }) mutatoidaan klikillä, minkä jälkeen
// paivita() renderöi taulukon uudelleen.
function varustaJarjestys(thead, tila, paivita) {
  thead.querySelectorAll("th[data-jarjesta]").forEach((th) => {
    const sarake = th.dataset.jarjesta;
    let napit = th.querySelector(".jarjesta-napit");
    if (!napit) {
      napit = document.createElement("span");
      napit.className = "jarjesta-napit";
      napit.innerHTML =
        `<button class="jarjesta-nappi" data-suunta="nouseva" title="Järjestä nousevasti">▲</button>`
        + `<button class="jarjesta-nappi" data-suunta="laskeva" title="Järjestä laskevasti">▼</button>`;
      th.appendChild(napit);
      napit.querySelectorAll(".jarjesta-nappi").forEach((b) => {
        b.addEventListener("click", (e) => {
          e.stopPropagation();
          tila.sarake = sarake;
          tila.suunta = b.dataset.suunta;
          paivita();
        });
      });
    }
    napit.querySelectorAll(".jarjesta-nappi").forEach((b) => {
      b.classList.toggle("aktiivinen", tila.sarake === sarake && tila.suunta === b.dataset.suunta);
    });
  });
}

// --- Reititys ---

function navigoi(polku) {
  history.pushState({}, "", polku);
  renderoi();
}

window.addEventListener("popstate", renderoi);

// Valittujen kurssien tilat ovat omia sivujaan (/tutkimukset/<slug>/kurssit-valittu …),
// jotta suodatinnäkymät ja läsnäolo koskevat vain yhtä tilaa eikä muita ladata turhaan.
const KURSSIT_TILAT = { "kurssit-valittu": "mukana", "kurssit-odottaa": "odottaa", "kurssit-hylatty": "hylätty" };

function jaaPolku() {
  const osat = location.pathname.replace(/^\//, "").split("/").filter(Boolean);
  if (osat[0] === "tutkimukset" && osat[1]) {
    const tila = KURSSIT_TILAT[osat[2]] || null;
    return { sivu: "tutkimukset", slug: osat[1], alasivu: tila ? "kurssit" : osat[2] || "tiedot", tila };
  }
  return { sivu: osat[0] || "korkeakoulut", slug: null, alasivu: null };
}

async function renderoi() {
  const r = jaaPolku();

  // Päänav aktiivinen kohta
  document.querySelectorAll("#paanav button").forEach((b) => {
    const kohde = b.dataset.polku.replace("/", "");
    b.classList.toggle("aktiivinen", kohde === r.sivu || (r.sivu === "tutkimukset" && kohde === "tutkimukset"));
  });

  // Kaikki osiot piilotetaan
  document.querySelectorAll(".nakyma").forEach((s) => s.classList.remove("aktiivinen"));

  if (r.sivu === "tutkimukset" && r.slug) {
    if (r.alasivu === "kurssit" && !r.tila) {  // alavalikon nappi / vanha polku → oletustila
      history.replaceState({}, "", `/tutkimukset/${r.slug}/kurssit-valittu`);
      return renderoi();
    }
    if (r.tila) aktiivinen_tila = r.tila;
    await renderTutkimusKonteksti(r.slug, r.alasivu);
  } else {
    document.getElementById("tutkimus-nav").classList.add("piilotettu");
    if (r.sivu === "korkeakoulut") {
      document.getElementById("s-korkeakoulut").classList.add("aktiivinen");
      await lataaKorkeakoulut();
    } else if (r.sivu === "kurssit") {
      document.getElementById("s-kurssit").classList.add("aktiivinen");
      rekisteroiKurssitNakymat();
    } else if (r.sivu === "tutkimukset") {
      document.getElementById("s-tutkimukset").classList.add("aktiivinen");
      laataaTutkimukset();
    }
  }
  sovitaAktiivisetOtsikot();
  merkitsePaivitetty();
}

// --- Päänav klikki ---

document.querySelectorAll("#paanav button").forEach((b) => {
  b.addEventListener("click", () => navigoi(b.dataset.polku));
});

// --- Korkeakoulut ---

// "YYYY-YYYY" tai "YYYY-YY" (Sisu/HY) -> [alkuvuosi, loppuvuosi]; null jos virheellinen
function parsiVuodet(kausi) {
  const m = /^(\d{4})-(\d{2,4})$/.exec((kausi || "").trim());
  if (!m) return null;
  const alku = parseInt(m[1], 10);
  let loppu;
  if (m[2].length === 2) {
    loppu = Math.floor(alku / 100) * 100 + parseInt(m[2], 10);
    if (loppu < alku) loppu += 100;
  } else {
    loppu = parseInt(m[2], 10);
  }
  return [alku, loppu];
}

// Opinto-opas-linkki muodossa "Sisu: sisu.helsinki.fi" (tyyppi tekstiin, https:// pois)
function opasLinkki(k) {
  const tyyppi = escapeHtml(k.OpsTyyppi || "");
  if (!k.OpsOsoite) return tyyppi;
  const host = k.OpsOsoite.replace(/^https?:\/\//, "").replace(/\/+$/, "");
  return `<a href="${encodeURI(k.OpsOsoite)}" target="_blank" rel="noopener" class="ops-linkki">`
    + `${tyyppi}: ${escapeHtml(host)}</a>`;
}

// Vaihteleva pastellisävy vuoden mukaan (todennäköisesti täydet kaudet)
function pastelli(vuosi) {
  const hue = (vuosi * 47) % 360;
  return `hsl(${hue}, 62%, 88%)`;
}

// Vuosisarakkeiden solut yhdelle koululle: kukin OPS-kausi vie colspan = vuosien
// määrä ja näkyy tiilenä. Pastelli kun kurssimäärä on lähellä rivin suurinta
// (todennäk. kaikki haettu), harmaa kun selvästi vähemmän tai kautta ei ole haettu.
function vuosiSolut(kaudet, minV, maxV) {
  const maxLkm = kaudet.reduce((m, k) => Math.max(m, k.lkm), 0);
  let html = "";
  let col = minV;
  while (col < maxV) {
    const kausi = kaudet.find((x) => x.alku <= col && col < x.loppu);
    if (kausi) {
      const span = Math.min(kausi.loppu, maxV) - col;
      const taysi = maxLkm > 0 && kausi.lkm >= 0.5 * maxLkm;
      const tiili = taysi
        ? `<span class="kk-tiili kk-tiili-taysi" style="background:${pastelli(col)}">${kausi.lkm} kpl</span>`
        : `<span class="kk-tiili kk-tiili-vajaa">${kausi.lkm} kpl</span>`;
      html += `<td class="kk-solu" colspan="${span}">${tiili}</td>`;
      col += span;
    } else {
      html += `<td class="kk-solu"><span class="kk-tiili kk-tiili-eihaettu">ei haettu</span></td>`;
      col += 1;
    }
  }
  return html;
}

async function lataaKorkeakoulut() {
  const otsikko = document.getElementById("korkeakoulut-otsikko");
  const runko = document.getElementById("korkeakoulut-rungot");
  const koulut = await haeJson("/api/korkeakoulut");
  kaikki_koulut = koulut;

  // Parsi kunkin koulun kaudet ja koko aineiston vuosiväli
  let minV = Infinity, maxV = -Infinity;
  for (const k of koulut) {
    k._kaudet = [];
    for (const kausi of (k.KurssitKausittain || [])) {
      const v = parsiVuodet(kausi.Opetusvuosi);
      if (v) k._kaudet.push({ alku: v[0], loppu: v[1], lkm: kausi.lkm });
    }
    k._kaudet.sort((a, b) => a.alku - b.alku);
    for (const kk of k._kaudet) { minV = Math.min(minV, kk.alku); maxV = Math.max(maxV, kk.loppu); }
  }
  const onVuosia = maxV > minV;
  const vuodet = [];
  if (onVuosia) for (let s = minV; s < maxV; s++) vuodet.push(s);

  // Otsikko (kaksirivinen kun vuosisarakkeita on)
  if (onVuosia) {
    otsikko.innerHTML =
      `<tr><th rowspan="2">Nimi</th><th rowspan="2">Opinto-opas</th>`
      + `<th colspan="${vuodet.length}" class="kk-kurssit-otsikko">Järjestelmään haetut kurssit</th></tr>`
      + `<tr>${vuodet.map((s) => `<th class="kk-vuosi">${s}-${s + 1}</th>`).join("")}</tr>`;
  } else {
    otsikko.innerHTML = `<tr><th>Nimi</th><th>Opinto-opas</th></tr>`;
  }

  // Rungot
  runko.innerHTML = "";
  if (koulut.length === 0) {
    runko.innerHTML = `<tr><td colspan="${2 + vuodet.length}">Ei korkeakouluja.</td></tr>`;
    return;
  }
  for (const k of koulut) {
    const rivi = document.createElement("tr");
    rivi.innerHTML = `<td class="kk-nimi">${escapeHtml(k.KouluNimi)}</td>`
      + `<td class="kk-opas">${opasLinkki(k)}</td>`
      + (onVuosia ? vuosiSolut(k._kaudet, minV, maxV) : "");
    runko.appendChild(rivi);
  }

  // Täytä kurssien yliopisto-suodatin
  const suodatin = document.getElementById("suodatin-koulu");
  suodatin.innerHTML = '<option value="">Kaikki yliopistot</option>';
  for (const k of koulut) {
    const opt = document.createElement("option");
    opt.value = k.KKID;
    opt.textContent = k.KouluNimi;
    suodatin.appendChild(opt);
  }
}

// --- Kurssit ---

const TASO_SUOMI = {
  yleis: "Yleisopinnot", perus: "Perusopinnot",
  aine: "Aineopinnot", "syventävä": "Syventävät",
};

let kaikki_kurssit = [];
let kaikki_koulut = [];
// Käynnistyksen korkeakoululataus: kurssirivit odottavat sitä, muuten
// opinto-opaslinkit puuttuisivat hitaalla yhteydellä seuraavaan pollaukseen asti.
let koulut_ladattu = Promise.resolve();
let kurssit_jarjestys = { sarake: null, suunta: null };

function kurssiUrl(kurssi) {
  const koulu = kaikki_koulut.find((k) => k.KKID === kurssi.KKID);
  if (!koulu || !kurssi.LahdeId) return null;
  if (koulu.OpsTyyppi === "Sisu")
    return `${koulu.OpsOsoite}/student/courseunit/${kurssi.LahdeId}/brochure`;
  if (!kurssi.Koodi) return null;
  return `${koulu.OpsOsoite}/fi/opintojakso/${kurssi.Koodi}/${kurssi.LahdeId}?period=${kurssi.Opetusvuosi}`;
}

function koulunLyhenne(koulu) {
  try {
    const osat = new URL(koulu.OpsOsoite).hostname.split(".");
    return (koulu.OpsTyyppi === "Sisu" ? osat[1] : osat[osat.length - 2])
      ?.toUpperCase() || "";
  } catch { return ""; }
}

// Opinto-opas-linkki (🌐 lyhenne · tyyppi) tai "" jos osoitetta ei ole.
function kurssiOpasLinkki(kurssi) {
  const url = kurssiUrl(kurssi);
  if (!url) return "";
  const koulu = kaikki_koulut.find((k) => k.KKID === kurssi.KKID);
  if (!koulu) return "";
  return `<a href="${escapeHtml(url)}" target="_blank" rel="noopener" class="ops-linkki">`
    + `🌐 ${escapeHtml(koulunLyhenne(koulu))} · ${escapeHtml(koulu.OpsTyyppi)}</a>`;
}

// Koodi-solun sisältö: kurssikoodi + opinto-opaslinkki seuraavalla rivillä.
function koodiJaOpasLinkki(kurssi) {
  const linkki = kurssiOpasLinkki(kurssi);
  return `${escapeHtml(kurssi.Koodi)}${linkki ? `<br>${linkki}` : ""}`;
}

// Nimi + opas-linkki samassa solussa (näkymät joissa ei ole Koodi-saraketta).
function kurssiLinkki(kurssi) {
  const linkki = kurssiOpasLinkki(kurssi);
  const nimi = escapeHtml(kurssi.KurssiNimi);
  return linkki ? `${nimi} ${linkki}` : nimi;
}

// Taso suomeksi (tai raakana) solun tekstiksi; "—" jos puuttuu.
function tasoTeksti(taso) {
  return taso ? escapeHtml(TASO_SUOMI[taso] || taso) : "—";
}

// Kurssirivin taso-, oppiaine- ja op-solut (kurssilista ja tutkimuksen kurssit).
function kurssiMetaSolut(k) {
  return `<td>${tasoTeksti(k.Taso)}</td>
      <td>${escapeHtml(k.Oppiaine || "—")}</td>
      <td class="op">${escapeHtml(k.Opintopisteet ?? "—")}</td>`;
}

function ryhmitaKurssit(kurssit) {
  const ryhmat = {};
  for (const k of kurssit) {
    const avain = k.Koodi || k.KurssiNimi;
    if (!ryhmat[avain]) ryhmat[avain] = [];
    ryhmat[avain].push(k);
  }
  for (const avain of Object.keys(ryhmat)) {
    ryhmat[avain].sort((a, b) => b.Opetusvuosi.localeCompare(a.Opetusvuosi));
  }
  return ryhmat;
}

// Täytä OPS-lukuvuosi-suodatin (uusin ensin), oletukseksi uusin
async function taytaLukuvuodet() {
  const sel = document.getElementById("suodatin-lukuvuosi");
  const vuodet = await haeJson("/api/lukuvuodet");
  sel.innerHTML = vuodet.map((v) => `<option value="${escapeHtml(v)}">${escapeHtml(v)}</option>`).join("");
  // Lista on uusin-ensin, joten ensimmäinen optio (oletusvalinta) on viimeisin vuosi
}

// Täytä taso-suodatin senhetkisen lukuvuoden + yliopiston mukaan (säilytä valinta)
async function taytaTasot(lukuvuosi, kkid) {
  const sel = document.getElementById("suodatin-taso");
  const valittu = sel.value;
  const params = new URLSearchParams();
  if (lukuvuosi) params.set("lukuvuosi", lukuvuosi);
  if (kkid) params.set("kkid", kkid);
  const tasot = await haeJson(`/api/tasot?${params}`);
  // Näytä raa'at arvot sellaisinaan: kannassa on rinnakkaisia muotoja
  // ("aine" ja "Aineopinnot"), eikä TASO_SUOMI-mappaus saa piilottaa niitä.
  sel.innerHTML = '<option value="">Kaikki tasot</option>'
    + tasot.map((t) => `<option value="${escapeHtml(t)}">${escapeHtml(t)}</option>`).join("");
  if (valittu && tasot.includes(valittu)) sel.value = valittu;  // säilytä jos yhä tarjolla
}

// Kurssilista osissa (tuotannossa ~7 Mt kerralla); pieni ensimmäinen osa, jotta
// rivit näkyvät heti, sitten isompia (vähemmän kiertoviiveitä). Taulukko renderöidään
// ensimmäisen osan jälkeen, sitten korkeintaan OSARENDER_VALI_MS välein ja
// lopuksi — koko listan uudelleenrakennus joka osalla olisi O(n²).
const KURSSIT_ENSIMMAINEN_OSA = 250;
const KURSSIT_OSA = 2000;
const OSARENDER_VALI_MS = 2000;
const KURSSIT_RIVIERA = 300;
let kurssit_lataus = 0;
let kurssit_kesken = false;
let kurssit_renderointi = 0;

async function lataaKurssit() {
  const lataus = ++kurssit_lataus;
  const sel = document.getElementById("suodatin-lukuvuosi");
  if (!sel.options.length) await taytaLukuvuodet();
  const kkid = document.getElementById("suodatin-koulu").value;
  taytaTasot(sel.value, kkid);  // ei awaitia: tasovalikko ei saa viivästää listaa
  const params = new URLSearchParams();
  if (sel.value) params.set("lukuvuosi", sel.value);
  if (kkid) params.set("kkid", kkid);
  kaikki_kurssit = [];
  kurssit_kesken = true;
  kurssit_renderointi++;  // edellisen listan erät eivät jatku latausrivin perään
  document.getElementById("kurssit-rungot").innerHTML = '<tr><td colspan="6">Ladataan kursseja…</td></tr>';
  let renderoity = 0;
  try {
    for (;;) {
      const koko = kaikki_kurssit.length ? KURSSIT_OSA : KURSSIT_ENSIMMAINEN_OSA;
      params.set("alku", kaikki_kurssit.length);
      params.set("koko", koko);
      const osa = await haeJson(`/api/kurssit?${params}`);
      await koulut_ladattu;
      if (lataus !== kurssit_lataus || location.pathname !== "/kurssit") return;  // suodatin vaihtui / poistuttiin
      kaikki_kurssit.push(...osa);
      kurssit_kesken = osa.length === koko;
      if (!kurssit_kesken || Date.now() - renderoity > OSARENDER_VALI_MS) {
        renderKurssit();
        renderoity = Date.now();
      }
      if (!kurssit_kesken) return;
    }
  } catch (_) {
    if (lataus !== kurssit_lataus) return;
    kurssit_kesken = false;
    renderKurssit();
    document.getElementById("kurssit-lkm").textContent += " — lataus keskeytyi (yhteysvirhe)";
  }
}

function renderKurssit() {
  const taso = document.getElementById("suodatin-taso").value;
  const suodatettu = taso ? kaikki_kurssit.filter((k) => k.Taso === taso) : kaikki_kurssit;
  const ryhmat = ryhmitaKurssit(suodatettu);
  const runko = document.getElementById("kurssit-rungot");
  const lkm = Object.keys(ryhmat).length;
  document.getElementById("kurssit-lkm").textContent = `${lkm} kurssia${kurssit_kesken ? " — ladataan lisää…" : ""}`;
  varustaJarjestys(document.querySelector("#s-kurssit thead"), kurssit_jarjestys, renderKurssit);
  const kierros = ++kurssit_renderointi;  // keskeyttää edellisen renderöinnin erät
  if (lkm === 0) {
    runko.innerHTML = '<tr><td colspan="6">Ei kursseja.</td></tr>';
    return;
  }
  const ryhmatLista = Object.values(ryhmat);
  if (kurssit_jarjestys.sarake) {
    const vertaa = vertaaKursseja(kurssit_jarjestys.sarake, kurssit_jarjestys.suunta);
    ryhmatLista.sort((a, b) => vertaa(a[0], b[0]));
  }
  // Rivit merkkijonoina ja delegoitu klikkikäsittelijä (alla): ~10 000 riviä ilman
  // rivikohtaisia elementtejä ja kuuntelijoita.
  const rivit = ryhmatLista.map((versiot) => {
    const uusin = versiot[0];
    const vuosiSolmu = versiot.length > 1
      ? `<select class="vuosivalinta">${versiot.map((v) =>
          `<option value="${v.KID}">${escapeHtml(v.Opetusvuosi)}</option>`).join("")}</select>`
      : escapeHtml(uusin.Opetusvuosi);
    return `<tr class="kurssi-rivi" data-kid="${uusin.KID}">
      <td>${escapeHtml(uusin.KurssiNimi)}</td>
      <td class="koodi">${koodiJaOpasLinkki(uusin)}</td>
      ${kurssiMetaSolut(uusin)}
      <td>${vuosiSolmu}</td></tr>`;
  });
  // DOMiin erissä: koko listan asettelu kerralla jumitti sivun ~1 s (8 700 riviä),
  // erä ~50 ms. Kaikki rivit päätyvät lopulta DOMiin (selaimen haku toimii).
  let i = 0;
  const era = () => {
    if (kierros !== kurssit_renderointi) return;
    runko.insertAdjacentHTML("beforeend", rivit.slice(i, i += KURSSIT_RIVIERA).join(""));
    if (i < rivit.length) setTimeout(era);
  };
  runko.innerHTML = "";
  era();
}

// Rivin klikkaus avaa kurssin (valitun vuoden version); linkki ja vuosivalinta eivät.
document.getElementById("kurssit-rungot").addEventListener("click", (e) => {
  const rivi = e.target.closest("tr.kurssi-rivi");
  if (!rivi || e.target.closest("a, select")) return;
  const valinta = rivi.querySelector(".vuosivalinta");
  avaaModaali(parseInt(valinta ? valinta.value : rivi.dataset.kid));
});

// Suodatinnäkymien (välilehdet, nakymat.js) välilehden nimi suodattimesta.
function suodatinNimi(s) {
  const koulu = kaikki_koulut.find((k) => String(k.KKID) === String(s.kkid));
  return [
    koulu && (koulunLyhenne(koulu) || koulu.KouluNimi),
    s.taso && (TASO_SUOMI[s.taso] || s.taso),
    s.lukuvuosi,
    s.hakusana && `"${s.hakusana}"`,
  ].filter(Boolean).join(" · ");
}

function rekisteroiKurssitNakymat() {
  const lv = document.getElementById("suodatin-lukuvuosi");
  const koulu = document.getElementById("suodatin-koulu");
  const taso = document.getElementById("suodatin-taso");
  const aseta = async (s, lataa = true) => {
    if (!lv.options.length) await taytaLukuvuodet();
    lv.value = s.lukuvuosi || lv.options[0]?.value || "";
    koulu.value = s.kkid || "";
    // taytaTasot säilyttää valinnan vain jos se on jo selectin arvo
    taso.innerHTML = `<option value="${escapeHtml(s.taso || "")}"></option>`;
    if (lataa) await lataaKurssit();
    else await taytaTasot(lv.value, koulu.value);
  };
  window.rekisteroiNakymat?.({
    otsikko: document.querySelector("#s-kurssit h2"),
    palkki: document.getElementById("kurssit-suodatin"),
    lue: () => ({ lukuvuosi: lv.value || null, kkid: koulu.value || null, taso: taso.value || null }),
    aseta,
    // Oletuslukuvuotta (uusin) ei toisteta nimessä
    nimea: (s) => suodatinNimi({ ...s, lukuvuosi: s.lukuvuosi === lv.options[0]?.value ? null : s.lukuvuosi }),
  });
  aseta({});
}

// "+"-tilassa (uuden näkymän luonti) lista on piilossa: päivitä vain tasovalikko, älä lataa.
function kurssiSuodatinMuuttui() {
  if (window.omaNakyma?.() === "+") {
    taytaTasot(document.getElementById("suodatin-lukuvuosi").value, document.getElementById("suodatin-koulu").value);
  } else {
    lataaKurssit();
  }
}
document.getElementById("suodatin-lukuvuosi").addEventListener("change", kurssiSuodatinMuuttui);
document.getElementById("suodatin-koulu").addEventListener("change", kurssiSuodatinMuuttui);
document.getElementById("suodatin-taso").addEventListener("change", renderKurssit);

// --- Modaali (kurssin tiedot) ---

const KIELI_SUOMI = {
  "urn:code:language:fi": "suomi", "urn:code:language:en": "englanti",
  "urn:code:language:sv": "ruotsi",
};

function _monikielinen(arvo) {
  if (arvo && typeof arvo === "object") return arvo.fi || arvo.en || "";
  return arvo || "";
}

// Peppi: contentList-rakenne nimetyillä osioilla
function peppiKuvausOsat(data) {
  return (data.contentList || [])
    .filter((o) => (o.content?.valueFi || "").trim())
    .map((o) => ({
      otsikko: o.title?.valueFi || "",
      sisalto: puhdistaHtml((o.content?.valueFi || "").replace(/\n/g, "<br>")),
    }));
}

// Sisu: KORI-rajapinnan kentät kartoitettuna samoihin osioihin kuin Peppi
function sisuKuvausOsat(data) {
  const osat = [];
  const lisaa = (otsikko, sisalto) => {
    if (sisalto && sisalto.trim()) osat.push({ otsikko, sisalto: puhdistaHtml(sisalto) });
  };
  lisaa("Lyhyt kuvaus", _monikielinen(data.tweetText));
  lisaa("Osaamistavoitteet", _monikielinen(data.outcomes));
  lisaa("Sisältö", _monikielinen(data.content));
  lisaa(
    "Suoritustavat",
    (data.completionMethods || []).map((c) => _monikielinen(c.description)).filter(Boolean).join("<br>"),
  );
  lisaa("Esitietovaatimukset", _monikielinen(data.prerequisites));
  lisaa("Oppimateriaalit", _monikielinen(data.learningMaterial));
  lisaa(
    "Kurssikirjallisuus",
    (data.literature || []).map((l) => l.name).filter(Boolean).map((n) => `• ${escapeHtml(n)}`).join("<br>"),
  );
  const kielet = (data.possibleAttainmentLanguages || []).map((k) => KIELI_SUOMI[k] || k).join(", ");
  lisaa("Opetuskieli", escapeHtml(kielet));
  lisaa("Lisätiedot", _monikielinen(data.additional));
  return osat;
}

async function avaaModaali(kid) {
  const kurssi = await haeJson(`/api/kurssit/${kid}`);
  const opsUrl = kurssiUrl(kurssi);
  const nimi = escapeHtml(kurssi.KurssiNimi);
  const nimiHtml = opsUrl
    ? `<a href="${escapeHtml(opsUrl)}" target="_blank" rel="noopener">${nimi}</a>`
    : nimi;
  document.getElementById("modaali-otsikko").innerHTML =
    `${nimiHtml} (${escapeHtml(kurssi.Koodi || "—")})`;

  const koulu = kaikki_koulut.find((k) => k.KKID === kurssi.KKID);
  let kuvaus = "—";
  if (kurssi.OpsKuvaus) {
    try {
      const data = JSON.parse(kurssi.OpsKuvaus);
      const osat = koulu?.OpsTyyppi === "Sisu" ? sisuKuvausOsat(data) : peppiKuvausOsat(data);
      kuvaus = osat.length
        ? osat.map((o) => `<strong>${escapeHtml(o.otsikko)}</strong><br>${o.sisalto}`).join("<hr>")
        : "—";
    } catch {
      kuvaus = tekstiHtml(kurssi.OpsKuvaus);
    }
  }

  document.getElementById("modaali-teksti").innerHTML = `
    <table class="modaali-meta">
      <tr><th>Taso</th><td>${tasoTeksti(kurssi.Taso)}</td></tr>
      <tr><th>Oppiaine</th><td>${escapeHtml(kurssi.Oppiaine || "—")}</td></tr>
      <tr><th>Opintopisteet</th><td>${escapeHtml(kurssi.Opintopisteet ?? "—")}</td></tr>
      <tr><th>Opetusvuosi</th><td>${escapeHtml(kurssi.Opetusvuosi)}</td></tr>
    </table>
    <div class="ops-kuvaus">${kuvaus}</div>`;
  document.getElementById("modaali").classList.remove("piilotettu");
}

document.getElementById("modaali-sulje").addEventListener("click", () => {
  document.getElementById("modaali").classList.add("piilotettu");
});
document.getElementById("modaali").addEventListener("click", (e) => {
  if (e.target === e.currentTarget)
    document.getElementById("modaali").classList.add("piilotettu");
});

// --- Tutkimukset ---

let tutkimukset_lista = [];

async function laataaTutkimukset() {
  const runko = document.getElementById("tutkimukset-rungot");
  tutkimukset_lista = await haeJson("/api/tutkimukset");
  runko.innerHTML = "";
  if (tutkimukset_lista.length === 0) {
    runko.innerHTML = '<tr><td colspan="5">Ei tutkimuksia.</td></tr>';
    return;
  }
  for (const t of tutkimukset_lista) {
    const rivi = document.createElement("tr");
    const lkm = t.MukanaLkm ?? 0;
    const slug = escapeHtml(t.Slug);
    rivi.innerHTML = `
      <td class="kurssi-rivi tutkimus-nimi-solu">${escapeHtml(t.LuokittelunNimi)}</td>
      <td>${escapeHtml(t.Lukuvuosi || "—")}</td>
      <td>${escapeHtml(t.Tasorajaus || "—")}</td>
      <td class="tutkimus-oppiaine-solu" title="${escapeHtml(t.Oppiainerajaus)}">${escapeHtml(t.Oppiainerajaus || "—")}</td>
      <td class="tutkimus-toiminnot">
        ${verkkosivuIkoni(t.Verkkosivu)}
        <button class="nappi-pieni" data-slug="${slug}" data-alasivu="kurssit">Valitut kurssit (${escapeHtml(lkm)})</button>
        <button class="nappi-pieni" data-slug="${slug}" data-alasivu="arvioinnit">Arvioinnit</button>
        <button class="nappi-pieni" data-slug="${slug}" data-alasivu="raportti">Raportti</button>
      </td>`;
    rivi.querySelector(".tutkimus-nimi-solu").addEventListener("click", () =>
      navigoi(`/tutkimukset/${t.Slug}`)
    );
    rivi.querySelectorAll(".nappi-pieni").forEach((b) =>
      b.addEventListener("click", () => navigoi(`/tutkimukset/${b.dataset.slug}/${b.dataset.alasivu}`))
    );
    runko.appendChild(rivi);
  }
}

// --- Tutkimus-konteksti (alinav + sisältö) ---

let aktiivinen_tutkimus = null;

async function renderTutkimusKonteksti(slug, alasivu) {
  if (!aktiivinen_tutkimus || aktiivinen_tutkimus.Slug !== slug) {
    aktiivinen_tutkimus = await haeJson(`/api/tutkimukset/${slug}`).catch(() => null);
  }
  if (!aktiivinen_tutkimus) {
    document.getElementById("tutkimus-nav").classList.add("piilotettu");
    return;
  }

  // Päivitä alinav
  const nav = document.getElementById("tutkimus-nav");
  nav.classList.remove("piilotettu");
  document.getElementById("tutkimus-nav-nimi").textContent = aktiivinen_tutkimus.LuokittelunNimi;

  nav.querySelectorAll("[data-tutkimus-alasivu]").forEach((b) => {
    b.classList.toggle("aktiivinen", b.dataset.tutkimusAlasivu === alasivu);
  });
  nav.querySelectorAll("button[data-tutkimus-alasivu]").forEach((b) => {
    b.onclick = () => navigoi(`/tutkimukset/${slug}/${b.dataset.tutkimusAlasivu}`);
  });

  const navTila = document.getElementById("tutkimus-nav-tila");
  navTila.classList.toggle("piilotettu", alasivu !== "kurssit");

  // Näkymä näkyviin heti — data täyttyy perässä (huonolla yhteydellä sekunteja).
  document.getElementById(`s-tutkimus-${alasivu}`)?.classList.add("aktiivinen");
  sovitaAktiivisetOtsikot();
  if (alasivu === "tiedot") {
    renderTutkimusTiedot(aktiivinen_tutkimus);
  } else if (alasivu === "kurssit") {
    await renderTutkimusKurssit(slug, aktiivinen_tutkimus.LuokittelunNimi);
  } else if (alasivu === "arvioinnit") {
    await renderTutkimusArvioinnit(slug, aktiivinen_tutkimus.LuokittelunNimi);
  } else if (alasivu === "raportti") {
    await renderTutkimusRaportti(slug, aktiivinen_tutkimus);
  }
}

function verkkosivuLinkki(url) {
  if (!url) return "—";
  const e = escapeHtml(url);
  return /^https?:\/\//i.test(url)
    ? `<a href="${e}" target="_blank" rel="noopener" class="ops-linkki">🌐 ${e}</a>`
    : e;
}

// Pelkkä maapallo-ikonilinkki (esim. tutkimuslistan toimintosarakkeeseen).
function verkkosivuIkoni(url) {
  if (!url || !/^https?:\/\//i.test(url)) return "";
  const e = escapeHtml(url);
  return `<a href="${e}" target="_blank" rel="noopener" class="ops-linkki" title="${e}">🌐</a>`;
}

const KYS_TYYPPI_NIMI = { vapaa_teksti: "Vapaa teksti", luokittelu: "Luokittelu", asteikko: "Asteikko", lista: "Lista" };

function _kysymysMaarittelyHtml(k) {
  const tyyppi = k.Luokittelu || "vapaa_teksti";
  const m = k.LuokitteluMaarittely || {};
  let maar = "";
  if (tyyppi === "luokittelu" && Array.isArray(m.luokat)) {
    maar = `<ul class="kys-maar">${m.luokat.map((l) => `<li><strong>${escapeHtml(l.nimi || "")}</strong>: ${escapeHtml(l.kuvaus || "")}</li>`).join("")}</ul>`;
  } else if (tyyppi === "asteikko") {
    const pisteet = Array.isArray(m.pisteet) ? m.pisteet : [];
    maar = `<div class="kys-maar">Asteikko ${escapeHtml(m.minimi ?? "?")}–${escapeHtml(m.maksimi ?? "?")}`
      + (pisteet.length ? `<ul>${pisteet.map((p) => `<li>${escapeHtml(String(p.arvo))}: ${escapeHtml(p.kuvaus || "")}</li>`).join("")}</ul>` : "")
      + `</div>`;
  } else if (tyyppi === "lista") {
    maar = `<div class="kys-maar">Kohtien yläraja: ${m.max_kohdat ? escapeHtml(String(m.max_kohdat)) : "ei rajaa"}</div>`;
  }
  return `<span class="kys-tyyppi">${escapeHtml(KYS_TYYPPI_NIMI[tyyppi] || tyyppi)}</span>${maar}`;
}

function renderTutkimusTiedot(t) {
  const kysymysLista = (t.Kysymykset && t.Kysymykset.length > 0)
    ? `<ol class="kys-lista">${t.Kysymykset.map((k) => `<li><div class="kys-teksti">${escapeHtml(k.Kysymys)}</div>${_kysymysMaarittelyHtml(k)}</li>`).join("")}</ol>`
    : `<p class="tulossa">Ei arviointikysymyksiä.</p>`;
  document.getElementById("tutkimus-tiedot-sisalto").innerHTML = `
    <h2>${escapeHtml(t.LuokittelunNimi)}</h2>
    <table class="modaali-meta">
      <tr><th>Slug</th><td>${escapeHtml(t.Slug)}</td></tr>
      <tr><th>Verkkosivu</th><td>${verkkosivuLinkki(t.Verkkosivu)}</td></tr>
      <tr><th>Tasorajaus</th><td>${escapeHtml(t.Tasorajaus || "—")}</td></tr>
      <tr><th>Oppiainerajaus</th><td>${escapeHtml(t.Oppiainerajaus || "—")}</td></tr>
    </table>
    <h3>Valintakehote</h3>
    <pre class="kehote-teksti">${escapeHtml(t.Luokittelukehote)}</pre>
    <h3>Arviointikehote</h3>
    <pre class="kehote-teksti">${escapeHtml(t.Arviointikehote)}</pre>
    <h3>Raportointikehote</h3>
    <pre class="kehote-teksti">${escapeHtml(t.Raportointikehote || "—")}</pre>
    <h3>Arviointikysymykset</h3>
    ${kysymysLista}`;
}

let tutkimus_luokitukset = [];
let aktiivinen_tila = "mukana";

// --- HITL ---

let hitl_kid = null;
let hitl_uusi_tila = null;
let hitl_kurssiniimi = "";
let hitl_nimi = localStorage.getItem("hitl_nimi") || "";
let hitl_sahkoposti = localStorage.getItem("hitl_sahkoposti") || "";

function avaaHitlModaali(kid, kurssiniimi, ai_perustelu, uusi_tila) {
  hitl_kid = kid;
  hitl_uusi_tila = uusi_tila;
  hitl_kurssiniimi = kurssiniimi;
  const toiminto = uusi_tila ? "Sisällytä tutkimukseen" : "Poista tutkimuksesta";
  document.getElementById("hitl-otsikko").textContent = `${toiminto}: ${kurssiniimi}`;
  const aiOsio = document.getElementById("hitl-ai-perustelu-osio");
  if (ai_perustelu) {
    aiOsio.innerHTML = `<strong>Tekoälyn perustelu:</strong> ${escapeHtml(ai_perustelu)}`;
  } else {
    aiOsio.textContent = "";
  }
  document.getElementById("hitl-nimi").value = hitl_nimi;
  document.getElementById("hitl-sahkoposti").value = hitl_sahkoposti;
  document.getElementById("hitl-perustelu").value = "";
  document.querySelectorAll('input[name="hitl-juurisyy"]').forEach((r) => (r.checked = false));
  document.getElementById("hitl-laheta").textContent = toiminto;
  const modaali = document.getElementById("hitl-modaali");
  modaali.classList.remove("piilotettu");
  // Jaettu lomake: muut saman kurssin päätöstä korjaavat näkevät samat arvot ja toisensa.
  window.avaaLomakesessio?.(`hitl:${aktiivinen_tutkimus.TID}:${kid}`, modaali, {
    tallennettu: () => {
      suljeHitlModaali();
      renderTutkimusKurssit(aktiivinen_tutkimus.Slug, aktiivinen_tutkimus.LuokittelunNimi, true);
    },
  });
}

function suljeHitlModaali() {
  window.suljeLomakesessio?.();
  document.getElementById("hitl-modaali").classList.add("piilotettu");
}

document.getElementById("hitl-modaali-sulje").addEventListener("click", suljeHitlModaali);
document.getElementById("hitl-modaali").addEventListener("click", (e) => {
  if (e.target === e.currentTarget) suljeHitlModaali();
});

document.getElementById("hitl-lomake").addEventListener("submit", async (e) => {
  e.preventDefault();
  const nimi = document.getElementById("hitl-nimi").value.trim();
  const sahkoposti = document.getElementById("hitl-sahkoposti").value.trim();
  const perustelu = document.getElementById("hitl-perustelu").value.trim();
  const juurisyy = document.querySelector('input[name="hitl-juurisyy"]:checked')?.value || null;
  if (!nimi || !sahkoposti || !perustelu || !juurisyy) return;

  // Jaetussa lomakkeessa nimi voi olla ensimmäisen avaajan — ei tallenneta omaksi.
  if (window.lomakeOlenAloittaja?.() ?? true) {
    hitl_nimi = nimi;
    hitl_sahkoposti = sahkoposti;
    localStorage.setItem("hitl_nimi", nimi);
    localStorage.setItem("hitl_sahkoposti", sahkoposti);
  }

  const nappi = document.getElementById("hitl-laheta");
  try {
    await lahetaNapilla(nappi, `/api/tutkimukset/${aktiivinen_tutkimus.Slug}/kurssit/${hitl_kid}/hitl`,
                        { uusi_tila: hitl_uusi_tila, perustelu, nimi, sahkoposti, juurisyy });
  } catch (e) {
    nappi.textContent = `Virhe: ${e.message} — yritä uudelleen`;
    return;
  }
  window.lomakeTallennettu?.();
  suljeHitlModaali();
  const toiminto = hitl_uusi_tila ? "sisällytti" : "poisti";
  const tutkimusNimi = aktiivinen_tutkimus?.LuokittelunNimi || aktiivinen_tutkimus?.Slug || "";
  window.lahetaUutinen?.(`${window.omaNimimerkki?.()} ${toiminto} kurssin "${hitl_kurssiniimi}" tutkimuksesta ${tutkimusNimi}`);
  await renderTutkimusKurssit(aktiivinen_tutkimus.Slug, aktiivinen_tutkimus.LuokittelunNimi, true);
});

// Peukutus (luokitus tai arviointivastaus): nimi HITL-lomakkeelta muistetusta,
// muuten yhteistyöprofiilin anonyymi nimimerkki (Anonyymi_Otus_123);
// sähköposti vain jos tiedossa. polku = "<kid>" tai "<kid>/kysymykset/<kysid>".
async function lahetaHyvaksynta(nappi, polku, kohde) {
  const nimi = hitl_nimi || window.omaNimimerkki?.() || "Anonyymi";
  try {
    await lahetaNapilla(nappi, `/api/tutkimukset/${aktiivinen_tutkimus.Slug}/kurssit/${polku}/hyvaksy`,
                        { nimi, sahkoposti: hitl_sahkoposti });
  } catch (_) {
    nappi.textContent = "Virhe";
    return false;
  }
  const tutkimusNimi = aktiivinen_tutkimus?.LuokittelunNimi || aktiivinen_tutkimus?.Slug || "";
  window.lahetaUutinen?.(`${nimi} hyväksyi ${kohde} tutkimuksessa ${tutkimusNimi}`);
  return true;
}

async function hyvaksyLuokitus(nappi) {
  if (await lahetaHyvaksynta(nappi, nappi.dataset.kid, `kurssin "${nappi.dataset.nimi}"`)) {
    await renderTutkimusKurssit(aktiivinen_tutkimus.Slug, aktiivinen_tutkimus.LuokittelunNimi, true);
  }
}

const TUTKIMUS_KURSSIT_KOKO = 100;
let tutkimus_maarat = { mukana: 0, odottaa: 0, "hylätty": 0 };
let tutkimus_sivu = 0;
let luokitus_suodatin = { kkid: null, taso: null, hakusana: null };
let luokitus_jarjestys = { sarake: null, suunta: null };

// --- Jaettu suodatinpalkki (yliopisto + taso + hakusana) — DRY ---

let _suodKoulut = null, _suodTasot = null;

async function _suodatinData() {
  if (!_suodKoulut) _suodKoulut = await haeJson("/api/korkeakoulut");
  if (!_suodTasot) _suodTasot = await haeJson("/api/tasot");
  return { koulut: _suodKoulut, tasot: _suodTasot };
}

function _suodatinParams(tila) {
  const p = new URLSearchParams();
  if (tila.kkid) p.set("kkid", tila.kkid);
  if (tila.taso) p.set("taso", tila.taso);
  if (tila.hakusana) p.set("hakusana", tila.hakusana);
  return p.toString();
}

// Tutkimussivun suodatinnäkymät (välilehdet): tila = jaetun suodatinpalkin tilaobjekti.
function rekisteroiTutkimusNakymat(otsikkoId, palkki, tila, onChange) {
  window.rekisteroiNakymat?.({
    otsikko: document.getElementById(otsikkoId),
    palkki,
    lue: () => ({ ...tila }),
    aseta: async (s, lataa = true) => {
      Object.assign(tila, { kkid: null, taso: null, hakusana: null }, s);
      await rakennaSuodatinPalkki(palkki, tila, onChange);
      if (lataa) await onChange();
    },
    nimea: suodatinNimi,
  });
}

// Rakentaa suodatinkontrollit elementtiin ja kutsuu onChange muutoksilla.
async function rakennaSuodatinPalkki(el, tila, onChange) {
  const { koulut, tasot } = await _suodatinData();
  el.innerHTML =
    `<select class="suod-koulu" title="Yliopisto"><option value="">Kaikki yliopistot</option>`
    + koulut.map((k) => `<option value="${k.KKID}">${escapeHtml(koulunLyhenne(k) || k.KouluNimi)}</option>`).join("")
    + `</select>`
    + `<select class="suod-taso" title="Taso"><option value="">Kaikki tasot</option>`
    + tasot.map((x) => `<option value="${escapeHtml(x)}">${escapeHtml(TASO_SUOMI[x] || x)}</option>`).join("")
    + `</select>`
    + `<input class="suod-haku" type="search" placeholder="Hae nimestä tai koodista…" />`;
  const koulu = el.querySelector(".suod-koulu");
  const taso = el.querySelector(".suod-taso");
  const haku = el.querySelector(".suod-haku");
  koulu.value = tila.kkid || ""; taso.value = tila.taso || ""; haku.value = tila.hakusana || "";
  // "+"-tilassa (uuden näkymän luonti) valinnat vain kerätään — lista on piilossa, ei latausta.
  const muuttui = () => { if (window.omaNakyma?.() !== "+") onChange(); };
  koulu.onchange = () => { tila.kkid = koulu.value || null; muuttui(); };
  taso.onchange = () => { tila.taso = taso.value || null; muuttui(); };
  let viive;
  haku.oninput = () => {
    clearTimeout(viive);
    viive = setTimeout(() => { tila.hakusana = haku.value.trim() || null; muuttui(); }, 300);
  };
}

async function renderTutkimusKurssit(slug, nimi, sailyta = false) {
  document.getElementById("tutkimus-kurssit-otsikko").textContent = `${nimi} — kurssit`;
  // Pollaus / annotoinnin jälkeinen päivitys (sailyta=true) päivittää vain datan
  // — ei nollaa käyttäjän suodatinvalintaa eikä sivua eikä rakenna palkkia uusiksi.
  if (!sailyta) {
    luokitus_suodatin = { kkid: null, taso: null, hakusana: null };
    luokitus_jarjestys = { sarake: null, suunta: null };
    const palkki = document.getElementById("tutkimus-kurssit-suodatin");
    const onChange = () => {
      tutkimus_sivu = 0;
      window.lahetaTilaNyt?.();
      naytaLuokitusLataus();
      return lataaTilaSivu(true);
    };
    // Ei awaitia: palkin data (korkeakoulut, tasot) ei saa viivästää kurssilistaa.
    rakennaSuodatinPalkki(palkki, luokitus_suodatin, onChange);
    rekisteroiTutkimusNakymat("tutkimus-kurssit-otsikko", palkki, luokitus_suodatin, onChange);
    tutkimus_sivu = 0;
    naytaLuokitusLataus();
  }
  await lataaTilaSivu(true);
}

// Käyttäjän vaihto (tila/sivu/suodatin/järjestys): vanha lista pois heti ja latausrivi
// tilalle — muuten edellinen näkymä jää näkyviin kuin mitään ei tapahtuisi.
function naytaLuokitusLataus() {
  document.getElementById("tutkimus-kurssit-rungot").innerHTML =
    '<tr class="lataus-rivi"><td colspan="6">Ladataan kursseja…</td></tr>';
  document.getElementById("tutkimus-kurssit-lkm").textContent = "Ladataan…";
}

let _luokitusLataus = 0;

// Hae aktiivisen välilehden nykyinen sivu (ja maaratKanssa: suodatetut tilamäärät
// rinnakkain) palvelimelta ja renderöi. Vain uusin lataus renderöidään: hitaalla
// yhteydellä edellisen tilan/sivun myöhästynyt vastaus ei saa korvata uutta.
async function lataaTilaSivu(maaratKanssa = false) {
  const lataus = ++_luokitusLataus;
  document.querySelectorAll(".tila-nappi, .tila-nappi-nav").forEach((b) => {
    b.classList.toggle("aktiivinen", b.dataset.tila === aktiivinen_tila);
  });
  varustaJarjestys(
    document.querySelector("#s-tutkimus-kurssit thead"),
    luokitus_jarjestys,
    () => vaihdaSivu(0),
  );
  const slug = aktiivinen_tutkimus.Slug;
  const p = _suodatinParams(luokitus_suodatin);
  const j = luokitus_jarjestys.sarake
    ? `&jarjesta=${luokitus_jarjestys.sarake}&suunta=${luokitus_jarjestys.suunta}` : "";
  const url = `/api/tutkimukset/${slug}/luokitukset?tila=${encodeURIComponent(aktiivinen_tila)}`
    + `&sivu=${tutkimus_sivu}&koko=${TUTKIMUS_KURSSIT_KOKO}` + (p ? `&${p}` : "") + j;
  const [rivit, maarat] = await Promise.all([
    haeJson(url),
    maaratKanssa ? haeJson(`/api/tutkimukset/${slug}/luokitukset/maarat?${p}`) : null,
    koulut_ladattu,
  ]);
  if (lataus !== _luokitusLataus) return;
  if (maarat) {
    tutkimus_maarat = maarat;
    const nimet = { mukana: "Mukana", odottaa: "Odottaa", "hylätty": "Hylätty" };
    document.querySelectorAll(".tila-nappi").forEach((b) => {
      b.textContent = `${nimet[b.dataset.tila]} (${tutkimus_maarat[b.dataset.tila] ?? 0})`;
    });
  }
  tutkimus_luokitukset = rivit;
  renderTutkimusKurssitRivit(tutkimus_luokitukset);
  renderTutkimusKurssitSivutus();
}

function vaihdaSivu(sivu) {
  tutkimus_sivu = sivu;
  window.lahetaTilaNyt?.();
  naytaLuokitusLataus();
  window.scrollTo(0, 0);
  lataaTilaSivu();
}

// Läsnäolotieto (yhteistyo.js): sivutussivu, jotta muut näkevät palluran sivunumeron kohdalla.
window.omaSivunumero = () => (jaaPolku().alasivu === "kurssit" ? tutkimus_sivu : null);

let _sivutusMuut = [];

// Sivutus ylä- ja alalaitaan: Edellinen, sivunumerot, Seuraava. Samassa näkymässä
// eri sivulla olevat muut käyttäjät näkyvät pallurana oman sivunumeronsa kohdalla.
function renderTutkimusKurssitSivutus() {
  const kpl = tutkimus_maarat[aktiivinen_tila] ?? 0;
  document.getElementById("tutkimus-kurssit-lkm").textContent = `${kpl} kurssia`;
  const sivuja = Math.ceil(kpl / TUTKIMUS_KURSSIT_KOKO);
  const omaNakyma = window.omaNakyma?.() ?? null;
  const muut = _sivutusMuut.filter((k) => k.profiili && k.sivu === location.pathname
    && (k.nakyma ?? null) === omaNakyma && k.sivunumero != null && k.sivunumero !== tutkimus_sivu);
  // Ensimmäinen, viimeinen, nykyinen ±2 ja sivut, joilla on muita käyttäjiä; välit "…".
  const naytettavat = [...new Set([0, sivuja - 1, ...muut.map((k) => k.sivunumero),
    ...[-2, -1, 0, 1, 2].map((d) => tutkimus_sivu + d)])]
    .filter((i) => i >= 0 && i < sivuja).sort((a, b) => a - b);
  document.querySelectorAll(".tutkimus-kurssit-sivutus").forEach((el) => {
    el.innerHTML = "";
    if (sivuja <= 1) return;
    const nappi = (teksti, sivu, luokka = "") => {
      const b = document.createElement("button");
      b.textContent = teksti;
      b.className = luokka;
      b.disabled = sivu < 0 || sivu >= sivuja || sivu === tutkimus_sivu;
      b.addEventListener("click", () => vaihdaSivu(sivu));
      el.appendChild(b);
      return b;
    };
    nappi("← Edellinen", tutkimus_sivu - 1);
    let edellinen = -1;
    for (const i of naytettavat) {
      if (i > edellinen + 1) el.insertAdjacentHTML("beforeend", '<span class="sivu-vali">…</span>');
      const b = nappi(String(i + 1), i, i === tutkimus_sivu ? "sivu-numero aktiivinen" : "sivu-numero");
      for (const k of muut) if (k.sivunumero === i) b.appendChild(window.luoPikkupallura(k));
      edellinen = i;
    }
    nappi("Seuraava →", tutkimus_sivu + 1);
  });
}

// Kutsutaan jokaisella kursoriliikkeellä → renderöi vain kun sivutuspallurat muuttuvat.
let _sivutusAvain = "";
window.paivitaSivutusPallurat = (muut) => {
  _sivutusMuut = muut;
  const avain = JSON.stringify(muut.map((k) => [k.id, k.sivu, k.nakyma, k.sivunumero, k.taso, k.nimimerkki, k.profiili]));
  if (avain === _sivutusAvain) return;
  _sivutusAvain = avain;
  if (jaaPolku().alasivu === "kurssit") renderTutkimusKurssitSivutus();
};

// Meta-perustelun (metasuodatus.py) ystävällinen esitys: säilytä kurssin oma
// taso/oppiaine, mutta pudota koko rajauslista (voi olla satoja alkioita).
function metaPerusteluYstavallinen(teksti) {
  const runko = String(teksti || "").replace(/^meta:\s*/, "");
  const osat = [];
  // taso käyttää '∉'-merkkiä, oppiaine '≉'-merkkiä (metasuodatus.py). Geneerinen
  // teksti — kurssin oma taso/oppiaine näkyy jo rivin omissa sarakkeissa, eikä
  // koko rajauslistaa (voi olla tuhansia merkkejä) toisteta tähän.
  if (runko.includes("∉")) osat.push("Taso ei ole tutkimukseen rajattujen tasojen joukossa.");
  if (runko.includes("≉")) osat.push("Oppiaine ei ole tutkimukseen listattujen oppiaineiden listalla.");
  if (osat.length) return osat.join(" ");
  if (runko.startsWith("odottaa LLM")) return "Odottaa LLM-seulontaa.";
  return runko;
}

// Yksi perustelu-pylpyrä: lähde-merkki + värikoodi; tarkat perusteet auki
// hoverilla/fokuksella/klikkauksella. detaljiOnHtml=true => detalji valmista HTML:ää.
function perusteluPylpyra(lahde, vari, detalji, detaljiOnHtml = false) {
  const sisalto = detaljiOnHtml ? detalji : escapeHtml(detalji || "—");
  return `<span class="perustelu-pylpyra ${vari}" tabindex="0" role="button">${lahde}`
       + `<span class="perustelu-detalji">${sisalto}</span></span>`;
}

// Perustelu-solun sisältö: pohja (meta/LLM) + mahdollinen HITL-pylpyrä.
// Väri = sivun tila (vihreä mukana / punainen hylätty). Kun HITL on ohittanut,
// pohjapylpyrä on harmaa (ohitettu) ja HITL saa sivun värin.
function perusteluSolu(k) {
  const korjaukset = k.HitlKorjaukset || [];
  const korjattu = korjaukset.length > 0;
  const sivuVari = aktiivinen_tila === "mukana" ? "vihrea"
                 : aktiivinen_tila === "hylätty" ? "punainen" : "harmaa";
  const peruste = k.Luokitteluperuste || "";
  const onMeta = peruste.startsWith("meta:");
  const lahde = onMeta ? "meta" : "LLM";
  const perusteTeksti = onMeta ? metaPerusteluYstavallinen(peruste) : peruste;

  let html = perusteluPylpyra(lahde, korjattu ? "harmaa" : sivuVari, perusteTeksti);
  if (korjattu) {
    const detalji = korjaukset.map((h) => {
      const nimi = h.KayttajaNimi ? ` — ${escapeHtml(h.KayttajaNimi)}` : "";
      const tila = h.UusiTila ? "sisällytti" : "poisti";
      return `<div>${tila}: ${escapeHtml(h.Perustelu || "")}${nimi}</div>`;
    }).join("");
    html += perusteluPylpyra("HITL", sivuVari, detalji, true);
  }
  return html;
}

function renderTutkimusKurssitRivit(rivit) {
  const runko = document.getElementById("tutkimus-kurssit-rungot");
  runko.innerHTML = "";
  if (rivit.length === 0) {
    runko.innerHTML = `<tr><td colspan="6">Ei kursseja tässä kategoriassa.</td></tr>`;
    return;
  }
  let html = "";
  for (const k of rivit) {
    let perusteluHtml = perusteluSolu(k);

    // Hyväksyntä (vain mukana-välilehdellä): HITL-päätös on aina hyväksytty,
    // LLM-päätöksen voi peukuttaa. Pelkkä visuaalinen tila — Hylkää toimii yhä.
    const hitlPaatos = (k.HitlKorjaukset || []).length > 0;
    const hyvaksytty = aktiivinen_tila === "mukana" && (hitlPaatos || !!k.Hyvaksyja);
    if (aktiivinen_tila === "mukana" && !hitlPaatos) {
      perusteluHtml += k.Hyvaksyja
        ? ` <button class="nappi-pieni nappi-hyva peukku" title="Hyväksyjä: ${escapeHtml(k.Hyvaksyja)}">👍</button>`
        : ` <button class="nappi-pieni hyvaksy-nappi" data-kid="${k.KID}" data-nimi="${escapeHtml(k.KurssiNimi)}" title="Hyväksy LLM:n tekemä arvio tästä">Hyväksy</button>`;
    }

    let toimintoHtml = "";
    const lomake = `data-lomake="hitl:${aktiivinen_tutkimus.TID}:${k.KID}"`;
    if (aktiivinen_tila === "mukana") {
      toimintoHtml = `<button ${lomake} class="nappi-pieni nappi-vaara hitl-nappi${hyvaksytty ? " nappi-haalea" : ""}" data-kid="${k.KID}" data-nimi="${escapeHtml(k.KurssiNimi)}" data-perustelu="${escapeHtml(k.Luokitteluperuste || "")}" data-tila="0">Hylkää</button>`;
    } else if (aktiivinen_tila === "hylätty") {
      toimintoHtml = `<button ${lomake} class="nappi-pieni nappi-hyva hitl-nappi" data-kid="${k.KID}" data-nimi="${escapeHtml(k.KurssiNimi)}" data-perustelu="${escapeHtml(k.Luokitteluperuste || "")}" data-tila="1">Sisällytä</button>`;
    }

    html += `<tr class="kurssi-rivi${hyvaksytty ? " hyvaksytty" : ""}" data-kid="${k.KID}">
      <td>${escapeHtml(k.KurssiNimi)}</td>
      <td class="koodi">${koodiJaOpasLinkki(k)}</td>
      ${kurssiMetaSolut(k)}
      <td class="perustelu">${perusteluHtml}${toimintoHtml ? `<div class="perustelu-toiminto">${toimintoHtml}</div>` : ""}</td></tr>`;
  }
  runko.innerHTML = html;
}

// Delegoitu klikkaus (rivit renderöidään uudelleen joka pollauksella): napit ja
// pylpyrät hoitavat oman toimintonsa, muu rivin klikkaus avaa kurssin tiedot.
document.getElementById("tutkimus-kurssit-rungot").addEventListener("click", (e) => {
  const kohde = e.target.closest(".hitl-nappi, .hyvaksy-nappi, .peukku, .perustelu-pylpyra, a");
  if (kohde) {
    if (kohde.matches(".hitl-nappi")) {
      const d = kohde.dataset;
      avaaHitlModaali(parseInt(d.kid), d.nimi, d.perustelu, d.tila === "1");
    } else if (kohde.matches(".hyvaksy-nappi")) {
      hyvaksyLuokitus(kohde);
    } else if (kohde.matches(".perustelu-pylpyra")) {
      kohde.classList.toggle("auki");
    }
    return;
  }
  const rivi = e.target.closest("tr.kurssi-rivi");
  if (rivi) avaaModaali(parseInt(rivi.dataset.kid));
});

document.querySelectorAll(".tila-nappi, .tila-nappi-nav").forEach((b) => {
  b.addEventListener("click", () => navigoi(`/tutkimukset/${aktiivinen_tutkimus.Slug}/${b.dataset.alasivu}`));
});

// --- Tutkimus-arvioinnit ---

function _renderArviointiSolu(kys, v) {
  if (typeof v === "string") return escapeHtml(v || "—");
  const luokittelu = kys.Luokittelu || "vapaa_teksti";
  const perustelu = v?.vastaus ? `<em class="arvio-perustelu">${escapeHtml(v.vastaus)}</em>` : "";
  // Vanhentunut = tekoälyn vastaus on generoitu vanhaan kysymykseen/kehotteeseen
  const vanha = v?.vanhentunut
    ? `<span class="vanha-merkki" title="Tämä tekoälyn vastaus on generoitu vanhentuneeseen kysymykseen tai kehotteeseen. Aja LLM-arviointi uudelleen päivittääksesi.">⚠ vanhentunut</span>`
    : "";
  let body;
  if (luokittelu === "luokittelu" && v?.luokka) {
    body = `<span class="luokka-badge">${escapeHtml(v.luokka)}</span>${perustelu}`;
  } else if (luokittelu === "asteikko" && v?.pisteet != null) {
    const max = kys.LuokitteluMaarittely?.maksimi;
    body = `<span class="pisteet-arvo">${escapeHtml(v.pisteet)}${max ? "/" + escapeHtml(max) : ""}</span>${perustelu}`;
  } else if (luokittelu === "lista" && Array.isArray(v?.lista)) {
    const kohdat = v.lista.length
      ? `<ul class="arvio-lista">${v.lista.map((x) => `<li>${escapeHtml(x)}</li>`).join("")}</ul>`
      : '<span class="arvio-tyhja">—</span>';
    body = kohdat + perustelu;
  } else {
    body = escapeHtml(v?.vastaus || "—");
  }
  return vanha + body;
}

function _vastusOnAnnettu(v) {
  if (typeof v === "string") return !!v;
  return !!(v?.vastaus || v?.luokka || v?.pisteet != null || (Array.isArray(v?.lista) && v.lista.length));
}

let arvioinnit_data = null;
let arvioinnit_suodatin = { kkid: null, taso: null, hakusana: null };
let arvioinnit_jarjestys = { sarake: null, suunta: null };

// Virhetaksonomian juurisyyt (mallit.JUURISYYT) ihmisluettavina.
const JUURISYY_NIMI = {
  riittamaton_opas: "Riittämätön opinto-opas",
  llm_virhe: "LLM:n väärinymmärrys",
};

// Korjausikkuna kutsuu tätä tallennuksen jälkeen, jotta solu päivittyy heti.
window.paivitaArvioinnit = function () {
  if (aktiivinen_tutkimus) {
    renderTutkimusArvioinnit(aktiivinen_tutkimus.Slug, aktiivinen_tutkimus.LuokittelunNimi, true);
  }
};

// Arvioinnit ladataan osissa ja taulukko kasvaa sitä mukaa (huono yhteys: koko
// data kerralla oli ~0,5 Mt). arvioinnit_lataus = käynnissä olevan latauksen tunniste.
const ARVIOINNIT_OSA = 25;
// Hiljainen päivitys (pollaus 15 s) hakee kaiken uudelleen: isommat osat = vähemmän
// pyyntöjä (palvelin hakee tutkimuksen vastaukset jokaiselle osalle).
const ARVIOINNIT_POLLAUS_OSA = 200;
let arvioinnit_lataus = 0;
let arvioinnit_kesken = false;

async function renderTutkimusArvioinnit(slug, nimi, sailyta = false) {
  // Pollaus ei keskeytä käynnissä olevaa latausta (muuten taulu jäisi vajaaksi).
  if (sailyta && arvioinnit_kesken) return;
  const lataus = ++arvioinnit_lataus;
  document.getElementById("tutkimus-arvioinnit-otsikko").textContent = `${nimi} — arvioinnit`;
  const sisalto = document.getElementById("tutkimus-arvioinnit-sisalto");
  const suodatinEl = document.getElementById("tutkimus-arvioinnit-suodatin");

  // sailyta=true (pollaus/tallennus): lataa hiljaa, vaihda data vasta valmiina,
  // säilytä suodatinvalinta. Muuten tyhjä pöytä ja rivit näkyviin osa kerrallaan.
  if (!sailyta) {
    arvioinnit_data = null;
    arvioinnit_suodatin = { kkid: null, taso: null, hakusana: null };
    arvioinnit_jarjestys = { sarake: null, suunta: null };
    document.getElementById("tutkimus-arvioinnit-lkm").textContent = "";
    sisalto.innerHTML = '<p class="tulossa">Ladataan arviointeja…</p>';
    rakennaSuodatinPalkki(suodatinEl, arvioinnit_suodatin, renderArvioinnitTaulu);
    rekisteroiTutkimusNakymat("tutkimus-arvioinnit-otsikko", suodatinEl, arvioinnit_suodatin, renderArvioinnitTaulu);
  }
  arvioinnit_kesken = true;
  let koottu = null;
  let renderoity = 0;
  const koko = sailyta ? ARVIOINNIT_POLLAUS_OSA : ARVIOINNIT_OSA;
  try {
    for (let sivu = 0; ; sivu++) {
      const osa = await haeJson(`/api/tutkimukset/${slug}/arvioinnit?sivu=${sivu}&koko=${koko}`);
      await koulut_ladattu;
      // Uudempi lataus ohitti, tai käyttäjä siirtyi muualle (älä kuluta kaistaa piilonäkymään).
      if (lataus !== arvioinnit_lataus || jaaPolku().alasivu !== "arvioinnit") return;
      if (!osa.kysymykset.length) {
        arvioinnit_data = null;
        document.getElementById("tutkimus-arvioinnit-lkm").textContent = "";
        suodatinEl.innerHTML = "";
        document.querySelector("#s-tutkimus-arvioinnit .nakyma-nauha")?.remove();
        sisalto.innerHTML = '<p class="tulossa">Ei arviointikysymyksiä — lisää kysymyksiä tutkimukselle.</p>';
        return;
      }
      koottu = koottu ? { ...osa, kurssit: koottu.kurssit.concat(osa.kurssit) } : osa;
      const valmis = !osa.kurssit.length || koottu.kurssit.length >= osa.yhteensa;
      if (valmis) arvioinnit_kesken = false;
      // Koko taulun uudelleenrakennus joka osalla olisi O(n²): korkeintaan OSARENDER_VALI_MS välein.
      if (valmis || (!sailyta && Date.now() - renderoity > OSARENDER_VALI_MS)) {
        arvioinnit_data = koottu;
        renderArvioinnitTaulu();
        renderoity = Date.now();
      }
      if (valmis) return;
    }
  } catch (_) {
    if (lataus === arvioinnit_lataus && !sailyta) {
      document.getElementById("tutkimus-arvioinnit-lkm").textContent +=
        " — lataus keskeytyi (yhteysvirhe), päivittyy automaattisesti";
    }
  } finally {
    if (lataus === arvioinnit_lataus) arvioinnit_kesken = false;
  }
}

function _arvioinnitSuodatetut() {
  const s = arvioinnit_suodatin;
  const haku = (s.hakusana || "").toLowerCase();
  return arvioinnit_data.kurssit.filter((k) => {
    if (s.kkid && String(k.KKID) !== String(s.kkid)) return false;
    if (s.taso && (k.Taso || "") !== s.taso) return false;
    if (haku && !((k.KurssiNimi || "").toLowerCase().includes(haku)
                  || (k.Koodi || "").toLowerCase().includes(haku))) return false;
    return true;
  });
}

const ARVIOINTI_SARAKKEET = { Nimi: "nimi", Taso: "taso", op: "op" };

// Arviointitaulun delegoitu klikkaus: Korjaa / Hyväksy solun kysymykselle, muu rivin
// klikkaus avaa kurssin. Kurssi haetaan klikkaushetken datasta (pollaus vaihtaa sen).
document.getElementById("tutkimus-arvioinnit-sisalto").addEventListener("click", async (e) => {
  const rivi = e.target.closest("tr.kurssi-rivi");
  if (!rivi || e.target.closest("a, .peukku")) return;
  const kid = parseInt(rivi.dataset.kid);
  const nappi = e.target.closest("button[data-lomake], .arvio-hyvaksy-nappi");
  if (!nappi) { avaaModaali(kid); return; }
  const k = arvioinnit_data?.kurssit.find((x) => x.KID === kid);
  const i = parseInt(nappi.closest("td").dataset.i);
  const kys = arvioinnit_data?.kysymykset[i];
  if (!k || !kys) return;
  const v = k.vastaukset[i];
  if (nappi.matches("[data-lomake]")) {
    window.avaaArviointiMuokkaus?.(aktiivinen_tutkimus.TID, aktiivinen_tutkimus.Slug, kid, kys, v,
                                   k.korjaukset?.[kys.KysID] || null);
    return;
  }
  const kohde = `arvion "${k.KurssiNimi}" / "${kys.Kysymys.slice(0, 40)}"`;
  if (await lahetaHyvaksynta(nappi, `${kid}/kysymykset/${kys.KysID}`, kohde)) {
    await renderTutkimusArvioinnit(aktiivinen_tutkimus.Slug, aktiivinen_tutkimus.LuokittelunNimi, true);
  }
});

function renderArvioinnitTaulu() {
  if (!arvioinnit_data) return;  // suodatinmuutos ennen ensimmäistä osaa
  const { kysymykset } = arvioinnit_data;
  const kurssit = _arvioinnitSuodatetut();
  if (arvioinnit_jarjestys.sarake) {
    kurssit.sort(vertaaKursseja(arvioinnit_jarjestys.sarake, arvioinnit_jarjestys.suunta));
  }
  const sisalto = document.getElementById("tutkimus-arvioinnit-sisalto");
  const lkm = document.getElementById("tutkimus-arvioinnit-lkm");

  const arvioitu = kurssit.filter((k) => k.vastaukset.some(_vastusOnAnnettu)).length;
  lkm.textContent = `${arvioitu} / ${kurssit.length} kurssia arvioitu`
    + (arvioinnit_kesken ? ` — ladattu ${arvioinnit_data.kurssit.length} / ${arvioinnit_data.yhteensa}…` : "");

  if (!kurssit.length) {
    sisalto.innerHTML = '<p class="tulossa">Ei kursseja suodatuksella.</p>';
    return;
  }

  const taulu = document.createElement("table");

  const thead = taulu.createTHead();
  const otsikkorivi = thead.insertRow();
  for (const teksti of ["Nimi", "Taso", "op"]) {
    const th = document.createElement("th");
    th.textContent = teksti;
    th.dataset.jarjesta = ARVIOINTI_SARAKKEET[teksti];
    otsikkorivi.appendChild(th);
  }
  for (const k of kysymykset) {
    const th = document.createElement("th");
    th.className = "kysymys-sarake";
    const tyyppiMerkki = k.Luokittelu === "luokittelu" ? " [L]" : k.Luokittelu === "asteikko" ? " [A]" : k.Luokittelu === "lista" ? " [Li]" : "";
    th.textContent = (k.Kysymys.length > 48 ? k.Kysymys.slice(0, 45) + "…" : k.Kysymys) + tyyppiMerkki;
    th.title = k.Kysymys;
    otsikkorivi.appendChild(th);
  }
  varustaJarjestys(thead, arvioinnit_jarjestys, renderArvioinnitTaulu);

  const tid = aktiivinen_tutkimus?.TID;
  // Merkkijonona ja delegoidulla kuuntelijalla (alla): rivit × kysymykset soluja,
  // joissa kussakin oli 3–4 omaa kuuntelijaa.
  taulu.createTBody().innerHTML = kurssit.map((k) => {
    const solut = kysymykset.map((kys, i) => {
      const v = k.vastaukset[i];
      const korjaus = k.korjaukset?.[kys.KysID] || null;
      // Ihmisen korjaus näkyy tekoälyn vastauksen alla, ei sen tilalla: molemmat
      // tarvitaan virhetaksonomian arviointiin (oliko opas puutteellinen vai LLM väärässä).
      const korjausHtml = korjaus
        ? `<div class="arvio-korjaus">${_renderArviointiSolu(kys, korjaus)}` +
          `<span class="arvio-korjaaja">Korjannut ${escapeHtml(korjaus.nimi || "?")}` +
          `${korjaus.juurisyy ? " · " + escapeHtml(JUURISYY_NIMI[korjaus.juurisyy] || korjaus.juurisyy) : ""}</span></div>`
        : "";
      // Hyväksyntä: ihmisen korjaus on aina hyväksytty, LLM-vastauksen voi
      // peukuttaa. Pelkkä visuaalinen tila — Korjaa toimii yhä.
      const hyvaksytty = !!korjaus || !!v.hyvaksyja;
      let hyvaksyHtml = "";
      if (!korjaus && v.hyvaksyja) {
        hyvaksyHtml = `<button class="arvio-korjaa-nappi nappi-hyva peukku" title="Hyväksyjä: ${escapeHtml(v.hyvaksyja)}">👍</button> `;
      } else if (!korjaus && _vastusOnAnnettu(v)) {
        hyvaksyHtml = `<button class="arvio-korjaa-nappi arvio-hyvaksy-nappi" title="Hyväksy LLM:n tekemä arvio tästä">Hyväksy</button> `;
      }
      return `<td class="arviointi-vastaus${hyvaksytty ? " hyvaksytty" : ""}" data-i="${i}">` +
        `<span class="arvio-teksti">${_renderArviointiSolu(kys, v)}</span>` + korjausHtml + hyvaksyHtml +
        `<button class="arvio-korjaa-nappi${hyvaksytty ? " nappi-haalea" : ""}" data-lomake="arvio:${tid}:${k.KID}:${kys.KysID}">Korjaa</button></td>`;
    }).join("");
    return `<tr class="kurssi-rivi" data-kid="${k.KID}">
      <td>${kurssiLinkki(k)}</td>
      <td>${tasoTeksti(k.Taso)}</td>
      <td class="op">${escapeHtml(k.Opintopisteet ?? "—")}</td>${solut}</tr>`;
  }).join("");

  sisalto.innerHTML = "";
  sisalto.appendChild(taulu);
}

// --- Tutkimus-raportti ---

const RAPORTTI_OSIOT = [
  { avain: "johdanto",   otsikko: "1. Johdanto" },
  { avain: "kurssit",    otsikko: "2. Tutkittavat kurssit" },
  { avain: "arvioinnit", otsikko: "3. Arvioinnit" },
];

function _renderTilastotTaulukko(tilastot) {
  if (!tilastot?.kysymykset?.length) return "";
  const rakenteiset = tilastot.kysymykset.filter(
    (k) => k.luokittelu === "luokittelu" || k.luokittelu === "asteikko" || k.luokittelu === "lista"
  );
  if (!rakenteiset.length) return "";

  let html = '<div class="tilastot-osio"><h3>Tilastot</h3>';
  for (const k of rakenteiset) {
    html += `<div class="tilasto-kysymys"><strong>${escapeHtml(k.kysymys)}</strong> (${escapeHtml(k.yhteensa)} arviointia)`;
    if (k.luokittelu === "luokittelu") {
      const jakauma = k.jakauma || {};
      const yht = k.yhteensa || 1;
      html += '<table class="tilasto-taulu"><tr>';
      for (const luokka of Object.keys(jakauma)) {
        html += `<th>${escapeHtml(luokka)}</th>`;
      }
      html += "</tr><tr>";
      for (const lkm of Object.values(jakauma)) {
        const pct = Math.round((lkm / yht) * 100);
        html += `<td><div class="tilasto-pylvas" style="width:${pct}%"></div>${escapeHtml(lkm)} (${pct}%)</td>`;
      }
      html += "</tr></table>";
    } else if (k.luokittelu === "asteikko") {
      html += `<table class="tilasto-taulu"><tr><th>ka</th><th>min</th><th>max</th></tr>` +
        `<tr><td>${escapeHtml(k.keskiarvo ?? "—")}</td><td>${escapeHtml(k.minimi ?? "—")}</td>` +
        `<td>${escapeHtml(k.maksimi ?? "—")}</td></tr></table>`;
      const jakauma = k.jakauma || {};
      if (Object.keys(jakauma).length) {
        const yht = k.yhteensa || 1;
        const avaimet = Object.keys(jakauma).sort((a, b) => +a - +b);
        html += '<table class="tilasto-taulu"><tr>' + avaimet.map((a) => `<th>${escapeHtml(a)}</th>`).join("") + "</tr><tr>";
        html += avaimet.map((a) => {
          const lkm = jakauma[a] || 0;
          const pct = Math.round((lkm / yht) * 100);
          return `<td>${escapeHtml(lkm)} (${pct}%)</td>`;
        }).join("") + "</tr></table>";
      }
    } else if (k.luokittelu === "lista") {
      const jakauma = k.jakauma || {};
      const parit = Object.entries(jakauma).sort((a, b) => b[1] - a[1]).slice(0, 10);
      if (parit.length) {
        html += '<table class="tilasto-taulu"><tr><th>Kohta</th><th>Mainintoja</th></tr>';
        html += parit.map(([kohde, lkm]) => `<tr><td>${escapeHtml(kohde)}</td><td>${escapeHtml(lkm)}</td></tr>`).join("");
        html += "</table>";
      }
    }
    html += "</div>";
  }
  html += "</div>";
  return html;
}

// HITL-laatumittarit (CLAUDE.md vaihe 4): montako % luokittelupäätöksistä
// muutettiin käsin, ja montako % korjauksista johtui riittämättömästä
// oppaasta (data) vs. LLM:n virheestä (kehote). Auktoritatiivinen rakenteellinen
// luku — erillään LLM-generoidusta proosasta.
function _renderHitlMittarit(hitl) {
  if (!hitl || !hitl.llm_kasitelty) return "";
  const p = (x) => (x ?? 0).toFixed(1);
  const rivi = (nimi, lkm, pros) =>
    `<tr><td>${nimi}</td><td>${lkm}</td><td>${p(pros)} %</td></tr>`;
  return `
    <div class="tilastot-osio hitl-mittarit">
      <h3>Ihmistarkistuksen laatumittarit</h3>
      <p>Käsin muutettuja luokittelupäätöksiä:
        <strong>${hitl.muutettu} / ${hitl.llm_kasitelty}</strong>
        LLM-luokiteltua kurssia (<strong>${p(hitl.muutettu_pros)} %</strong>).</p>
      <table class="tilasto-taulu">
        <tr><th>Korjauksen juurisyy</th><th>Kursseja</th><th>Osuus korjauksista</th></tr>
        ${rivi("Riittämätön opinto-opas (oppaan laatu)", hitl.opas, hitl.opas_pros)}
        ${rivi("LLM:n väärinymmärrys (kehote)", hitl.llm_virhe, hitl.llm_virhe_pros)}
        ${rivi("Juurisyy merkitsemättä", hitl.tuntematon, hitl.tuntematon_pros)}
      </table>
    </div>`;
}

// Raportin tuoreuspalkki (CLIUI:n "Näytä tilanne" -vastine): milloin generoitu,
// onko lähdeaineisto muuttunut sen jälkeen (tiivistevertailu) ja montako
// HITL-korjausta/kommenttia on tehty generoinnin jälkeen.
const _TUOREUS = {
  ajan_tasalla: { merkki: "✓", teksti: "Ajan tasalla", luokka: "tuoreus-ok" },
  vanhentunut: { merkki: "⚠", teksti: "Vanhentunut — lähdeaineisto muuttunut generoinnin jälkeen", luokka: "tuoreus-vanha" },
  tuntematon: { merkki: "?", teksti: "Tuoreus tuntematon — ei vielä laskettu tai generoitu ennen tuoreusseurantaa", luokka: "tuoreus-tuntematon" },
};

function _fmtAika(iso) {
  return iso ? String(iso).replace("T", " ").slice(0, 16) : "—";
}

function _renderTuoreusPalkki(tilanne) {
  if (!tilanne || !tilanne.generoitu) return "";
  const t = _TUOREUS[tilanne.tuoreus] || _TUOREUS.tuntematon;
  const h = tilanne.hitl_jalkeen || 0, k = tilanne.arviokorjaukset_jalkeen || 0;
  const muutokset = (h || k)
    ? `<span class="tuoreus-muutokset">Generoinnin jälkeen: ${h} luokituskorjausta, ${k} arviokorjausta</span>`
    : "";
  // Tuoreus lasketaan taustalla — näytä milloin viimeksi tarkistettu, jotta
  // käyttäjä tietää tilan ajantasaisuuden (ei "juuri nyt" -takuuta).
  const tarkistettu = tilanne.tarkistettu
    ? `<span class="tuoreus-tarkistettu">Tuoreus tarkistettu ${_fmtAika(tilanne.tarkistettu)}</span>`
    : `<span class="tuoreus-tarkistettu">Tuoreutta ei ole vielä tarkistettu</span>`;
  return `<div class="tuoreus-palkki ${t.luokka}">
      <span class="tuoreus-tila">${t.merkki} ${t.teksti}</span>
      <span class="tuoreus-aika">Generoitu ${_fmtAika(tilanne.generoitu_aika)}</span>
      ${tarkistettu}
      ${muutokset}
    </div>`;
}

// Raporttiosion teksti näkymään (myös raporttimuokkaus.js tallennuksen jälkeen).
function raporttiOsioHtml(teksti) {
  return teksti ? tekstiHtml(teksti) : '<em class="tulossa">Tämä osio puuttuu raportista.</em>';
}

// sailyta=true (pollaus): vanha raportti pysyy näkyvissä haun ajan ja virheessä.
async function renderTutkimusRaportti(slug, tutkimus, sailyta = false) {
  const sisalto = document.getElementById("raportti-sisalto");
  const pdfNappi = document.getElementById("raportti-pdf-nappi");
  if (!sailyta) sisalto.innerHTML = '<p class="tulossa">Ladataan raporttia…</p>';

  let data, tilastot, tilanne;
  try {
    [data, tilastot, tilanne] = await Promise.all([
      haeJson(`/api/tutkimukset/${slug}/raportti`),
      haeJson(`/api/tutkimukset/${slug}/raportti/tilastot`).catch(() => null),
      haeJson(`/api/tutkimukset/${slug}/raportti/tilanne`).catch(() => null),
    ]);
  } catch (_) {
    if (!sailyta) sisalto.innerHTML = '<p class="tulossa">Raportin lataaminen epäonnistui.</p>';
    return;
  }
  sisalto.innerHTML = "";

  const { tid, osiot } = data;
  const onRaportti = Object.keys(osiot).length > 0;

  pdfNappi.style.display = onRaportti ? "" : "none";

  if (!onRaportti) {
    sisalto.innerHTML = '<p class="tulossa">Raporttia ei ole vielä koostettu.</p>';
    return;
  }

  pdfNappi.onclick = () => avaaRaporttiTulostus(slug, tutkimus, osiot, tilastot);
  sisalto.insertAdjacentHTML("beforeend", _renderTuoreusPalkki(tilanne));

  for (const { avain, otsikko } of RAPORTTI_OSIOT) {
    const teksti = osiot[avain] || "";
    let tilastotHtml = avain === "arvioinnit" ? _renderTilastotTaulukko(tilastot) : "";
    if (avain === "kurssit") tilastotHtml = _renderHitlMittarit(tilastot?.hitl);
    const div = document.createElement("div");
    div.className = "raportti-osio";
    div.dataset.avain = avain;
    div.innerHTML = `
      <div class="raportti-osio-otsikkorivi">
        <h2 class="raportti-osio-otsikko">${otsikko}</h2>
        <button class="arvio-korjaa-nappi raportti-muokkaa-nappi" data-avain="${avain}">Muokkaa</button>
      </div>
      ${tilastotHtml}
      <div class="raportti-osio-teksti">${raporttiOsioHtml(teksti)}</div>
      <div class="raportti-muokkaajat" id="raportti-muokkaajat-${avain}"></div>`;
    div.querySelector(".raportti-muokkaa-nappi").addEventListener("click", () => {
      window.avaaRaporttiMuokkaus?.(tid, avain, otsikko, teksti);
    });
    sisalto.appendChild(div);
  }
}

function _hitlMittaritTulostus(hitl) {
  if (!hitl || !hitl.llm_kasitelty) return "";
  const p = (x) => (x ?? 0).toFixed(1);
  const rivi = (nimi, lkm, pros) =>
    `<tr><td>${nimi}</td><td style="text-align:right">${lkm}</td>` +
    `<td style="text-align:right">${p(pros)} %</td></tr>`;
  return `<p>Käsin muutettuja luokittelupäätöksiä: <strong>${hitl.muutettu} / ` +
    `${hitl.llm_kasitelty}</strong> LLM-luokiteltua kurssia (<strong>${p(hitl.muutettu_pros)} %</strong>).</p>` +
    `<table style="border-collapse:collapse;margin:0.5rem 0"><tr>` +
    `<th style="text-align:left;padding:0.2rem 0.6rem">Korjauksen juurisyy</th>` +
    `<th style="padding:0.2rem 0.6rem">Kursseja</th>` +
    `<th style="padding:0.2rem 0.6rem">Osuus korjauksista</th></tr>` +
    rivi("Riittämätön opinto-opas (oppaan laatu)", hitl.opas, hitl.opas_pros) +
    rivi("LLM:n väärinymmärrys (kehote)", hitl.llm_virhe, hitl.llm_virhe_pros) +
    rivi("Juurisyy merkitsemättä", hitl.tuntematon, hitl.tuntematon_pros) +
    `</table>`;
}

function avaaRaporttiTulostus(slug, tutkimus, osiot, tilastot) {
  const nimi = escapeHtml(tutkimus?.LuokittelunNimi || slug);
  let html = `<!DOCTYPE html><html lang="fi"><head><meta charset="utf-8">
    <title>${nimi} — raportti</title>
    <style>
      body { font-family: Georgia, serif; max-width: 800px; margin: 2rem auto; color: #111; }
      h1 { font-size: 1.6rem; margin-bottom: 0.5rem; }
      h2 { font-size: 1.1rem; margin-top: 2rem; border-bottom: 1px solid #ccc; padding-bottom: 0.3rem; }
      p { line-height: 1.7; margin: 0.5rem 0; }
      td, th { border: 1px solid #ccc; padding: 0.2rem 0.6rem; }
    </style></head><body>
    <h1>${nimi}</h1>`;
  for (const { avain, otsikko } of RAPORTTI_OSIOT) {
    const teksti = osiot[avain] || "";
    html += `<h2>${otsikko}</h2><p>${escapeHtml(teksti).replace(/\n/g, "</p><p>")}</p>`;
    if (avain === "kurssit") html += _hitlMittaritTulostus(tilastot?.hitl);
  }
  html += `<script>window.print();<\/script></body></html>`;
  const ikkuna = window.open("", "_blank");
  if (ikkuna) {
    ikkuna.document.write(html);
    ikkuna.document.close();
  }
}

// --- Automaattinen päivitys ---

const PAIVITYSVALI_MS = 15 * 1000;

function merkitsePaivitetty() {
  const aika = new Date().toLocaleTimeString("fi-FI");
  const el = document.getElementById("paivitysaika");
  if (el) el.textContent = `Päivitetty ${aika}`;
}

// Hitaalla yhteydellä päivitys voi kestää yli välin → ei päällekkäisiä kierroksia.
let paivitys_kaynnissa = false;

async function paivitaNakyma() {
  if (document.visibilityState !== "visible" || paivitys_kaynnissa || window.lahetyksiaKesken
      || window.omaNakyma?.() === "+") return;  // "+": lista piilossa, ei päivitettävää
  paivitys_kaynnissa = true;
  try { await _paivitaNakyma(); } finally { paivitys_kaynnissa = false; }
}

async function _paivitaNakyma() {
  const r = jaaPolku();
  try {
    if (r.sivu === "tutkimukset" && r.slug && aktiivinen_tutkimus) {
      if (r.alasivu === "kurssit") {
        await renderTutkimusKurssit(r.slug, aktiivinen_tutkimus.LuokittelunNimi, true);
      } else if (r.alasivu === "arvioinnit") {
        await renderTutkimusArvioinnit(r.slug, aktiivinen_tutkimus.LuokittelunNimi, true);
      } else if (r.alasivu === "raportti") {
        await renderTutkimusRaportti(r.slug, aktiivinen_tutkimus, true);
      } else if (r.alasivu === "tiedot") {
        // tiedot-näkymä on staattinen, ei tarvitse päivittää
      }
    } else if (r.sivu === "tutkimukset") {
      await laataaTutkimukset();
    }
    merkitsePaivitetty();
  } catch (_) {
    // Verkkohäiriö — ei keskeytä silmukkaa
  }
}

setInterval(paivitaNakyma, PAIVITYSVALI_MS);

// Pidä sticky-otsikoiden offset ajan tasalla yläpalkin korkeuden mukaan
// (nav piilotetaan/tuodaan valikkovihjeellä → korkeus muuttuu).
const _ylapalkki = document.querySelector("header");
const _valikkovihje = document.getElementById("valikkovihje");
function asetaYlapalkkiKoottu(koottu) {
  _ylapalkki.classList.toggle("koottu", koottu);
  localStorage.setItem("ylapalkki_koottu", koottu ? "1" : "");
  const teksti = koottu ? "Näytä valikko" : "Piilota valikko";
  Object.assign(_valikkovihje, { textContent: koottu ? "☰" : "^", title: teksti });
  _valikkovihje.setAttribute("aria-label", teksti);
  _valikkovihje.setAttribute("aria-expanded", String(!koottu));
}
_valikkovihje.addEventListener("click", () => asetaYlapalkkiKoottu(!_ylapalkki.classList.contains("koottu")));
asetaYlapalkkiKoottu(!!localStorage.getItem("ylapalkki_koottu"));  // tila säilyy uudelleenlatauksessa
if (_ylapalkki && window.ResizeObserver) {
  new ResizeObserver(() => {
    document.documentElement.style.setProperty("--otsikkokorkeus", _ylapalkki.offsetHeight + "px");
  }).observe(_ylapalkki);
}

// --- Käynnistys ---

koulut_ladattu = lataaKorkeakoulut().catch(() => {});
renderoi();
