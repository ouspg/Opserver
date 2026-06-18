"use strict";

// --- Reititys ---

function navigoi(polku) {
  history.pushState({}, "", polku);
  renderoi();
}

window.addEventListener("popstate", renderoi);

function jaaPolku() {
  const osat = location.pathname.replace(/^\//, "").split("/").filter(Boolean);
  if (osat[0] === "tutkimukset" && osat[1]) {
    return { sivu: "tutkimukset", slug: osat[1], alasivu: osat[2] || "tiedot" };
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
    await renderTutkimusKonteksti(r.slug, r.alasivu);
  } else {
    document.getElementById("tutkimus-nav").classList.add("piilotettu");
    if (r.sivu === "korkeakoulut") {
      document.getElementById("s-korkeakoulut").classList.add("aktiivinen");
      await lataaKorkeakoulut();
    } else if (r.sivu === "kurssit") {
      document.getElementById("s-kurssit").classList.add("aktiivinen");
      lataaKurssit();
    } else if (r.sivu === "tutkimukset") {
      document.getElementById("s-tutkimukset").classList.add("aktiivinen");
      laataaTutkimukset();
    }
  }
  merkitsePaivitetty();
}

// --- Päänav klikki ---

document.querySelectorAll("#paanav button").forEach((b) => {
  b.addEventListener("click", () => navigoi(b.dataset.polku));
});

// --- Korkeakoulut ---

async function lataaKorkeakoulut() {
  const runko = document.getElementById("korkeakoulut-rungot");
  const koulut = await fetch("/api/korkeakoulut").then((r) => r.json());
  kaikki_koulut = koulut;
  runko.innerHTML = "";
  if (koulut.length === 0) {
    runko.innerHTML = '<tr><td colspan="3">Ei korkeakouluja.</td></tr>';
    return;
  }
  for (const k of koulut) {
    const rivi = document.createElement("tr");
    rivi.innerHTML = `<td>${k.KouluNimi}</td><td>${k.OpsTyyppi}</td><td>${k.OpsOsoite}</td>`;
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

function kurssiLinkki(kurssi) {
  const url = kurssiUrl(kurssi);
  if (!url) return kurssi.KurssiNimi;
  const koulu = kaikki_koulut.find((k) => k.KKID === kurssi.KKID);
  if (!koulu) return kurssi.KurssiNimi;
  return `${kurssi.KurssiNimi} <a href="${url}" target="_blank" rel="noopener" class="ops-linkki">🌐 ${koulunLyhenne(koulu)} · ${koulu.OpsTyyppi}</a>`;
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

async function lataaKurssit() {
  const kkid = document.getElementById("suodatin-koulu").value;
  const url = kkid ? `/api/kurssit?kkid=${kkid}` : "/api/kurssit";
  kaikki_kurssit = await fetch(url).then((r) => r.json());
  renderKurssit();
}

function renderKurssit() {
  const taso = document.getElementById("suodatin-taso").value;
  const suodatettu = taso ? kaikki_kurssit.filter((k) => k.Taso === taso) : kaikki_kurssit;
  const ryhmat = ryhmitaKurssit(suodatettu);
  const runko = document.getElementById("kurssit-rungot");
  const lkm = Object.keys(ryhmat).length;
  document.getElementById("kurssit-lkm").textContent = `${lkm} kurssia`;
  runko.innerHTML = "";
  if (lkm === 0) {
    runko.innerHTML = '<tr><td colspan="6">Ei kursseja.</td></tr>';
    return;
  }
  for (const versiot of Object.values(ryhmat)) {
    const uusin = versiot[0];
    const rivi = document.createElement("tr");
    rivi.className = "kurssi-rivi";
    let vuosiSolmu;
    if (versiot.length > 1) {
      const valinnat = versiot.map((v) => `<option value="${v.KID}">${v.Opetusvuosi}</option>`).join("");
      vuosiSolmu = `<select class="vuosivalinta" onclick="event.stopPropagation()">${valinnat}</select>`;
    } else {
      vuosiSolmu = uusin.Opetusvuosi;
    }
    rivi.innerHTML = `
      <td>${kurssiLinkki(uusin)}</td>
      <td class="koodi">${uusin.Koodi || ""}</td>
      <td>${uusin.Taso ? TASO_SUOMI[uusin.Taso] || uusin.Taso : "—"}</td>
      <td>${uusin.Oppiaine || "—"}</td>
      <td class="op">${uusin.Opintopisteet ?? "—"}</td>
      <td>${vuosiSolmu}</td>`;
    rivi.querySelector("a")?.addEventListener("click", (e) => e.stopPropagation());
    rivi.addEventListener("click", () => {
      const select = rivi.querySelector(".vuosivalinta");
      const kid = select ? parseInt(select.value) : uusin.KID;
      avaaModaali(kid);
    });
    runko.appendChild(rivi);
  }
}

document.getElementById("suodatin-koulu").addEventListener("change", lataaKurssit);
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
      sisalto: (o.content?.valueFi || "").replace(/\n/g, "<br>"),
    }));
}

