"use strict";

// Tutkimuksen kurssit (luokitukset): tilavälilehdet, sivutus, perustelut ja HITL-korjaus.

let tutkimus_luokitukset = [];
let aktiivinen_tila = "mukana";

let hitl_kid = null;
let hitl_uusi_tila = null;
let hitl_kurssiniimi = "";

// Luokitusten hiljainen päivitys (tallennuksen jälkeen): suodatin ja sivu säilyvät.
function paivitaTutkimusKurssit() {
  return renderTutkimusKurssit(aktiivinen_tutkimus.Slug, aktiivinen_tutkimus.LuokittelunNimi, true);
}

function avaaHitlModaali(kid, kurssiniimi, ai_perustelu, uusi_tila) {
  hitl_kid = kid;
  hitl_uusi_tila = uusi_tila;
  hitl_kurssiniimi = kurssiniimi;
  const toiminto = uusi_tila ? "Sisällytä tutkimukseen" : "Poista tutkimuksesta";
  document.getElementById("hitl-otsikko").textContent = `${toiminto}: ${kurssiniimi}`;
  const aiOsio = document.getElementById("hitl-ai-perustelu-osio");
  if (ai_perustelu) {
    aiOsio.innerHTML = `<strong>Tekoälyn perustelu:</strong> ${escapeHtml(ai_perustelu)}`;
  } else {
    aiOsio.textContent = "";
  }
  document.getElementById("hitl-nimi").value = hitl_nimi;
  document.getElementById("hitl-sahkoposti").value = hitl_sahkoposti;
  document.getElementById("hitl-perustelu").value = "";
  document.querySelectorAll('input[name="hitl-juurisyy"]').forEach((r) => (r.checked = false));
  document.getElementById("hitl-laheta").textContent = toiminto;
  const modaali = document.getElementById("hitl-modaali");
  modaali.classList.remove("piilotettu");
  // Jaettu lomake: muut saman kurssin päätöstä korjaavat näkevät samat arvot ja toisensa.
  window.avaaLomakesessio?.(`hitl:${aktiivinen_tutkimus.TID}:${kid}`, modaali, {
    tallennettu: () => {
      suljeHitlModaali();
      paivitaTutkimusKurssit();
    },
  });
}

function suljeHitlModaali() {
  window.suljeLomakesessio?.();
  document.getElementById("hitl-modaali").classList.add("piilotettu");
}

kytkeSulkeminen(document.getElementById("hitl-modaali"), suljeHitlModaali);

document.getElementById("hitl-lomake").addEventListener("submit", async (e) => {
  e.preventDefault();
  const nimi = document.getElementById("hitl-nimi").value.trim();
  const sahkoposti = document.getElementById("hitl-sahkoposti").value.trim();
  const perustelu = document.getElementById("hitl-perustelu").value.trim();
  const juurisyy = document.querySelector('input[name="hitl-juurisyy"]:checked')?.value || null;
  if (!nimi || !sahkoposti || !perustelu || !juurisyy) return;

  muistaTunnistus(nimi, sahkoposti);

  const nappi = document.getElementById("hitl-laheta");
  try {
    await lahetaNapilla(nappi, `/api/tutkimukset/${aktiivinen_tutkimus.Slug}/kurssit/${hitl_kid}/hitl`,
                        { uusi_tila: hitl_uusi_tila, perustelu, nimi, sahkoposti, juurisyy });
  } catch (e) {
    nappi.textContent = `Virhe: ${e.message} — yritä uudelleen`;
    return;
  }
  window.lomakeTallennettu?.();
  suljeHitlModaali();
  const toiminto = hitl_uusi_tila ? "sisällytti" : "poisti";
  window.lahetaUutinen?.(`${window.omaNimimerkki?.()} ${toiminto} kurssin "${hitl_kurssiniimi}" tutkimuksesta ${tutkimusNimi()}`);
  await paivitaTutkimusKurssit();
});

