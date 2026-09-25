"use strict";

// Arviointivastauksen HITL-korjaus. Lomake rakennetaan kysymystyypin mukaan:
//   vapaa_teksti → pelkkä perustelu
//   luokittelu   → SELECT kysymyksen luokista + perustelu
//   asteikko     → number-kenttä asteikon rajoissa + perustelu
//   lista        → (+)/(x) kohtien hallinta + perustelu
// Vaihtoehdot ja rajat tulevat kysymyksen LuokitteluMaarittely-kentästä, joten
// mitään ei ole kovakoodattu tähän.
//
// Perustelu-kentässä on yhä reaaliaikainen yhteismuokkaus (muiden kursorit);
// rakenteiset kentät ovat kertaklikkauksia joissa kursorista ei ole hyötyä.

let _tid = null, _kid = null, _kysid = null, _kysymys = null, _slug = null;
let _lahetysAjastin = null;
const MUOKKAUS_LAHETYS_VALI_MS = 60;

function luoMuokkausModaali() {
  if (document.getElementById("arviointimuokkaus-modaali")) return;

  const modaali = document.createElement("div");
  modaali.id = "arviointimuokkaus-modaali";
  modaali.className = "modaali piilotettu";
  modaali.innerHTML = `
    <div class="modaali-sisalto arviointimuokkaus-sisalto">
      <button class="modaali-sulje" id="arviointimuokkaus-sulje">&#x2715;</button>
      <h2 id="arviointimuokkaus-otsikko"></h2>
      <div id="arviointimuokkaus-ai-vastaus" class="arviointimuokkaus-ai"></div>
      <div id="arviointimuokkaus-kentat"></div>
      <div class="arviointimuokkaus-kommentti-alue">
        <label class="arviointimuokkaus-label" for="arviointimuokkaus-tekstialue">Perustelu:</label>
        <div id="arviointimuokkaus-kursori-sailyo" style="position:relative;">
          <textarea id="arviointimuokkaus-tekstialue" rows="4"
            placeholder="Perustele korjaus..."></textarea>
          <canvas id="arviointimuokkaus-kursorit" style="
            position:absolute;top:0;left:0;pointer-events:none;"></canvas>
        </div>
        <div id="arviointimuokkaus-muokkaajat"></div>
      </div>
      <div class="arviointimuokkaus-juurisyy">
        <label class="arviointimuokkaus-label">Virheen juurisyy:</label>
        <label><input type="radio" name="arvio-juurisyy" value="riittamaton_opas">
          Riittämätön opinto-opas — oikea vastaus ei ollut johdettavissa tekstistä</label>
        <label><input type="radio" name="arvio-juurisyy" value="llm_virhe">
          LLM:n väärinymmärrys — vastaus oli johdettavissa, mutta väärä</label>
      </div>
      <div class="arviointimuokkaus-tunnistus">
        <label class="arviointimuokkaus-label" for="arvio-nimi">Nimi:</label>
        <input type="text" id="arvio-nimi" autocomplete="name">
        <label class="arviointimuokkaus-label" for="arvio-sahkoposti">Sähköposti:</label>
        <input type="email" id="arvio-sahkoposti" autocomplete="email">
      </div>
      <div id="arviointimuokkaus-virhe" class="arviointimuokkaus-virhe"></div>
      <div class="modaali-napit">
        <button id="arviointimuokkaus-tallenna" class="nappi-toiminto">Tallenna korjaus</button>
        <button id="arviointimuokkaus-peruuta">Peruuta</button>
      </div>
    </div>`;
  document.body.appendChild(modaali);

  document.getElementById("arviointimuokkaus-sulje").addEventListener("click", suljeArviointiMuokkaus);
  document.getElementById("arviointimuokkaus-peruuta").addEventListener("click", suljeArviointiMuokkaus);
  document.getElementById("arviointimuokkaus-tallenna").addEventListener("click", tallenna);

  modaali.addEventListener("click", (e) => {
    if (e.target === modaali) suljeArviointiMuokkaus();
  });

  const ta = document.getElementById("arviointimuokkaus-tekstialue");
  ta.addEventListener("input", () => lahetaTeksti(ta));
  ta.addEventListener("keyup", () => lahetaTeksti(ta));
  ta.addEventListener("click", () => lahetaTeksti(ta));
}

// --- Tyyppikohtaiset kentät ---

function maarittely() {
  const m = _kysymys?.LuokitteluMaarittely;
  if (!m) return {};
  return typeof m === "string" ? JSON.parse(m) : m;
}

function tyyppi() {
  return _kysymys?.Luokittelu || "vapaa_teksti";
}