// Sisu: KORI-rajapinnan kentät kartoitettuna samoihin osioihin kuin Peppi
function sisuKuvausOsat(data) {
  const osat = [];
  const lisaa = (otsikko, sisalto) => {
    if (sisalto && sisalto.trim()) osat.push({ otsikko, sisalto });
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
    (data.literature || []).map((l) => l.name).filter(Boolean).map((n) => `• ${n}`).join("<br>"),
  );
  const kielet = (data.possibleAttainmentLanguages || []).map((k) => KIELI_SUOMI[k] || k).join(", ");
  lisaa("Opetuskieli", kielet);
  lisaa("Lisätiedot", _monikielinen(data.additional));
  return osat;
}

async function avaaModaali(kid) {
  const kurssi = await fetch(`/api/kurssit/${kid}`).then((r) => r.json());
  const opsUrl = kurssiUrl(kurssi);
  const nimiHtml = opsUrl
    ? `<a href="${opsUrl}" target="_blank" rel="noopener">${kurssi.KurssiNimi}</a>`
    : kurssi.KurssiNimi;
  document.getElementById("modaali-otsikko").innerHTML =
    `${nimiHtml} (${kurssi.Koodi || "—"})`;

  const koulu = kaikki_koulut.find((k) => k.KKID === kurssi.KKID);
  let kuvaus = "—";
  if (kurssi.OpsKuvaus) {
    try {
      const data = JSON.parse(kurssi.OpsKuvaus);
      const osat = koulu?.OpsTyyppi === "Sisu" ? sisuKuvausOsat(data) : peppiKuvausOsat(data);
      kuvaus = osat.length
        ? osat.map((o) => `<strong>${o.otsikko}</strong><br>${o.sisalto}`).join("<hr>")
        : "—";
    } catch {
      kuvaus = kurssi.OpsKuvaus;
    }
  }

  document.getElementById("modaali-teksti").innerHTML = `
    <table class="modaali-meta">
      <tr><th>Taso</th><td>${kurssi.Taso ? TASO_SUOMI[kurssi.Taso] || kurssi.Taso : "—"}</td></tr>
      <tr><th>Oppiaine</th><td>${kurssi.Oppiaine || "—"}</td></tr>
      <tr><th>Opintopisteet</th><td>${kurssi.Opintopisteet ?? "—"}</td></tr>
      <tr><th>Opetusvuosi</th><td>${kurssi.Opetusvuosi}</td></tr>
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
  tutkimukset_lista = await fetch("/api/tutkimukset").then((r) => r.json());
  runko.innerHTML = "";
  if (tutkimukset_lista.length === 0) {
    runko.innerHTML = '<tr><td colspan="4">Ei tutkimuksia.</td></tr>';
    return;
  }
  for (const t of tutkimukset_lista) {
    const rivi = document.createElement("tr");
    const lkm = t.MukanaLkm ?? 0;
    rivi.innerHTML = `
      <td class="kurssi-rivi tutkimus-nimi-solu">${t.LuokittelunNimi}</td>
      <td>${t.Tasorajaus || "—"}</td>
      <td class="tutkimus-oppiaine-solu" title="${t.Oppiainerajaus || ""}">${t.Oppiainerajaus || "—"}</td>
      <td class="tutkimus-toiminnot">
        <button class="nappi-pieni" data-slug="${t.Slug}" data-alasivu="kurssit">Valitut kurssit (${lkm})</button>
        <button class="nappi-pieni" data-slug="${t.Slug}" data-alasivu="arvioinnit">Arvioinnit</button>
        <button class="nappi-pieni" data-slug="${t.Slug}" data-alasivu="raportti">Raportti</button>
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
    aktiivinen_tutkimus = await fetch(`/api/tutkimukset/${slug}`).then((r) => {
      if (!r.ok) return null;
      return r.json();
    });
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

  if (alasivu === "tiedot") {
    renderTutkimusTiedot(aktiivinen_tutkimus);
    document.getElementById("s-tutkimus-tiedot").classList.add("aktiivinen");
  } else if (alasivu === "kurssit") {
    await renderTutkimusKurssit(slug, aktiivinen_tutkimus.LuokittelunNimi);
    document.getElementById("s-tutkimus-kurssit").classList.add("aktiivinen");
  } else if (alasivu === "arvioinnit") {
    await renderTutkimusArvioinnit(slug, aktiivinen_tutkimus.LuokittelunNimi);
    document.getElementById("s-tutkimus-arvioinnit").classList.add("aktiivinen");
  } else if (alasivu === "raportti") {
    await renderTutkimusRaportti(slug, aktiivinen_tutkimus);
    document.getElementById("s-tutkimus-raportti").classList.add("aktiivinen");
  }
}

