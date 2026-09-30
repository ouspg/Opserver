"use strict";

// Jaetut apurit: escapointi, vikasietoinen haku, järjestys, kurssi- ja koululinkit,
// modaalin sulkeminen sekä HITL-tunnistus ja hyväksyntä (luokitukset, arvioinnit).

// XSS-suojaus: enkoodaa arvo turvalliseksi HTML-kontekstiin (innerHTML-sinkit).
// Jaettu globaali; yhteistyo.js ja arviointimuokkaus.js käyttävät samaa.
function escapeHtml(arvo) {
  return String(arvo ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

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

const TASO_SUOMI = {
  yleis: "Yleisopinnot", perus: "Perusopinnot",
  aine: "Aineopinnot", "syventävä": "Syventävät",
};

let kaikki_koulut = [];
// Käynnistyksen korkeakoululataus: kurssirivit odottavat sitä, muuten
// opinto-opaslinkit puuttuisivat hitaalla yhteydellä seuraavaan pollaukseen asti.
let koulut_ladattu = Promise.resolve();

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
  const nimi = kurssiNimiHtml(kurssi);
  return linkki ? `${nimi} ${linkki}` : nimi;
}

// Taso suomeksi, tai raakana jos tuntematon muoto.
const tasoNimi = (taso) => TASO_SUOMI[taso] || taso;

// Taso solun tekstiksi (escapoitu); "—" jos puuttuu.
function tasoTeksti(taso) {
  return taso ? escapeHtml(tasoNimi(taso)) : "—";
}

// Kurssirivin taso-, oppiaine- ja op-solut (kurssilista ja tutkimuksen kurssit).
function kurssiMetaSolut(k) {
  return `<td>${tasoTeksti(k.Taso)}</td>
      <td>${escapeHtml(k.Oppiaine || "—")}</td>
      <td class="op">${escapeHtml(k.Opintopisteet ?? "—")}</td>`;
}

const OSARENDER_VALI_MS = 2000;

// Suodatinnäkymien (välilehdet, nakymat.js) välilehden nimi suodattimesta.
function suodatinNimi(s) {
  const koulu = kaikki_koulut.find((k) => String(k.KKID) === String(s.kkid));
  return [
    koulu && (koulunLyhenne(koulu) || koulu.KouluNimi),
    s.taso && tasoNimi(s.taso),
    s.lukuvuosi,
    s.hakusana && `"${s.hakusana}"`,
  ].filter(Boolean).join(" · ");
}

// Modaalin sulkeminen ✕-napista ja taustan klikkauksesta (myös muokkausmodaalit).
function kytkeSulkeminen(modaali, sulje) {
  modaali.querySelector(".modaali-sulje").addEventListener("click", sulje);
  modaali.addEventListener("click", (e) => { if (e.target === modaali) sulje(); });
}

// Katselumodaali (kurssin tiedot, Opserver-info): näkyviin + läsnäolo muille. Avain on
// ankkurin data-lomake (kurssin nimi, logo): muut samalla sivulla ja näkymässä näkevät
// avaajan sen kohdalla kuten HITL-napilla (sykkivä kehys, pallurat, reunakursori).
// kuvaus = mitä avaaja tekee (yläpalkin pallura muilla, esim. 'Katsoo kurssia "X"').
function naytaKatselumodaali(modaali, avain, kuvaus) {
  modaali.classList.remove("piilotettu");
  window.asetaKatselu?.(avain, kuvaus);
}

function kytkeKatselumodaali(modaali) {
  kytkeSulkeminen(modaali, () => {
    modaali.classList.add("piilotettu");
    window.asetaKatselu?.(null);
  });
}

// Lyhennetty nimi läsnäolon kuvauksiin ("Kansallinen kyberturvall…").
const lyhenna = (teksti, pituus = 30) => {
  const s = String(teksti ?? "").trim();
  return s.length > pituus ? `${s.slice(0, pituus - 1)}…` : s;
};

// Odota ehtoa (esim. osissa renderöityvää elementtiä) enintään ms; ehdon arvo tai null.
async function odotaEhtoa(ehto, ms = 15000) {
  for (const loppu = Date.now() + ms; Date.now() < loppu; await new Promise((r) => setTimeout(r, 100))) {
    const arvo = ehto();
    if (arvo) return arvo;
  }
  return null;
}

// Kurssin nimi kurssimodaalin ankkurina (kaikki kurssilistat).
const kurssiAvain = (kid) => `kurssi:${kid}`;
function kurssiNimiHtml(kurssi, kid = kurssi.KID) {
  return `<span data-lomake="${kurssiAvain(kid)}">${escapeHtml(kurssi.KurssiNimi)}</span>`;
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

let hitl_nimi = localStorage.getItem("hitl_nimi") || "";
let hitl_sahkoposti = localStorage.getItem("hitl_sahkoposti") || "";

// Korjauslomakkeen (HITL, arvion korjaus) nimi ja sähköposti muistiin seuraaviin
// lomakkeisiin ja peukutuksiin. Jaetussa lomakkeessa ne voivat olla ensimmäisen
// avaajan — silloin niitä ei tallenneta omiksi.
function muistaTunnistus(nimi, sahkoposti) {
  if (!(window.lomakeOlenAloittaja?.() ?? true)) return;
  hitl_nimi = nimi;
  hitl_sahkoposti = sahkoposti;
  localStorage.setItem("hitl_nimi", nimi);
  localStorage.setItem("hitl_sahkoposti", sahkoposti);
}

// Uutispalkin tutkimusnimi.
const tutkimusNimi = () => aktiivinen_tutkimus?.LuokittelunNimi || aktiivinen_tutkimus?.Slug || "";

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
  window.lahetaUutinen?.(`${nimi} hyväksyi ${kohde} tutkimuksessa ${tutkimusNimi()}`);
  return true;
}
