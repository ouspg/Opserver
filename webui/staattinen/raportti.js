"use strict";

// Tutkimuksen raportti: osiot, tilastot, HITL-mittarit, tuoreus ja tulostus.

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
// Mittariteksti + juurisyytaulukko; näkymässä (tyyli.css) ja tulosteessa (oma <style>).
function _hitlMittaritHtml(hitl) {
  const p = (x) => (x ?? 0).toFixed(1);
  const rivi = (nimi, lkm, pros) =>
    `<tr><td>${nimi}</td><td>${lkm}</td><td>${p(pros)} %</td></tr>`;
  return `<p>Käsin muutettuja luokittelupäätöksiä:
        <strong>${hitl.muutettu} / ${hitl.llm_kasitelty}</strong>
        LLM:n luokittelemaa kurssia (<strong>${p(hitl.muutettu_pros)} %</strong>;
        nimittäjänä meta-suodatuksen läpäisseet kurssit, joille LLM antoi päätöksen).</p>
      <table class="tilasto-taulu">
        <tr><th>Korjauksen juurisyy</th><th>Kursseja</th><th>Osuus korjauksista</th></tr>
        ${rivi("Riittämätön opinto-opas (oppaan laatu)", hitl.opas, hitl.opas_pros)}
        ${rivi("LLM:n väärinymmärrys (kehote)", hitl.llm_virhe, hitl.llm_virhe_pros)}
        ${rivi("Juurisyy merkitsemättä", hitl.tuntematon, hitl.tuntematon_pros)}
      </table>`;
}

// Kurssien suppilo: meta-suodatuksen (sääntö) hylkäämät erikseen LLM:n seulomista,
// lopullinen mukana-lista HITL:n jälkeen omana rivinään.
function _suppiloHtml(s) {
  const rivi = (nimi, lkm, luokka = "") =>
    `<tr${luokka ? ` class="${luokka}"` : ""}><td>${nimi}</td><td>${escapeHtml(lkm ?? 0)}</td></tr>`;
  return `<table class="tilasto-taulu suppilo-taulu">
        <tr><th>Kurssien karsiutuminen</th><th>Kursseja</th></tr>
        ${rivi("Tutkimuksen rajauksessa (lukuvuosi + korkeakoulut)", s.kursseja)}
        ${rivi("Odottaa meta-suodatusta", s.odottaa_meta)}
        ${rivi("Meta-suodatuksen hylkäämät (taso-/oppiainerajaus)", s.meta_hylkaama, "suppilo-meta")}
        ${rivi("LLM:lle (meta-suodatuksen läpäisseet)", s.llm_lle, "suppilo-llm")}
        ${rivi("— joista odottaa LLM-seulontaa", s.odottaa_llm)}
        ${rivi("— LLM:n luokittelemat", s.llm_kasitelty)}
        ${rivi("Lopullinen mukana-lista HITL:n jälkeen", s.mukana, "suppilo-mukana")}
      </table>`;
}

function _renderHitlMittarit(tilastot) {
  const hitl = tilastot?.hitl, s = tilastot?.suppilo;
  if (!s?.kursseja && !hitl?.llm_kasitelty) return "";
  return `
    <div class="tilastot-osio hitl-mittarit">
      ${s?.kursseja ? `<h3>Kurssien suppilo</h3>${_suppiloHtml(s)}` : ""}
      ${hitl?.llm_kasitelty ? `<h3>Ihmistarkistuksen laatumittarit</h3>${_hitlMittaritHtml(hitl)}` : ""}
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
    if (avain === "kurssit") tilastotHtml = _renderHitlMittarit(tilastot);
    const div = document.createElement("div");
    div.className = "raportti-osio";
    div.dataset.avain = avain;
    div.innerHTML = `
      <div class="raportti-osio-otsikkorivi">
        <h2 class="raportti-osio-otsikko">${otsikko}</h2>
        <button class="arvio-korjaa-nappi raportti-muokkaa-nappi" data-lomake="raportti:${tid}:${avain}">Muokkaa</button>
      </div>
      ${tilastotHtml}
      <div class="raportti-osio-teksti">${raporttiOsioHtml(teksti)}</div>`;
    div.querySelector(".raportti-muokkaa-nappi").addEventListener("click", () => {
      window.avaaRaporttiMuokkaus?.(tid, slug, avain, otsikko);
    });
    sisalto.appendChild(div);
  }
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
      table { border-collapse: collapse; margin: 0.5rem 0; }
      td, th { border: 1px solid #ccc; padding: 0.2rem 0.6rem; }
      th:first-child { text-align: left; }
      td + td { text-align: right; }
    </style></head><body>
    <h1>${nimi}</h1>`;
  for (const { avain, otsikko } of RAPORTTI_OSIOT) {
    const teksti = osiot[avain] || "";
    html += `<h2>${otsikko}</h2><p>${escapeHtml(teksti).replace(/\n/g, "</p><p>")}</p>`;
    if (avain === "kurssit" && tilastot?.suppilo?.kursseja) html += _suppiloHtml(tilastot.suppilo);
    if (avain === "kurssit" && tilastot?.hitl?.llm_kasitelty) html += _hitlMittaritHtml(tilastot.hitl);
  }
  html += `<script>window.print();<\/script></body></html>`;
  const ikkuna = window.open("", "_blank");
  if (ikkuna) {
    ikkuna.document.write(html);
    ikkuna.document.close();
  }
}