function verkkosivuLinkki(url) {
  if (!url) return "—";
  return /^https?:\/\//i.test(url)
    ? `<a href="${url}" target="_blank" rel="noopener" class="ops-linkki">🌐 ${url}</a>`
    : url;
}

function renderTutkimusTiedot(t) {
  const kysymysLista = (t.Kysymykset && t.Kysymykset.length > 0)
    ? `<ol>${t.Kysymykset.map((k) => `<li>${k.Kysymys}</li>`).join("")}</ol>`
    : `<p class="tulossa">Ei arviointikysymyksiä.</p>`;
  document.getElementById("tutkimus-tiedot-sisalto").innerHTML = `
    <h2>${t.LuokittelunNimi}</h2>
    <table class="modaali-meta">
      <tr><th>Slug</th><td>${t.Slug}</td></tr>
      <tr><th>Verkkosivu</th><td>${verkkosivuLinkki(t.Verkkosivu)}</td></tr>
      <tr><th>Tasorajaus</th><td>${t.Tasorajaus || "—"}</td></tr>
      <tr><th>Oppiainerajaus</th><td>${t.Oppiainerajaus || "—"}</td></tr>
    </table>
    <h3>Valintakehote</h3>
    <pre class="kehote-teksti">${t.Luokittelukehote}</pre>
    <h3>Arviointikehote</h3>
    <pre class="kehote-teksti">${t.Arviointikehote}</pre>
    <h3>Raportointikehote</h3>
    <pre class="kehote-teksti">${t.Raportointikehote || "—"}</pre>
    <h3>Arviointikysymykset</h3>
    ${kysymysLista}`;
}