async function hyvaksyLuokitus(nappi) {
  if (await lahetaHyvaksynta(nappi, nappi.dataset.kid, `kurssin "${nappi.dataset.nimi}"`)) {
    await paivitaTutkimusKurssit();
  }
}

const TUTKIMUS_KURSSIT_KOKO = 100;
let tutkimus_maarat = { mukana: 0, odottaa: 0, "hylätty": 0 };
let tutkimus_sivu = 0;

let luokitus_suodatin = tyhjaSuodatin();
let luokitus_jarjestys = { sarake: null, suunta: null };

async function renderTutkimusKurssit(slug, nimi, sailyta = false) {
  document.getElementById("tutkimus-kurssit-otsikko").textContent = `${nimi} — kurssit`;
  // Pollaus / annotoinnin jälkeinen päivitys (sailyta=true) päivittää vain datan
  // — ei nollaa käyttäjän suodatinvalintaa eikä sivua eikä rakenna palkkia uusiksi.
  if (!sailyta) {
    luokitus_suodatin = tyhjaSuodatin();
    luokitus_jarjestys = { sarake: null, suunta: null };
    const palkki = document.getElementById("tutkimus-kurssit-suodatin");
    const onChange = () => {
      tutkimus_sivu = 0;
      window.lahetaTilaNyt?.();
      naytaLuokitusLataus();
      return lataaTilaSivu(true);
    };
    // Ei awaitia: palkin data (korkeakoulut, tasot) ei saa viivästää kurssilistaa.
    rakennaSuodatinPalkki(palkki, luokitus_suodatin, onChange);
    rekisteroiTutkimusNakymat("tutkimus-kurssit-otsikko", palkki, luokitus_suodatin, onChange);
    tutkimus_sivu = 0;
    naytaLuokitusLataus();
  }
  await lataaTilaSivu(true);
}

// Käyttäjän vaihto (tila/sivu/suodatin/järjestys): vanha lista pois heti ja latausrivi
// tilalle — muuten edellinen näkymä jää näkyviin kuin mitään ei tapahtuisi.
function naytaLuokitusLataus() {
  document.getElementById("tutkimus-kurssit-rungot").innerHTML =
    '<tr class="lataus-rivi"><td colspan="6">Ladataan kursseja…</td></tr>';
  document.getElementById("tutkimus-kurssit-lkm").textContent = "Ladataan…";
}

let _luokitusLataus = 0;

// Hae aktiivisen välilehden nykyinen sivu (ja maaratKanssa: suodatetut tilamäärät
// rinnakkain) palvelimelta ja renderöi. Vain uusin lataus renderöidään: hitaalla
// yhteydellä edellisen tilan/sivun myöhästynyt vastaus ei saa korvata uutta.
async function lataaTilaSivu(maaratKanssa = false) {
  const lataus = ++_luokitusLataus;
  document.querySelectorAll(".tila-nappi, .tila-nappi-nav").forEach((b) => {
    b.classList.toggle("aktiivinen", b.dataset.tila === aktiivinen_tila);
  });
  varustaJarjestys(
    document.querySelector("#s-tutkimus-kurssit thead"),
    luokitus_jarjestys,
    () => vaihdaSivu(0),
  );
  const slug = aktiivinen_tutkimus.Slug;
  const p = _suodatinParams(luokitus_suodatin);
  const j = luokitus_jarjestys.sarake
    ? `&jarjesta=${luokitus_jarjestys.sarake}&suunta=${luokitus_jarjestys.suunta}` : "";
  const url = `/api/tutkimukset/${slug}/luokitukset?tila=${encodeURIComponent(aktiivinen_tila)}`
    + `&sivu=${tutkimus_sivu}&koko=${TUTKIMUS_KURSSIT_KOKO}` + (p ? `&${p}` : "") + j;
  const [rivit, maarat] = await Promise.all([
    haeJson(url),
    maaratKanssa ? haeJson(`/api/tutkimukset/${slug}/luokitukset/maarat?${p}`) : null,
    koulut_ladattu,
  ]);
  if (lataus !== _luokitusLataus) return;
  if (maarat) {
    tutkimus_maarat = maarat;
    const nimet = { mukana: "Mukana", odottaa: "Odottaa", "hylätty": "Hylätty" };
    document.querySelectorAll(".tila-nappi").forEach((b) => {
      b.textContent = `${nimet[b.dataset.tila]} (${tutkimus_maarat[b.dataset.tila] ?? 0})`;
    });
  }
  tutkimus_luokitukset = rivit;
  renderTutkimusKurssitRivit(tutkimus_luokitukset);
  renderTutkimusKurssitSivutus();
}