function piirraKentat(nykyinen) {
  const sailio = document.getElementById("arviointimuokkaus-kentat");
  const m = maarittely();
  if (tyyppi() === "luokittelu") {
    const luokat = m.luokat || [];
    sailio.innerHTML = `
      <label class="arviointimuokkaus-label" for="arvio-luokka">Luokka:</label>
      <select id="arvio-luokka">
        <option value="">— valitse —</option>
        ${luokat.map((l) => `<option value="${escapeHtml(l.nimi)}" title="${escapeHtml(l.kuvaus || "")}">${escapeHtml(l.nimi)}</option>`).join("")}
      </select>
      ${luokat.length ? `<ul class="arvio-luokkaselitteet">${luokat.map((l) =>
        `<li><strong>${escapeHtml(l.nimi)}</strong>: ${escapeHtml(l.kuvaus || "")}</li>`).join("")}</ul>` : ""}`;
    const sel = document.getElementById("arvio-luokka");
    if (nykyinen?.luokka) sel.value = nykyinen.luokka;
  } else if (tyyppi() === "asteikko") {
    const minimi = m.minimi ?? 1, maksimi = m.maksimi ?? 5;
    const pisteselitteet = m.pisteet || [];
    sailio.innerHTML = `
      <label class="arviointimuokkaus-label" for="arvio-pisteet">Pisteet (${minimi}–${maksimi}):</label>
      <input type="number" id="arvio-pisteet" min="${minimi}" max="${maksimi}" step="1">
      ${pisteselitteet.length ? `<ul class="arvio-luokkaselitteet">${pisteselitteet.map((p) =>
        `<li><strong>${p.arvo}</strong>: ${escapeHtml(p.kuvaus || "")}</li>`).join("")}</ul>` : ""}`;
    if (nykyinen?.pisteet !== null && nykyinen?.pisteet !== undefined) {
      document.getElementById("arvio-pisteet").value = nykyinen.pisteet;
    }
  } else if (tyyppi() === "lista") {
    sailio.innerHTML = `
      <label class="arviointimuokkaus-label">Kohdat:</label>
      <div id="arvio-lista-kohdat"></div>
      <button type="button" id="arvio-lisaa-kohta" class="arvio-lista-nappi">+ Lisää kohta</button>
      <div id="arvio-lista-raja" class="arvio-lista-raja"></div>`;
    document.getElementById("arvio-lisaa-kohta").addEventListener("click", () => lisaaKohta(""));
    (nykyinen?.lista || []).forEach((k) => lisaaKohta(k));
    if (!(nykyinen?.lista || []).length) lisaaKohta("");
    paivitaListaRaja();
  } else {
    sailio.innerHTML = "";  // vapaa teksti: perustelukenttä riittää
  }
}

function lisaaKohta(arvo) {
  const kohdat = document.getElementById("arvio-lista-kohdat");
  if (!kohdat) return;
  const maks = maarittely().max_kohdat;
  if (maks && kohdat.children.length >= maks) return;
  const rivi = document.createElement("div");
  rivi.className = "arvio-lista-rivi";
  const kentta = document.createElement("input");
  kentta.type = "text";
  kentta.className = "arvio-lista-kentta";
  kentta.value = arvo || "";
  const poista = document.createElement("button");
  poista.type = "button";
  poista.className = "arvio-lista-poista";
  poista.title = "Poista kohta";
  poista.textContent = "✕";
  poista.addEventListener("click", () => {
    rivi.remove();
    paivitaListaRaja();
  });
  rivi.append(kentta, poista);
  kohdat.appendChild(rivi);
  paivitaListaRaja();
  kentta.focus();
}

function paivitaListaRaja() {
  const kohdat = document.getElementById("arvio-lista-kohdat");
  const raja = document.getElementById("arvio-lista-raja");
  const nappi = document.getElementById("arvio-lisaa-kohta");
  if (!kohdat || !raja) return;
  const maks = maarittely().max_kohdat;
  const n = kohdat.children.length;
  raja.textContent = maks ? `${n}/${maks} kohtaa` : `${n} kohtaa`;
  if (nappi) nappi.disabled = Boolean(maks && n >= maks);
}

function keraaArvot() {
  const perustelu = document.getElementById("arviointimuokkaus-tekstialue").value.trim();
  const runko = { vastaus: perustelu, luokka: null, pisteet: null, lista: null };
  if (tyyppi() === "luokittelu") {
    runko.luokka = document.getElementById("arvio-luokka").value || null;
  } else if (tyyppi() === "asteikko") {
    const arvo = document.getElementById("arvio-pisteet").value;
    runko.pisteet = arvo === "" ? null : Number(arvo);
  } else if (tyyppi() === "lista") {
    runko.lista = [...document.querySelectorAll(".arvio-lista-kentta")]
      .map((k) => k.value.trim()).filter(Boolean);
  }
  return runko;
}