let tutkimus_luokitukset = [];
let aktiivinen_tila = "mukana";
const scroll_muistit = { mukana: 0, odottaa: 0, "hylätty": 0 };

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
    aiOsio.innerHTML = `<strong>Tekoälyn perustelu:</strong> ${ai_perustelu}`;
  } else {
    aiOsio.textContent = "";
  }
  document.getElementById("hitl-nimi").value = hitl_nimi;
  document.getElementById("hitl-sahkoposti").value = hitl_sahkoposti;
  document.getElementById("hitl-perustelu").value = "";
  document.getElementById("hitl-laheta").textContent = toiminto;
  document.getElementById("hitl-modaali").classList.remove("piilotettu");
}

document.getElementById("hitl-modaali-sulje").addEventListener("click", () => {
  document.getElementById("hitl-modaali").classList.add("piilotettu");
});
document.getElementById("hitl-modaali").addEventListener("click", (e) => {
  if (e.target === e.currentTarget)
    document.getElementById("hitl-modaali").classList.add("piilotettu");
});

document.getElementById("hitl-lomake").addEventListener("submit", async (e) => {
  e.preventDefault();
  const nimi = document.getElementById("hitl-nimi").value.trim();
  const sahkoposti = document.getElementById("hitl-sahkoposti").value.trim();
  const perustelu = document.getElementById("hitl-perustelu").value.trim();
  if (!nimi || !sahkoposti || !perustelu) return;

  hitl_nimi = nimi;
  hitl_sahkoposti = sahkoposti;
  localStorage.setItem("hitl_nimi", nimi);
  localStorage.setItem("hitl_sahkoposti", sahkoposti);

  const nappi = document.getElementById("hitl-laheta");
  const alkuperainenTeksti = nappi.textContent;
  nappi.disabled = true;
  nappi.textContent = "Tallennetaan...";

  try {
    const vastaus = await fetch(
      `/api/tutkimukset/${aktiivinen_tutkimus.Slug}/kurssit/${hitl_kid}/hitl`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ uusi_tila: hitl_uusi_tila, perustelu, nimi, sahkoposti }),
      }
    );
    if (!vastaus.ok) throw new Error("Virhe tallennuksessa");
    document.getElementById("hitl-modaali").classList.add("piilotettu");
    const toiminto = hitl_uusi_tila ? "sisällytti" : "poisti";
    const tutkimusNimi = aktiivinen_tutkimus?.LuokittelunNimi || aktiivinen_tutkimus?.Slug || "";
    window.lahetaUutinen?.(`${window.omaNimimerkki?.()} ${toiminto} kurssin "${hitl_kurssiniimi}" tutkimuksesta ${tutkimusNimi}`);
    await renderTutkimusKurssit(aktiivinen_tutkimus.Slug, aktiivinen_tutkimus.LuokittelunNimi);
  } catch (_) {
    nappi.textContent = "Virhe — yritä uudelleen";
    nappi.disabled = false;
    return;
  }
  nappi.textContent = alkuperainenTeksti;
  nappi.disabled = false;
});

async function renderTutkimusKurssit(slug, nimi) {
  document.getElementById("tutkimus-kurssit-otsikko").textContent = `${nimi} — kurssit`;
  tutkimus_luokitukset = await fetch(`/api/tutkimukset/${slug}/luokitukset`).then((r) => r.json());
  const lkmt = {
    mukana:  tutkimus_luokitukset.filter((k) => k.Mukana === true  || k.Mukana === 1).length,
    odottaa: tutkimus_luokitukset.filter((k) => k.Mukana === null).length,
    "hylätty": tutkimus_luokitukset.filter((k) => k.Mukana === false || k.Mukana === 0).length,
  };
  const nimet = { mukana: "Mukana", odottaa: "Odottaa", "hylätty": "Hylätty" };
  document.querySelectorAll(".tila-nappi").forEach((b) => {
    b.textContent = `${nimet[b.dataset.tila]} (${lkmt[b.dataset.tila] ?? 0})`;
  });
  renderTutkimusKurssitTila();
}

