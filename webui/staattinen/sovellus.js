"use strict";

// --- Välilehtien vaihto ---

function vaihdaValilehti(nimi) {
  document.querySelectorAll("#valilehdet button").forEach((nappi) => {
    nappi.classList.toggle("aktiivinen", nappi.dataset.valilehti === nimi);
  });
  document.querySelectorAll(".nakyma").forEach((nakyma) => {
    nakyma.classList.toggle("aktiivinen", nakyma.id === nimi);
  });
  if (nimi === "kurssit") lataaKurssit();
}

document.querySelectorAll("#valilehdet button").forEach((nappi) => {
  nappi.addEventListener("click", () => vaihdaValilehti(nappi.dataset.valilehti));
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

  // Täytä myös kurssien yliopisto-suodatin
  const suodatin = document.getElementById("suodatin-koulu");
  suodatin.innerHTML = '<option value="">Kaikki yliopistot</option>';
  for (const k of koulut) {
    const vaihtoehto = document.createElement("option");
    vaihtoehto.value = k.KKID;
    vaihtoehto.textContent = k.KouluNimi;
    suodatin.appendChild(vaihtoehto);
  }
}

// --- Kurssit ---

const TASO_SUOMI = {
  yleis: "Yleisopinnot", perus: "Perusopinnot",
  aine: "Aineopinnot", "syventävä": "Syventävät",
};

let kaikki_kurssit = [];

async function lataaKurssit() {
  const kkid = document.getElementById("suodatin-koulu").value;
  const url = kkid ? `/api/kurssit?kkid=${kkid}` : "/api/kurssit";
  kaikki_kurssit = await fetch(url).then((r) => r.json());
  renderKurssit();
}

function renderKurssit() {
  const taso = document.getElementById("suodatin-taso").value;
  const suodatettu = taso ? kaikki_kurssit.filter((k) => k.Taso === taso) : kaikki_kurssit;
  const runko = document.getElementById("kurssit-rungot");
  document.getElementById("kurssit-lkm").textContent = `${suodatettu.length} kurssia`;
  runko.innerHTML = "";
  if (suodatettu.length === 0) {
    runko.innerHTML = '<tr><td colspan="6">Ei kursseja.</td></tr>';
    return;
  }
  for (const k of suodatettu) {
    const rivi = document.createElement("tr");
    rivi.className = "kurssi-rivi";
    rivi.innerHTML = `
      <td>${k.KurssiNimi}</td>
      <td class="koodi">${k.Koodi || ""}</td>
      <td>${k.Taso ? TASO_SUOMI[k.Taso] || k.Taso : "—"}</td>
      <td>${k.Oppiaine || "—"}</td>
      <td class="op">${k.Opintopisteet ?? "—"}</td>
      <td>${k.Opetusvuosi}</td>`;
    rivi.addEventListener("click", () => avaaModaali(k.KID));
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

// --- Käynnistys ---

lataaKorkeakoulut();
