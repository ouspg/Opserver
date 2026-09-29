"use strict";

// Reititys, tutkimuskonteksti (alinav), automaattinen päivitys, yläpalkki ja käynnistys.
// Ladataan näkymätiedostojen jälkeen: käynnistys kutsuu niiden funktioita.

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

document.querySelectorAll("#paanav button").forEach((b) => {
  b.addEventListener("click", () => navigoi(b.dataset.polku));
});

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

koulut_ladattu = lataaKorkeakoulut().catch(() => {});
renderoi();