function renderTutkimusKurssitTila() {
  document.querySelectorAll(".tila-nappi, .tila-nappi-nav").forEach((b) => {
    b.classList.toggle("aktiivinen", b.dataset.tila === aktiivinen_tila);
  });
  const suodatettu = tutkimus_luokitukset.filter((k) => {
    if (aktiivinen_tila === "mukana")  return k.Mukana === true  || k.Mukana === 1;
    if (aktiivinen_tila === "hylätty") return k.Mukana === false || k.Mukana === 0;
    if (aktiivinen_tila === "odottaa") return k.Mukana === null;
    return true;
  });
  document.getElementById("tutkimus-kurssit-lkm").textContent = `${suodatettu.length} kurssia`;
  const runko = document.getElementById("tutkimus-kurssit-rungot");
  runko.innerHTML = "";
  if (suodatettu.length === 0) {
    runko.innerHTML = `<tr><td colspan="7">Ei kursseja tässä kategoriassa.</td></tr>`;
    return;
  }
  for (const k of suodatettu) {
    let perusteluHtml = "";
    const korjaukset = k.HitlKorjaukset || [];
    if (korjaukset.length > 0) {
      const aiTila = k.AiMukana ? "mukana" : "hylkäys";
      const aiOsa = k.Luokitteluperuste
        ? `<span class="ai-perustelu">Tekoäly (${aiTila}): ${k.Luokitteluperuste}</span>`
        : "";
      const korjausOsat = korjaukset.map((h) => {
        const tila = h.UusiTila ? "mukana" : "hylkäys";
        const nimi = h.KayttajaNimi ? ` (${h.KayttajaNimi})` : "";
        return `<span class="hitl-perustelu">Ihminen (${tila}): ${h.Perustelu}${nimi}</span>`;
      }).join("");
      perusteluHtml = aiOsa + korjausOsat;
    } else {
      perusteluHtml = k.Luokitteluperuste || "";
    }

    let toimintoHtml = "";
    if (aktiivinen_tila === "mukana") {
      toimintoHtml = `<button class="nappi-pieni nappi-vaara hitl-nappi" data-kid="${k.KID}" data-nimi="${k.KurssiNimi.replace(/"/g, "&quot;")}" data-perustelu="${(k.Luokitteluperuste || "").replace(/"/g, "&quot;")}" data-tila="0">Poista tutkimuksesta</button>`;
    } else if (aktiivinen_tila === "hylätty") {
      toimintoHtml = `<button class="nappi-pieni nappi-hyva hitl-nappi" data-kid="${k.KID}" data-nimi="${k.KurssiNimi.replace(/"/g, "&quot;")}" data-perustelu="${(k.Luokitteluperuste || "").replace(/"/g, "&quot;")}" data-tila="1">Sisällytä tutkimukseen</button>`;
    }

    const rivi = document.createElement("tr");
    rivi.className = "kurssi-rivi";
    rivi.innerHTML = `
      <td>${kurssiLinkki(k)}</td>
      <td class="koodi">${k.Koodi || ""}</td>
      <td>${k.Taso ? TASO_SUOMI[k.Taso] || k.Taso : "—"}</td>
      <td>${k.Oppiaine || "—"}</td>
      <td class="op">${k.Opintopisteet ?? "—"}</td>
      <td class="perustelu">${perusteluHtml}</td>
      <td class="toiminto">${toimintoHtml}</td>`;
    rivi.querySelector("a.ops-linkki")?.addEventListener("click", (e) => e.stopPropagation());
    rivi.addEventListener("click", () => avaaModaali(k.KID));
    runko.appendChild(rivi);
  }

  runko.querySelectorAll(".hitl-nappi").forEach((nappi) => {
    nappi.addEventListener("click", (e) => {
      e.stopPropagation();
      avaaHitlModaali(
        parseInt(nappi.dataset.kid),
        nappi.dataset.nimi,
        nappi.dataset.perustelu,
        nappi.dataset.tila === "1",
      );
    });
  });
}

