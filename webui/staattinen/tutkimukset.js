"use strict";

// Tutkimuslista ja tutkimuksen tiedot -näkymä.

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
