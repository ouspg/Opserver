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
      <td>${uusin.KurssiNimi}</td>
      <td class="koodi">${uusin.Koodi || ""}</td>
      <td>${uusin.Taso ? TASO_SUOMI[uusin.Taso] || uusin.Taso : "—"}</td>
      <td>${uusin.Oppiaine || "—"}</td>
      <td class="op">${uusin.Opintopisteet ?? "—"}</td>
      <td>${vuosiSolmu}</td>`;
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

async function avaaModaali(kid) {
  const kurssi = await fetch(`/api/kurssit/${kid}`).then((r) => r.json());
  document.getElementById("modaali-otsikko").textContent =
    `${kurssi.KurssiNimi} (${kurssi.Koodi || "—"})`;

  let kuvaus = "—";
  if (kurssi.OpsKuvaus) {
    try {
      const data = JSON.parse(kurssi.OpsKuvaus);
      const osat = (data.contentList || [])
        .filter((o) => (o.content?.valueFi || "").trim())
        .map((o) => `<strong>${o.title?.valueFi || ""}</strong><br>${(o.content?.valueFi || "").replace(/\n/g, "<br>")}`);
      kuvaus = osat.length ? osat.join("<hr>") : "—";
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
      <td>${t.Oppiainerajaus || "—"}</td>
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

  nav.querySelectorAll("button").forEach((b) => {
    b.classList.toggle("aktiivinen", b.dataset.tutkimusAlasivu === alasivu);
  });
  nav.querySelectorAll("button[data-tutkimus-alasivu]").forEach((b) => {
    b.onclick = () => navigoi(`/tutkimukset/${slug}/${b.dataset.tutkimusAlasivu}`);
  });

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
    document.getElementById("s-tutkimus-raportti").classList.add("aktiivinen");
  }
}

function renderTutkimusTiedot(t) {
  document.getElementById("tutkimus-tiedot-sisalto").innerHTML = `
    <h2>${t.LuokittelunNimi}</h2>
    <table class="modaali-meta">
      <tr><th>Slug</th><td>${t.Slug}</td></tr>
      <tr><th>Tasorajaus</th><td>${t.Tasorajaus || "—"}</td></tr>
      <tr><th>Oppiainerajaus</th><td>${t.Oppiainerajaus || "—"}</td></tr>
    </table>
    <h3>Valintakehote</h3>
    <pre class="kehote-teksti">${t.Luokittelukehote}</pre>
    <h3>Arviointikehote</h3>
    <pre class="kehote-teksti">${t.Arviointikehote}</pre>`;
}

let tutkimus_luokitukset = [];
let aktiivinen_tila = "mukana";

async function renderTutkimusKurssit(slug, nimi) {
  document.getElementById("tutkimus-kurssit-otsikko").textContent = `${nimi} — kurssit`;
  tutkimus_luokitukset = await fetch(`/api/tutkimukset/${slug}/luokitukset`).then((r) => r.json());
  renderTutkimusKurssitTila();
}

function renderTutkimusKurssitTila() {
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
    runko.innerHTML = `<tr><td colspan="6">Ei kursseja tässä kategoriassa.</td></tr>`;
    return;
  }
  for (const k of suodatettu) {
    const rivi = document.createElement("tr");
    rivi.innerHTML = `
      <td>${k.KurssiNimi}</td>
      <td class="koodi">${k.Koodi || ""}</td>
      <td>${k.Taso ? TASO_SUOMI[k.Taso] || k.Taso : "—"}</td>
      <td>${k.Oppiaine || "—"}</td>
      <td class="op">${k.Opintopisteet ?? "—"}</td>
      <td class="perustelu">${k.Luokitteluperuste || ""}</td>`;
    runko.appendChild(rivi);
  }
}

document.querySelectorAll(".tila-nappi").forEach((b) => {
  b.addEventListener("click", () => {
    document.querySelectorAll(".tila-nappi").forEach((x) => x.classList.remove("aktiivinen"));
    b.classList.add("aktiivinen");
    aktiivinen_tila = b.dataset.tila;
    renderTutkimusKurssitTila();
  });
});

// --- Tutkimus-arvioinnit ---

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

  const arvioitu = kurssit.filter((k) => k.vastaukset.some((v) => v)).length;
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
    th.textContent = k.Kysymys.length > 50 ? k.Kysymys.slice(0, 47) + "…" : k.Kysymys;
    th.title = k.Kysymys;
    otsikkorivi.appendChild(th);
  }

  const tbody = taulu.createTBody();
  for (const k of kurssit) {
    const rivi = tbody.insertRow();
    const taso = k.Taso ? (TASO_SUOMI[k.Taso] || k.Taso) : "—";
    rivi.innerHTML = `
      <td>${k.KurssiNimi}</td>
      <td>${taso}</td>
      <td class="op">${k.Opintopisteet ?? "—"}</td>`;
    for (const vastaus of k.vastaukset) {
      const td = rivi.insertCell();
      td.className = "arviointi-vastaus";
      td.textContent = vastaus || "—";
    }
  }

  sisalto.innerHTML = "";
  sisalto.appendChild(taulu);
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