function asetaTila(tila) {
  scroll_muistit[aktiivinen_tila] = window.scrollY;
  aktiivinen_tila = tila;
  renderTutkimusKurssitTila();
  window.scrollTo(0, scroll_muistit[tila]);
}

document.querySelectorAll(".tila-nappi, .tila-nappi-nav").forEach((b) => {
  b.addEventListener("click", () => asetaTila(b.dataset.tila));
});

// --- Tutkimus-arvioinnit ---

function _renderArviointiSolu(kys, v) {
  if (typeof v === "string") return v || "—";
  const luokittelu = kys.Luokittelu || "vapaa_teksti";
  const perustelu = v?.vastaus ? `<em class="arvio-perustelu">${v.vastaus}</em>` : "";
  // Vanhentunut = tekoälyn vastaus on generoitu vanhaan kysymykseen/kehotteeseen
  const vanha = v?.vanhentunut
    ? `<span class="vanha-merkki" title="Tämä tekoälyn vastaus on generoitu vanhentuneeseen kysymykseen tai kehotteeseen. Aja LLM-arviointi uudelleen päivittääksesi.">⚠ vanhentunut</span>`
    : "";
  let body;
  if (luokittelu === "luokittelu" && v?.luokka) {
    body = `<span class="luokka-badge">${v.luokka}</span>${perustelu}`;
  } else if (luokittelu === "asteikko" && v?.pisteet != null) {
    const max = kys.LuokitteluMaarittely?.maksimi;
    body = `<span class="pisteet-arvo">${v.pisteet}${max ? "/" + max : ""}</span>${perustelu}`;
  } else if (luokittelu === "lista" && Array.isArray(v?.lista)) {
    const kohdat = v.lista.length
      ? `<ul class="arvio-lista">${v.lista.map((x) => `<li>${x}</li>`).join("")}</ul>`
      : '<span class="arvio-tyhja">—</span>';
    body = kohdat + perustelu;
  } else {
    body = v?.vastaus || "—";
  }
  return vanha + body;
}

function _vastusTeksti(v) {
  return typeof v === "string" ? v : (v?.vastaus || "");
}

function _vastusOnAnnettu(v) {
  if (typeof v === "string") return !!v;
  return !!(v?.vastaus || v?.luokka || v?.pisteet != null || (Array.isArray(v?.lista) && v.lista.length));
}