function puuttuvatKentat(runko) {
  const puuttuu = [];
  if (!runko.vastaus) puuttuu.push("perustelu");
  if (tyyppi() === "luokittelu" && !runko.luokka) puuttuu.push("luokka");
  if (tyyppi() === "asteikko" && runko.pisteet === null) puuttuu.push("pisteet");
  if (tyyppi() === "lista" && !runko.lista.length) puuttuu.push("vähintään yksi kohta");
  return puuttuu;
}

// --- Tallennus ---

async function tallenna() {
  const virhe = document.getElementById("arviointimuokkaus-virhe");
  const runko = keraaArvot();
  const nimi = document.getElementById("arvio-nimi").value.trim();
  const sahkoposti = document.getElementById("arvio-sahkoposti").value.trim();
  const juurisyy = document.querySelector('input[name="arvio-juurisyy"]:checked')?.value || null;

  const puuttuu = puuttuvatKentat(runko);
  if (!nimi) puuttuu.push("nimi");
  if (!sahkoposti) puuttuu.push("sähköposti");
  if (!juurisyy) puuttuu.push("juurisyy");
  if (puuttuu.length) {
    virhe.textContent = "Täytä vielä: " + puuttuu.join(", ");
    return;
  }

  localStorage.setItem("hitl_nimi", nimi);
  localStorage.setItem("hitl_sahkoposti", sahkoposti);
  virhe.textContent = "";

  try {
    const vastaus = await fetch(
      `/api/tutkimukset/${_slug}/kurssit/${_kid}/kysymykset/${_kysid}/korjaus`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...runko, nimi, sahkoposti, juurisyy }),
      });
    if (!vastaus.ok) {
      const data = await vastaus.json().catch(() => ({}));
      virhe.textContent = "Tallennus ei onnistunut: " + (data.detail || vastaus.status);
      return;
    }
  } catch (e) {
    virhe.textContent = "Tallennus ei onnistunut: " + e.message;
    return;
  }
  suljeArviointiMuokkaus();
  window.paivitaArvioinnit?.();
}

function suljeArviointiMuokkaus() {
  if (_tid !== null) {
    window.poistuMuokkausSessiosta?.(_tid, _kid, _kysid);
  }
  _tid = null; _kid = null; _kysid = null; _kysymys = null;
  const modaali = document.getElementById("arviointimuokkaus-modaali");
  if (modaali) modaali.classList.add("piilotettu");
}

function lahetaTeksti(ta) {
  if (!_tid) return;
  clearTimeout(_lahetysAjastin);
  _lahetysAjastin = setTimeout(() => {
    window.lahetaMuokkausTeksti?.(_tid, _kid, _kysid, ta.value, ta.selectionStart);
  }, MUOKKAUS_LAHETYS_VALI_MS);
}

// --- Tekoälyn vastauksen esitys (vertailu, ei muokattavissa) ---

function aiYhteenveto(v) {
  if (!v) return "<em>Ei vastausta</em>";
  const osat = [];
  if (v.luokka) osat.push(`<strong>Luokka:</strong> ${escapeHtml(v.luokka)}`);
  if (v.pisteet !== null && v.pisteet !== undefined) osat.push(`<strong>Pisteet:</strong> ${v.pisteet}`);
  if (v.lista?.length) {
    osat.push(`<strong>Kohdat:</strong><ul>${v.lista.map((k) => `<li>${escapeHtml(k)}</li>`).join("")}</ul>`);
  }
  if (v.vastaus) osat.push(escapeHtml(v.vastaus));
  return osat.length ? osat.join("<br>") : "<em>Ei vastausta</em>";
}

// --- Yhteismuokkaus: muiden kursorit perustelukentässä ---

function kursorinPikseli(ta, sijainti) {
  const tyyli = window.getComputedStyle(ta);
  const peili = document.createElement("div");
  // Sijoita peili pois näkyvistä mutta renderöi samanlaisena kuin textarea
  peili.style.cssText = `
    position:absolute;top:-9999px;left:-9999px;visibility:hidden;
    white-space:pre-wrap;word-wrap:break-word;overflow:hidden;
    width:${ta.offsetWidth}px;
    font:${tyyli.font};
    padding:${tyyli.padding};
    border:${tyyli.border};
    box-sizing:${tyyli.boxSizing};
    line-height:${tyyli.lineHeight};
  `;
  peili.textContent = ta.value.slice(0, sijainti);
  const span = document.createElement("span");
  span.textContent = "|";
  peili.appendChild(span);
  document.body.appendChild(peili);
  const peiliRect = peili.getBoundingClientRect();
  const spanRect = span.getBoundingClientRect();
  document.body.removeChild(peili);
  return {
    x: spanRect.left - peiliRect.left,
    y: spanRect.top - peiliRect.top + ta.scrollTop,
  };
}

