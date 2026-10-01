"use strict";

// Reititys, tutkimuskonteksti (alinav), automaattinen päivitys, yläpalkki ja käynnistys.
// Ladataan näkymätiedostojen jälkeen: käynnistys kutsuu niiden funktioita.

function navigoi(polku) {
  history.pushState({}, "", polku);
  return renderoi();
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
  window.lahetaTilaNyt?.();  // sivu ja tekeminen muille heti, ei vasta sydänlyönnillä
}

// --- Yhteistyö: oma tekeminen ja siirtyminen toisen käyttäjän luo (yhteistyo.js) ---

const SIVU_NIMI = { korkeakoulut: "Korkeakoulut", kurssit: "Kurssit", tutkimukset: "Tutkimukset" };
const TILA_KUVAUS = { mukana: "valittuja", odottaa: "odottavia", "hylätty": "hylättyjä" };

// Mitä käyttäjä tekee, kun modaalia ei ole auki (yläpalkin pallurassa muilla).
window.omaSivuKuvaus = () => {
  const r = jaaPolku();
  if (!r.slug) return `Katsoo ${SIVU_NIMI[r.sivu] || r.sivu}-sivua`;
  const nimi = aktiivinen_tutkimus?.Slug === r.slug ? aktiivinen_tutkimus.LuokittelunNimi : r.slug;
  const tutkimuksessa = `tutkimuksessa "${lyhenna(nimi)}"`;
  if (r.alasivu === "kurssit") return `Katsoo ${TILA_KUVAUS[r.tila] || "valittuja"} kursseja ${tutkimuksessa}`;
  if (r.alasivu === "arvioinnit") return `Katsoo arviointeja ${tutkimuksessa}`;
  if (r.alasivu === "raportti") return `Katsoo raporttia ${tutkimuksessa}`;
  return `Katsoo tutkimusta "${lyhenna(nimi)}"`;
};

// Yläpalkin pallurasta toisen käyttäjän luo: sivu → suodatinnäkymä → sivutussivu → hänen
// avoin modaalinsa (sen data-lomake-ankkurin klikkaus: HITL/Korjaa/Muokkaa-nappi, kurssin
// nimi, logo — sama polku kuin itse avatessa, myös jaettuun lomakkeeseen liittyminen)
// tai vieritys hänen hiirensä kohdalle.
window.siirryKayttajanLuo = async (k) => {
  if (k.sivu && k.sivu !== location.pathname) await navigoi(k.sivu);
  if ((k.nakyma ?? null) !== (window.omaNakyma?.() ?? null)) await valitseNakyma(k.nakyma ?? null);
  if (k.sivunumero != null && (window.omaSivunumero?.() ?? null) !== k.sivunumero) await vaihdaSivu(k.sivunumero);
  const avain = k.lomake || k.katselu;
  if (avain && avain === window.omaModaali?.()) {
    // Sama modaali jo auki: vieritä oma modaali hänen kohdalleen (reunapallura).
    const modaali = document.querySelector(".modaali:not(.piilotettu)");
    const sisalto = modaali?.querySelector(".modaali-sisalto");
    if (sisalto && k.sijainti?.modaali) {
      modaali.scrollBy(0, sisalto.getBoundingClientRect().top + k.sijainti.y - innerHeight / 2);
    }
  } else if (avain) {
    const ankkuri = await odotaEhtoa(() => document.querySelector(`[data-lomake="${CSS.escape(avain)}"]`));
    ankkuri?.scrollIntoView({ block: "center" });
    ankkuri?.click();
  } else if (k.sijainti && !k.sijainti.ylapalkki) {  // yläpalkissa: ei vieritettävää
    const { x, y } = k.sijainti;  // sivun koordinaatit; odota että sisältö on niin pitkä
    await odotaEhtoa(() => document.documentElement.scrollHeight >= y, 5000);
    window.scrollTo(x - innerWidth / 2, y - innerHeight / 2);
  }
};

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
  const ohjaimet = new ResizeObserver((havainnot) => {
    for (const h of havainnot) h.target.parentElement.style.setProperty("--ohjainkorkeus", h.target.offsetHeight + "px");
  });
  document.querySelectorAll(".kiinnitetyt").forEach((el) => ohjaimet.observe(el));
}

koulut_ladattu = lataaKorkeakoulut().catch(() => {});
renderoi();