async function renderTutkimusArvioinnit(slug, nimi) {
  document.getElementById("tutkimus-arvioinnit-otsikko").textContent = `${nimi} — arvioinnit`;
  const data = await fetch(`/api/tutkimukset/${slug}/arvioinnit`).then((r) => r.json());
  const { kysymykset, kurssit } = data;
  const sisalto = document.getElementById("tutkimus-arvioinnit-sisalto");
  const lkm = document.getElementById("tutkimus-arvioinnit-lkm");

  if (!kysymykset.length) {
    lkm.textContent = "";
    sisalto.innerHTML = '<p class="tulossa">Ei arviointikysymyksiä — lisää kysymyksiä tutkimukselle.</p>';
    return;
  }

  const arvioitu = kurssit.filter((k) => k.vastaukset.some(_vastusOnAnnettu)).length;
  lkm.textContent = `${arvioitu} / ${kurssit.length} kurssia arvioitu`;

  if (!kurssit.length) {
    sisalto.innerHTML = '<p class="tulossa">Ei mukaan otettuja kursseja.</p>';
    return;
  }

  const taulu = document.createElement("table");

  const thead = taulu.createTHead();
  const otsikkorivi = thead.insertRow();
  for (const teksti of ["Nimi", "Taso", "op"]) {
    const th = document.createElement("th");
    th.textContent = teksti;
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

  const tid = aktiivinen_tutkimus?.TID;
  const tbody = taulu.createTBody();
  for (const k of kurssit) {
    const rivi = tbody.insertRow();
    rivi.className = "kurssi-rivi";
    const taso = k.Taso ? (TASO_SUOMI[k.Taso] || k.Taso) : "—";
    rivi.innerHTML = `
      <td>${kurssiLinkki(k)}</td>
      <td>${taso}</td>
      <td class="op">${k.Opintopisteet ?? "—"}</td>`;
    rivi.querySelector("a.ops-linkki")?.addEventListener("click", (e) => e.stopPropagation());
    rivi.addEventListener("click", () => avaaModaali(k.KID));
    kysymykset.forEach((kys, i) => {
      const v = k.vastaukset[i];
      const vastausTeksti = _vastusTeksti(v);
      const kommentti = k.kommentit?.[kys.KysID] || "";
      const td = rivi.insertCell();
      td.className = "arviointi-vastaus";
      const korjaaId = `korjaa-${k.KID}-${kys.KysID}`;
      td.innerHTML = `<span class="arvio-teksti">${_renderArviointiSolu(kys, v)}</span>` +
        (kommentti ? `<div class="arvio-kommentti">${kommentti}</div>` : "") +
        `<button class="arvio-korjaa-nappi" id="${korjaaId}">Korjaa</button>`;
      td.querySelector(".arvio-korjaa-nappi").addEventListener("click", (e) => {
        e.stopPropagation();
        window.avaaArviointiMuokkaus?.(tid, k.KID, kys.KysID, kys.Kysymys, vastausTeksti, kommentti);
      });
    });
  }

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
    html += `<div class="tilasto-kysymys"><strong>${k.kysymys}</strong> (${k.yhteensa} arviointia)`;
    if (k.luokittelu === "luokittelu") {
      const jakauma = k.jakauma || {};
      const yht = k.yhteensa || 1;
      html += '<table class="tilasto-taulu"><tr>';
      for (const [luokka, lkm] of Object.entries(jakauma)) {
        const pct = Math.round((lkm / yht) * 100);
        html += `<th>${luokka}</th>`;
      }
      html += "</tr><tr>";
      for (const [luokka, lkm] of Object.entries(jakauma)) {
        const pct = Math.round((lkm / yht) * 100);
        html += `<td><div class="tilasto-pylvas" style="width:${pct}%"></div>${lkm} (${pct}%)</td>`;
      }
      html += "</tr></table>";
    } else if (k.luokittelu === "asteikko") {
      html += `<table class="tilasto-taulu"><tr><th>ka</th><th>min</th><th>max</th></tr>` +
        `<tr><td>${k.keskiarvo ?? "—"}</td><td>${k.minimi ?? "—"}</td><td>${k.maksimi ?? "—"}</td></tr></table>`;
      const jakauma = k.jakauma || {};
      if (Object.keys(jakauma).length) {
        const yht = k.yhteensa || 1;
        const avaimet = Object.keys(jakauma).sort((a, b) => +a - +b);
        html += '<table class="tilasto-taulu"><tr>' + avaimet.map((a) => `<th>${a}</th>`).join("") + "</tr><tr>";
        html += avaimet.map((a) => {
          const lkm = jakauma[a] || 0;
          const pct = Math.round((lkm / yht) * 100);
          return `<td>${lkm} (${pct}%)</td>`;
        }).join("") + "</tr></table>";
      }
    } else if (k.luokittelu === "lista") {
      const jakauma = k.jakauma || {};
      const parit = Object.entries(jakauma).sort((a, b) => b[1] - a[1]).slice(0, 10);
      if (parit.length) {
        html += '<table class="tilasto-taulu"><tr><th>Kohta</th><th>Mainintoja</th></tr>';
        html += parit.map(([kohde, lkm]) => `<tr><td>${kohde}</td><td>${lkm}</td></tr>`).join("");
        html += "</table>";
      }
    }
    html += "</div>";
  }
  html += "</div>";
  return html;
}