function vaihdaSivu(sivu) {
  tutkimus_sivu = sivu;
  window.lahetaTilaNyt?.();
  naytaLuokitusLataus();
  window.scrollTo(0, 0);
  lataaTilaSivu();
}

// Läsnäolotieto (yhteistyo.js): sivutussivu, jotta muut näkevät palluran sivunumeron kohdalla.
window.omaSivunumero = () => (jaaPolku().alasivu === "kurssit" ? tutkimus_sivu : null);

let _sivutusMuut = [];

// Sivutus ylä- ja alalaitaan: Edellinen, sivunumerot, Seuraava. Samassa näkymässä
// eri sivulla olevat muut käyttäjät näkyvät pallurana oman sivunumeronsa kohdalla.
function renderTutkimusKurssitSivutus() {
  const kpl = tutkimus_maarat[aktiivinen_tila] ?? 0;
  document.getElementById("tutkimus-kurssit-lkm").textContent = `${kpl} kurssia`;
  const sivuja = Math.ceil(kpl / TUTKIMUS_KURSSIT_KOKO);
  const omaNakyma = window.omaNakyma?.() ?? null;
  const muut = _sivutusMuut.filter((k) => k.profiili && k.sivu === location.pathname
    && (k.nakyma ?? null) === omaNakyma && k.sivunumero != null && k.sivunumero !== tutkimus_sivu);
  // Ensimmäinen, viimeinen, nykyinen ±2 ja sivut, joilla on muita käyttäjiä; välit "…".
  const naytettavat = [...new Set([0, sivuja - 1, ...muut.map((k) => k.sivunumero),
    ...[-2, -1, 0, 1, 2].map((d) => tutkimus_sivu + d)])]
    .filter((i) => i >= 0 && i < sivuja).sort((a, b) => a - b);
  document.querySelectorAll(".tutkimus-kurssit-sivutus").forEach((el) => {
    el.innerHTML = "";
    if (sivuja <= 1) return;
    const nappi = (teksti, sivu, luokka = "") => {
      const b = document.createElement("button");
      b.textContent = teksti;
      b.className = luokka;
      b.disabled = sivu < 0 || sivu >= sivuja || sivu === tutkimus_sivu;
      b.addEventListener("click", () => vaihdaSivu(sivu));
      el.appendChild(b);
      return b;
    };
    nappi("← Edellinen", tutkimus_sivu - 1);
    let edellinen = -1;
    for (const i of naytettavat) {
      if (i > edellinen + 1) el.insertAdjacentHTML("beforeend", '<span class="sivu-vali">…</span>');
      const b = nappi(String(i + 1), i, i === tutkimus_sivu ? "sivu-numero aktiivinen" : "sivu-numero");
      for (const k of muut) if (k.sivunumero === i) b.appendChild(window.luoPikkupallura(k));
      edellinen = i;
    }
    nappi("Seuraava →", tutkimus_sivu + 1);
  });
}