function piirraKursorit(muokkaajat) {
  const ta = document.getElementById("arviointimuokkaus-tekstialue");
  const canvas = document.getElementById("arviointimuokkaus-kursorit");
  if (!ta || !canvas) return;

  canvas.width = ta.offsetWidth;
  canvas.height = ta.offsetHeight;
  canvas.style.top = ta.offsetTop + "px";
  canvas.style.left = ta.offsetLeft + "px";

  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const omaId = window._omaId;
  for (const m of muokkaajat) {
    if (m.id === omaId || !m.profiili) continue;
    const pos = kursorinPikseli(ta, m.kursori || 0);
    ctx.strokeStyle = m.profiili.taustavari || "#c0392b";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(pos.x, pos.y);
    ctx.lineTo(pos.x, pos.y + 18);
    ctx.stroke();
    const offsc = document.createElement("canvas");
    offsc.width = 14; offsc.height = 14;
    window.piirraYmpyra?.(offsc, m.profiili);
    ctx.drawImage(offsc, pos.x - 7, pos.y - 14);
  }
}

function paivitaMuokkaajat(muokkaajat) {
  const div = document.getElementById("arviointimuokkaus-muokkaajat");
  if (!div) return;
  const muut = muokkaajat.filter((m) => m.id !== window._omaId);
  if (muut.length === 0) {
    div.textContent = "";
    return;
  }
  div.innerHTML = "Muokkaa nyt myös: " + muut.map((m) => {
    const offsc = document.createElement("canvas");
    offsc.width = 14; offsc.height = 14;
    offsc.className = "vieras-ympyra-pieni";
    window.piirraYmpyra?.(offsc, m.profiili);
    return `<span class="muokkaaja-rivi">${offsc.outerHTML} ${escapeHtml(m.nimimerkki || "?")}</span>`;
  }).join(", ");
}

// Kuuntelija muokkaussessio-viesteille (kutsutaan yhteistyo.js:stä)
window.muokkausKuuntelija = function (viesti) {
  if (viesti.tid !== _tid || viesti.kid !== _kid || viesti.kysid !== _kysid) return;
  const ta = document.getElementById("arviointimuokkaus-tekstialue");
  if (!ta) return;
  // Päivitä teksti vain jos muuttui (muuten kursori hyppää)
  if (ta.value !== viesti.teksti) {
    const kursori = ta.selectionStart;
    ta.value = viesti.teksti;
    ta.setSelectionRange(kursori, kursori);
  }
  piirraKursorit(viesti.muokkaajat || []);
  paivitaMuokkaajat(viesti.muokkaajat || []);
};

window.avaaArviointiMuokkaus = function (tid, slug, kid, kysymys, aiVastaus, korjaus) {
  luoMuokkausModaali();
  _tid = tid; _slug = slug; _kid = kid; _kysid = kysymys.KysID; _kysymys = kysymys;

  document.getElementById("arviointimuokkaus-otsikko").textContent = kysymys.Kysymys;
  document.getElementById("arviointimuokkaus-ai-vastaus").innerHTML =
    `<strong>Tekoälyn vastaus:</strong><br>${aiYhteenveto(aiVastaus)}`;

  // Lomake esitäytetään ihmisen aiemmalla korjauksella jos on, muuten tekoälyn
  // vastauksella — korjaaminen on harvoin tyhjältä pöydältä aloittamista.
  const pohja = korjaus || aiVastaus || {};
  piirraKentat(pohja);
  document.getElementById("arviointimuokkaus-tekstialue").value = pohja.vastaus || "";
  document.getElementById("arvio-nimi").value = localStorage.getItem("hitl_nimi") || "";
  document.getElementById("arvio-sahkoposti").value = localStorage.getItem("hitl_sahkoposti") || "";
  document.querySelectorAll('input[name="arvio-juurisyy"]').forEach((r) => {
    r.checked = Boolean(korjaus?.juurisyy) && r.value === korjaus.juurisyy;
  });
  document.getElementById("arviointimuokkaus-virhe").textContent = "";
  document.getElementById("arviointimuokkaus-muokkaajat").textContent = "";

  document.getElementById("arviointimuokkaus-modaali").classList.remove("piilotettu");
  document.getElementById("arviointimuokkaus-tekstialue").focus();

  window.liityMuokkausSessioon?.(tid, kid, kysymys.KysID);
};