async function renderTutkimusRaportti(slug, tutkimus) {
  const sisalto = document.getElementById("raportti-sisalto");
  const pdfNappi = document.getElementById("raportti-pdf-nappi");
  sisalto.innerHTML = "";

  let data, tilastot;
  try {
    [data, tilastot] = await Promise.all([
      fetch(`/api/tutkimukset/${slug}/raportti`).then((r) => r.json()),
      fetch(`/api/tutkimukset/${slug}/raportti/tilastot`).then((r) => r.json()).catch(() => null),
    ]);
  } catch (_) {
    sisalto.innerHTML = '<p class="tulossa">Raportin lataaminen epäonnistui.</p>';
    return;
  }

  const { tid, osiot } = data;
  const onRaportti = Object.keys(osiot).length > 0;

  pdfNappi.style.display = onRaportti ? "" : "none";

  if (!onRaportti) {
    sisalto.innerHTML = '<p class="tulossa">Raporttia ei ole vielä koostettu.</p>';
    return;
  }

  pdfNappi.onclick = () => avaaRaporttiTulostus(slug, tutkimus, osiot);

  for (const { avain, otsikko } of RAPORTTI_OSIOT) {
    const teksti = osiot[avain] || "";
    const tilastotHtml = avain === "arvioinnit" ? _renderTilastotTaulukko(tilastot) : "";
    const div = document.createElement("div");
    div.className = "raportti-osio";
    div.dataset.avain = avain;
    div.innerHTML = `
      <div class="raportti-osio-otsikkorivi">
        <h2 class="raportti-osio-otsikko">${otsikko}</h2>
        <button class="arvio-korjaa-nappi raportti-muokkaa-nappi" data-avain="${avain}">Muokkaa</button>
      </div>
      ${tilastotHtml}
      <div class="raportti-osio-teksti">${teksti ? teksti.replace(/\n/g, "<br>") : '<em class="tulossa">Tämä osio puuttuu raportista.</em>'}</div>
      <div class="raportti-muokkaajat" id="raportti-muokkaajat-${avain}"></div>`;
    div.querySelector(".raportti-muokkaa-nappi").addEventListener("click", () => {
      window.avaaRaporttiMuokkaus?.(tid, avain, otsikko, teksti);
    });
    sisalto.appendChild(div);
  }
}

function avaaRaporttiTulostus(slug, tutkimus, osiot) {
  const nimi = tutkimus?.LuokittelunNimi || slug;
  let html = `<!DOCTYPE html><html lang="fi"><head><meta charset="utf-8">
    <title>${nimi} — raportti</title>
    <style>
      body { font-family: Georgia, serif; max-width: 800px; margin: 2rem auto; color: #111; }
      h1 { font-size: 1.6rem; margin-bottom: 0.5rem; }
      h2 { font-size: 1.1rem; margin-top: 2rem; border-bottom: 1px solid #ccc; padding-bottom: 0.3rem; }
      p { line-height: 1.7; margin: 0.5rem 0; }
    </style></head><body>
    <h1>${nimi}</h1>`;
  for (const { avain, otsikko } of RAPORTTI_OSIOT) {
    const teksti = osiot[avain] || "";
    html += `<h2>${otsikko}</h2><p>${teksti.replace(/\n/g, "</p><p>")}</p>`;
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

async function paivitaNakyma() {
  if (document.visibilityState !== "visible") return;
  const r = jaaPolku();
  try {
    if (r.sivu === "tutkimukset" && r.slug && aktiivinen_tutkimus) {
      if (r.alasivu === "kurssit") {
        await renderTutkimusKurssit(r.slug, aktiivinen_tutkimus.LuokittelunNimi);
      } else if (r.alasivu === "arvioinnit") {
        await renderTutkimusArvioinnit(r.slug, aktiivinen_tutkimus.LuokittelunNimi);
      } else if (r.alasivu === "raportti") {
        await renderTutkimusRaportti(r.slug, aktiivinen_tutkimus);
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

// --- Käynnistys ---

lataaKorkeakoulut();
renderoi();