// Kutsutaan jokaisella kursoriliikkeellä → renderöi vain kun sivutuspallurat muuttuvat.
let _sivutusAvain = "";
window.paivitaSivutusPallurat = (muut) => {
  _sivutusMuut = muut;
  const avain = JSON.stringify(muut.map((k) => [k.id, k.sivu, k.nakyma, k.sivunumero, k.taso, k.nimimerkki, k.profiili]));
  if (avain === _sivutusAvain) return;
  _sivutusAvain = avain;
  if (jaaPolku().alasivu === "kurssit") renderTutkimusKurssitSivutus();
};

// Meta-perustelun (metasuodatus.py) ystävällinen esitys: säilytä kurssin oma
// taso/oppiaine, mutta pudota koko rajauslista (voi olla satoja alkioita).
function metaPerusteluYstavallinen(teksti) {
  const runko = String(teksti || "").replace(/^meta:\s*/, "");
  const osat = [];
  // taso käyttää '∉'-merkkiä, oppiaine '≉'-merkkiä (metasuodatus.py). Geneerinen
  // teksti — kurssin oma taso/oppiaine näkyy jo rivin omissa sarakkeissa, eikä
  // koko rajauslistaa (voi olla tuhansia merkkejä) toisteta tähän.
  if (runko.includes("∉")) osat.push("Taso ei ole tutkimukseen rajattujen tasojen joukossa.");
  if (runko.includes("≉")) osat.push("Oppiaine ei ole tutkimukseen listattujen oppiaineiden listalla.");
  if (osat.length) return osat.join(" ");
  if (runko.startsWith("odottaa LLM")) return "Odottaa LLM-seulontaa.";
  return runko;
}

// Yksi perustelu-pylpyrä: lähde-merkki + värikoodi; tarkat perusteet auki
// hoverilla/fokuksella/klikkauksella. detaljiOnHtml=true => detalji valmista HTML:ää.
function perusteluPylpyra(lahde, vari, detalji, detaljiOnHtml = false) {
  const sisalto = detaljiOnHtml ? detalji : escapeHtml(detalji || "—");
  return `<span class="perustelu-pylpyra ${vari}" tabindex="0" role="button">${lahde}`
       + `<span class="perustelu-detalji">${sisalto}</span></span>`;
}

// Perustelu-solun sisältö: pohja (meta/LLM) + mahdollinen HITL-pylpyrä.
// Väri = sivun tila (vihreä mukana / punainen hylätty). Kun HITL on ohittanut,
// pohjapylpyrä on harmaa (ohitettu) ja HITL saa sivun värin.
function perusteluSolu(k) {
  const korjaukset = k.HitlKorjaukset || [];
  const korjattu = korjaukset.length > 0;
  const sivuVari = aktiivinen_tila === "mukana" ? "vihrea"
                 : aktiivinen_tila === "hylätty" ? "punainen" : "harmaa";
  const peruste = k.Luokitteluperuste || "";
  const onMeta = peruste.startsWith("meta:");
  const lahde = onMeta ? "meta" : "LLM";
  const perusteTeksti = onMeta ? metaPerusteluYstavallinen(peruste) : peruste;

  let html = perusteluPylpyra(lahde, korjattu ? "harmaa" : sivuVari, perusteTeksti);
  if (korjattu) {
    const detalji = korjaukset.map((h) => {
      const nimi = h.KayttajaNimi ? ` — ${escapeHtml(h.KayttajaNimi)}` : "";
      const tila = h.UusiTila ? "sisällytti" : "poisti";
      return `<div>${tila}: ${escapeHtml(h.Perustelu || "")}${nimi}</div>`;
    }).join("");
    html += perusteluPylpyra("HITL", sivuVari, detalji, true);
  }
  return html;
}

