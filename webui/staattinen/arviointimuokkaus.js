"use strict";

// Lohko rajaa funktiot tiedoston sisään (vain window.* näkyy ulos). Ilman sitä
// raporttimuokkaus.js:n samannimiset globaalit (tallenna, lahetaTeksti, …) ylikirjoittavat
// nämä, ja esim. "Tallenna"-nappi kutsuu väärän tiedoston funktiota.
{

// Arviointivastauksen HITL-korjaus. Lomake rakennetaan kysymystyypin mukaan:
//   vapaa_teksti → pelkkä perustelu
//   luokittelu   → SELECT kysymyksen luokista + perustelu
//   asteikko     → number-kenttä asteikon rajoissa + perustelu
//   lista        → (+)/(x) kohtien hallinta + perustelu
// Vaihtoehdot ja rajat tulevat kysymyksen LuokitteluMaarittely-kentästä, joten
// mitään ei ole kovakoodattu tähän.
//
// Lomake on jaettu (lomakesessio.js): saman vastauksen korjausta avanneet näkevät
// samat kenttien arvot, toistensa pallurat ja tekstikursorit (data-jaettu-kentät).

let _tid = null, _kid = null, _kysid = null, _kysymys = null, _slug = null;

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
        <textarea id="arviointimuokkaus-tekstialue" rows="4" data-jaettu="perustelu"
          placeholder="Perustele korjaus..."></textarea>
      </div>
      <div class="arviointimuokkaus-juurisyy">
        <label class="arviointimuokkaus-label">Virheen juurisyy:</label>
        <label><input type="radio" name="arvio-juurisyy" value="riittamaton_opas" data-jaettu="juurisyy">
          Riittämätön opinto-opas — oikea vastaus ei ollut johdettavissa tekstistä</label>
        <label><input type="radio" name="arvio-juurisyy" value="llm_virhe" data-jaettu="juurisyy">
          LLM:n väärinymmärrys — vastaus oli johdettavissa, mutta väärä</label>
      </div>
      <div class="arviointimuokkaus-tunnistus">
        <label class="arviointimuokkaus-label" for="arvio-nimi">Nimi:</label>
        <input type="text" id="arvio-nimi" autocomplete="name" data-jaettu="nimi">
        <label class="arviointimuokkaus-label" for="arvio-sahkoposti">Sähköposti:</label>
        <input type="email" id="arvio-sahkoposti" autocomplete="email" data-jaettu="sahkoposti">
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
      <select id="arvio-luokka" data-jaettu="luokka">
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
      <label class="arviointimuokkaus-label" for="arvio-pisteet">Pisteet (${escapeHtml(minimi)}–${escapeHtml(maksimi)}):</label>
      <input type="number" id="arvio-pisteet" min="${escapeHtml(minimi)}" max="${escapeHtml(maksimi)}" step="1" data-jaettu="pisteet">
      ${pisteselitteet.length ? `<ul class="arvio-luokkaselitteet">${pisteselitteet.map((p) =>
        `<li><strong>${escapeHtml(p.arvo)}</strong>: ${escapeHtml(p.kuvaus || "")}</li>`).join("")}</ul>` : ""}`;
    if (nykyinen?.pisteet !== null && nykyinen?.pisteet !== undefined) {
      document.getElementById("arvio-pisteet").value = nykyinen.pisteet;
    }
  } else if (tyyppi() === "lista") {
    sailio.innerHTML = `
      <label class="arviointimuokkaus-label">Kohdat:</label>
      <div id="arvio-lista-kohdat" data-jaettu="lista"></div>
      <button type="button" id="arvio-lisaa-kohta" class="arvio-lista-nappi">+ Lisää kohta</button>
      <div id="arvio-lista-raja" class="arvio-lista-raja"></div>`;
    document.getElementById("arvio-lisaa-kohta").addEventListener("click", () => {
      lisaaKohta("");
      window.lomakeMuuttui?.("lista");
    });
    asetaLista(nykyinen?.lista || [], false);
  } else {
    sailio.innerHTML = "";  // vapaa teksti: perustelukenttä riittää
  }
}

// Kohdelistan jaettu arvo (lomakesessio.js): kaikki kentät, myös tyhjät (uusi rivi näkyy muillekin).
function lueLista() {
  return [...document.querySelectorAll(".arvio-lista-kentta")].map((k) => k.value);
}

function asetaLista(kohdat, fokus = false) {
  document.getElementById("arvio-lista-kohdat").innerHTML = "";
  (kohdat.length ? kohdat : [""]).forEach((k) => lisaaKohta(k, fokus));
  paivitaListaRaja();
}

function lisaaKohta(arvo, fokus = true) {
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
    window.lomakeMuuttui?.("lista");
  });
  rivi.append(kentta, poista);
  kohdat.appendChild(rivi);
  paivitaListaRaja();
  if (fokus) kentta.focus();
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

  // Jaetussa lomakkeessa nimi voi olla ensimmäisen avaajan — ei tallenneta omaksi.
  if (window.lomakeOlenAloittaja?.() ?? true) {
    localStorage.setItem("hitl_nimi", nimi);
    localStorage.setItem("hitl_sahkoposti", sahkoposti);
  }
  virhe.textContent = "";

  try {
    await lahetaNapilla(document.getElementById("arviointimuokkaus-tallenna"),
                        `/api/tutkimukset/${_slug}/kurssit/${_kid}/kysymykset/${_kysid}/korjaus`,
                        { ...runko, nimi, sahkoposti, juurisyy });
  } catch (e) {
    virhe.textContent = "Tallennus ei onnistunut: " + e.message;
    return;
  }
  window.lomakeTallennettu?.();
  suljeArviointiMuokkaus();
  window.paivitaArvioinnit?.();
}

function suljeArviointiMuokkaus() {
  window.suljeLomakesessio?.();
  _tid = null; _kid = null; _kysid = null; _kysymys = null;
  const modaali = document.getElementById("arviointimuokkaus-modaali");
  if (modaali) modaali.classList.add("piilotettu");
}

// --- Tekoälyn vastauksen esitys (vertailu, ei muokattavissa) ---

function aiYhteenveto(v) {
  if (!v) return "<em>Ei vastausta</em>";
  const osat = [];
  if (v.luokka) osat.push(`<strong>Luokka:</strong> ${escapeHtml(v.luokka)}`);
  if (v.pisteet !== null && v.pisteet !== undefined) osat.push(`<strong>Pisteet:</strong> ${escapeHtml(v.pisteet)}`);
  if (v.lista?.length) {
    osat.push(`<strong>Kohdat:</strong><ul>${v.lista.map((k) => `<li>${escapeHtml(k)}</li>`).join("")}</ul>`);
  }
  if (v.vastaus) osat.push(escapeHtml(v.vastaus));
  return osat.length ? osat.join("<br>") : "<em>Ei vastausta</em>";
}

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

  document.getElementById("arviointimuokkaus-modaali").classList.remove("piilotettu");
  document.getElementById("arviointimuokkaus-tekstialue").focus();

  // Jaettu lomake: muut saman vastauksen korjausta avanneet näkevät samat arvot.
  const modaali = document.getElementById("arviointimuokkaus-modaali");
  window.avaaLomakesessio?.(`arvio:${tid}:${kid}:${kysymys.KysID}`, modaali, {
    erikois: tyyppi() === "lista" ? { lista: { lue: lueLista, aseta: (v) => asetaLista(v || []) } } : {},
    tallennettu: () => { suljeArviointiMuokkaus(); window.paivitaArvioinnit?.(); },
  });
};
}