function renderTutkimusKurssitRivit(rivit) {
  const runko = document.getElementById("tutkimus-kurssit-rungot");
  runko.innerHTML = "";
  if (rivit.length === 0) {
    runko.innerHTML = `<tr><td colspan="6">Ei kursseja tässä kategoriassa.</td></tr>`;
    return;
  }
  let html = "";
  for (const k of rivit) {
    let perusteluHtml = perusteluSolu(k);

    // Hyväksyntä (vain mukana-välilehdellä): HITL-päätös on aina hyväksytty,
    // LLM-päätöksen voi peukuttaa. Pelkkä visuaalinen tila — Hylkää toimii yhä.
    const hitlPaatos = (k.HitlKorjaukset || []).length > 0;
    const hyvaksytty = aktiivinen_tila === "mukana" && (hitlPaatos || !!k.Hyvaksyja);
    if (aktiivinen_tila === "mukana" && !hitlPaatos) {
      perusteluHtml += k.Hyvaksyja
        ? ` <button class="nappi-pieni nappi-hyva peukku" title="Hyväksyjä: ${escapeHtml(k.Hyvaksyja)}">👍</button>`
        : ` <button class="nappi-pieni hyvaksy-nappi" data-kid="${k.KID}" data-nimi="${escapeHtml(k.KurssiNimi)}" title="Hyväksy LLM:n tekemä arvio tästä">Hyväksy</button>`;
    }

    let toimintoHtml = "";
    const lomake = `data-lomake="hitl:${aktiivinen_tutkimus.TID}:${k.KID}"`;
    if (aktiivinen_tila === "mukana") {
      toimintoHtml = `<button ${lomake} class="nappi-pieni nappi-vaara hitl-nappi${hyvaksytty ? " nappi-haalea" : ""}" data-kid="${k.KID}" data-nimi="${escapeHtml(k.KurssiNimi)}" data-perustelu="${escapeHtml(k.Luokitteluperuste || "")}" data-tila="0">Hylkää</button>`;
    } else if (aktiivinen_tila === "hylätty") {
      toimintoHtml = `<button ${lomake} class="nappi-pieni nappi-hyva hitl-nappi" data-kid="${k.KID}" data-nimi="${escapeHtml(k.KurssiNimi)}" data-perustelu="${escapeHtml(k.Luokitteluperuste || "")}" data-tila="1">Sisällytä</button>`;
    }

    html += `<tr class="kurssi-rivi${hyvaksytty ? " hyvaksytty" : ""}" data-kid="${k.KID}">
      <td>${escapeHtml(k.KurssiNimi)}</td>
      <td class="koodi">${koodiJaOpasLinkki(k)}</td>
      ${kurssiMetaSolut(k)}
      <td class="perustelu">${perusteluHtml}${toimintoHtml ? `<div class="perustelu-toiminto">${toimintoHtml}</div>` : ""}</td></tr>`;
  }
  runko.innerHTML = html;
}

// Delegoitu klikkaus (rivit renderöidään uudelleen joka pollauksella): napit ja
// pylpyrät hoitavat oman toimintonsa, muu rivin klikkaus avaa kurssin tiedot.
document.getElementById("tutkimus-kurssit-rungot").addEventListener("click", (e) => {
  const kohde = e.target.closest(".hitl-nappi, .hyvaksy-nappi, .peukku, .perustelu-pylpyra, a");
  if (kohde) {
    if (kohde.matches(".hitl-nappi")) {
      const d = kohde.dataset;
      avaaHitlModaali(parseInt(d.kid), d.nimi, d.perustelu, d.tila === "1");
    } else if (kohde.matches(".hyvaksy-nappi")) {
      hyvaksyLuokitus(kohde);
    } else if (kohde.matches(".perustelu-pylpyra")) {
      kohde.classList.toggle("auki");
    }
    return;
  }
  const rivi = e.target.closest("tr.kurssi-rivi");
  if (rivi) avaaModaali(parseInt(rivi.dataset.kid));
});

document.querySelectorAll(".tila-nappi, .tila-nappi-nav").forEach((b) => {
  b.addEventListener("click", () => navigoi(`/tutkimukset/${aktiivinen_tutkimus.Slug}/${b.dataset.alasivu}`));
});
