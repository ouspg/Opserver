"use strict";

// Tutkimuksen arvioinnit: kurssit × kysymykset, korjaukset ja hyväksynnät.

function _renderArviointiSolu(kys, v) {
  if (typeof v === "string") return escapeHtml(v || "—");
  const luokittelu = kys.Luokittelu || "vapaa_teksti";
  const perustelu = v?.vastaus ? `<em class="arvio-perustelu">${escapeHtml(v.vastaus)}</em>` : "";
  // Vanhentunut = tekoälyn vastaus on generoitu vanhaan kysymykseen/kehotteeseen
  const vanha = v?.vanhentunut
    ? `<span class="vanha-merkki" title="Tämä tekoälyn vastaus on generoitu vanhentuneeseen kysymykseen tai kehotteeseen. Aja LLM-arviointi uudelleen päivittääksesi.">⚠ vanhentunut</span>`
    : "";
  let body;
  if (luokittelu === "luokittelu" && v?.luokka) {
    body = `<span class="luokka-badge">${escapeHtml(v.luokka)}</span>${perustelu}`;
  } else if (luokittelu === "asteikko" && v?.pisteet != null) {
    const max = kys.LuokitteluMaarittely?.maksimi;
    body = `<span class="pisteet-arvo">${escapeHtml(v.pisteet)}${max ? "/" + escapeHtml(max) : ""}</span>${perustelu}`;
  } else if (luokittelu === "lista" && Array.isArray(v?.lista)) {
    const kohdat = v.lista.length
      ? `<ul class="arvio-lista">${v.lista.map((x) => `<li>${escapeHtml(x)}</li>`).join("")}</ul>`
      : '<span class="arvio-tyhja">—</span>';
    body = kohdat + perustelu;
  } else {
    body = escapeHtml(v?.vastaus || "—");
  }
  return vanha + body;
}

function _vastusOnAnnettu(v) {
  if (typeof v === "string") return !!v;
  return !!(v?.vastaus || v?.luokka || v?.pisteet != null || (Array.isArray(v?.lista) && v.lista.length));
}

let arvioinnit_data = null;
let arvioinnit_suodatin = tyhjaSuodatin();
let arvioinnit_jarjestys = { sarake: null, suunta: null };

// Virhetaksonomian juurisyyt (mallit.JUURISYYT) ihmisluettavina.
const JUURISYY_NIMI = {
  riittamaton_opas: "Riittämätön opinto-opas",
  llm_virhe: "LLM:n väärinymmärrys",
};

// Korjausikkuna kutsuu tätä tallennuksen jälkeen, jotta solu päivittyy heti.
window.paivitaArvioinnit = async function () {
  if (aktiivinen_tutkimus) {
    await renderTutkimusArvioinnit(aktiivinen_tutkimus.Slug, aktiivinen_tutkimus.LuokittelunNimi, true);
  }
};

// Arvioinnit ladataan osissa ja taulukko kasvaa sitä mukaa (huono yhteys: koko
// data kerralla oli ~0,5 Mt). arvioinnit_lataus = käynnissä olevan latauksen tunniste.
const ARVIOINNIT_OSA = 25;
// Hiljainen päivitys (pollaus 15 s) hakee kaiken uudelleen: isommat osat = vähemmän
// pyyntöjä (palvelin hakee tutkimuksen vastaukset jokaiselle osalle).
const ARVIOINNIT_POLLAUS_OSA = 200;
let arvioinnit_lataus = 0;
let arvioinnit_kesken = false;

async function renderTutkimusArvioinnit(slug, nimi, sailyta = false) {
  // Pollaus ei keskeytä käynnissä olevaa latausta (muuten taulu jäisi vajaaksi).
  if (sailyta && arvioinnit_kesken) return;
  const lataus = ++arvioinnit_lataus;
  document.getElementById("tutkimus-arvioinnit-otsikko").textContent = `${nimi} — arvioinnit`;
  const sisalto = document.getElementById("tutkimus-arvioinnit-sisalto");
  const suodatinEl = document.getElementById("tutkimus-arvioinnit-suodatin");

  // sailyta=true (pollaus/tallennus): lataa hiljaa, vaihda data vasta valmiina,
  // säilytä suodatinvalinta. Muuten tyhjä pöytä ja rivit näkyviin osa kerrallaan.
  if (!sailyta) {
    arvioinnit_data = null;
    arvioinnit_suodatin = tyhjaSuodatin();
    arvioinnit_jarjestys = { sarake: null, suunta: null };
    document.getElementById("tutkimus-arvioinnit-lkm").textContent = "";
    sisalto.innerHTML = '<p class="tulossa">Ladataan arviointeja…</p>';
    rakennaSuodatinPalkki(suodatinEl, arvioinnit_suodatin, renderArvioinnitTaulu);
    rekisteroiTutkimusNakymat("tutkimus-arvioinnit-otsikko", suodatinEl, arvioinnit_suodatin, renderArvioinnitTaulu);
  }
  arvioinnit_kesken = true;
  let koottu = null;
  let renderoity = 0;
  const koko = sailyta ? ARVIOINNIT_POLLAUS_OSA : ARVIOINNIT_OSA;
  try {
    for (let sivu = 0; ; sivu++) {
      const osa = await haeJson(`/api/tutkimukset/${slug}/arvioinnit?sivu=${sivu}&koko=${koko}`);
      await koulut_ladattu;
      // Uudempi lataus ohitti, tai käyttäjä siirtyi muualle (älä kuluta kaistaa piilonäkymään).
      if (lataus !== arvioinnit_lataus || jaaPolku().alasivu !== "arvioinnit") return;
      if (!osa.kysymykset.length) {
        arvioinnit_data = null;
        document.getElementById("tutkimus-arvioinnit-lkm").textContent = "";
        suodatinEl.innerHTML = "";
        document.querySelector("#s-tutkimus-arvioinnit .nakyma-nauha")?.remove();
        sisalto.innerHTML = '<p class="tulossa">Ei arviointikysymyksiä — lisää kysymyksiä tutkimukselle.</p>';
        return;
      }
      koottu = koottu ? { ...osa, kurssit: koottu.kurssit.concat(osa.kurssit) } : osa;
      const valmis = !osa.kurssit.length || koottu.kurssit.length >= osa.yhteensa;
      if (valmis) arvioinnit_kesken = false;
      // Koko taulun uudelleenrakennus joka osalla olisi O(n²): korkeintaan OSARENDER_VALI_MS välein.
      if (valmis || (!sailyta && Date.now() - renderoity > OSARENDER_VALI_MS)) {
        arvioinnit_data = koottu;
        renderArvioinnitTaulu();
        renderoity = Date.now();
      }
      if (valmis) return;
    }
  } catch (_) {
    if (lataus === arvioinnit_lataus && !sailyta) {
      document.getElementById("tutkimus-arvioinnit-lkm").textContent +=
        " — lataus keskeytyi (yhteysvirhe), päivittyy automaattisesti";
    }
  } finally {
    if (lataus === arvioinnit_lataus) arvioinnit_kesken = false;
  }
}

function _arvioinnitSuodatetut() {
  const s = arvioinnit_suodatin;
  const haku = (s.hakusana || "").toLowerCase();
  return arvioinnit_data.kurssit.filter((k) => {
    if (s.kkid && String(k.KKID) !== String(s.kkid)) return false;
    if (s.taso && (k.Taso || "") !== s.taso) return false;
    if (haku && !((k.KurssiNimi || "").toLowerCase().includes(haku)
                  || (k.Koodi || "").toLowerCase().includes(haku))) return false;
    return true;
  });
}

const ARVIOINTI_SARAKKEET = { Nimi: "nimi", Taso: "taso", op: "op" };

// Arviointitaulun delegoitu klikkaus: Korjaa / Hyväksy solun kysymykselle, muu rivin
// klikkaus avaa kurssin. Kurssi haetaan klikkaushetken datasta (pollaus vaihtaa sen).
document.getElementById("tutkimus-arvioinnit-sisalto").addEventListener("click", async (e) => {
  const rivi = e.target.closest("tr.kurssi-rivi");
  if (!rivi || e.target.closest("a, .peukku")) return;
  const kid = parseInt(rivi.dataset.kid);
  const nappi = e.target.closest("button[data-lomake], .arvio-hyvaksy-nappi");
  if (!nappi) { avaaModaali(kid); return; }
  const k = arvioinnit_data?.kurssit.find((x) => x.KID === kid);
  const i = parseInt(nappi.closest("td").dataset.i);
  const kys = arvioinnit_data?.kysymykset[i];
  if (!k || !kys) return;
  const v = k.vastaukset[i];
  if (nappi.matches("[data-lomake]")) {
    window.avaaArviointiMuokkaus?.(aktiivinen_tutkimus.TID, aktiivinen_tutkimus.Slug, kid, kys, v,
                                   k.korjaukset?.[kys.KysID] || null, k.KurssiNimi);
    return;
  }
  const kohde = `arvion "${k.KurssiNimi}" / "${kys.Kysymys.slice(0, 40)}"`;
  if (await lahetaHyvaksynta(nappi, `${kid}/kysymykset/${kys.KysID}`, kohde)) {
    await window.paivitaArvioinnit();
  }
});

function renderArvioinnitTaulu() {
  if (!arvioinnit_data) return;  // suodatinmuutos ennen ensimmäistä osaa
  const { kysymykset } = arvioinnit_data;
  const kurssit = _arvioinnitSuodatetut();
  if (arvioinnit_jarjestys.sarake) {
    kurssit.sort(vertaaKursseja(arvioinnit_jarjestys.sarake, arvioinnit_jarjestys.suunta));
  }
  const sisalto = document.getElementById("tutkimus-arvioinnit-sisalto");
  const lkm = document.getElementById("tutkimus-arvioinnit-lkm");

  const arvioitu = kurssit.filter((k) => k.vastaukset.some(_vastusOnAnnettu)).length;
  lkm.textContent = `${arvioitu} / ${kurssit.length} kurssia arvioitu`
    + (arvioinnit_kesken ? ` — ladattu ${arvioinnit_data.kurssit.length} / ${arvioinnit_data.yhteensa}…` : "");

  if (!kurssit.length) {
    sisalto.innerHTML = '<p class="tulossa">Ei kursseja suodatuksella.</p>';
    return;
  }

  const taulu = document.createElement("table");

  const thead = taulu.createTHead();
  const otsikkorivi = thead.insertRow();
  for (const teksti of ["Nimi", "Taso", "op"]) {
    const th = document.createElement("th");
    th.textContent = teksti;
    th.dataset.jarjesta = ARVIOINTI_SARAKKEET[teksti];
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
  varustaJarjestys(thead, arvioinnit_jarjestys, renderArvioinnitTaulu);

  const tid = aktiivinen_tutkimus?.TID;
  // Merkkijonona ja delegoidulla kuuntelijalla (alla): rivit × kysymykset soluja,
  // joissa kussakin oli 3–4 omaa kuuntelijaa.
  taulu.createTBody().innerHTML = kurssit.map((k) => {
    const solut = kysymykset.map((kys, i) => {
      const v = k.vastaukset[i];
      const korjaus = k.korjaukset?.[kys.KysID] || null;
      // Ihmisen korjaus näkyy tekoälyn vastauksen alla, ei sen tilalla: molemmat
      // tarvitaan virhetaksonomian arviointiin (oliko opas puutteellinen vai LLM väärässä).
      const korjausHtml = korjaus
        ? `<div class="arvio-korjaus">${_renderArviointiSolu(kys, korjaus)}` +
          `<span class="arvio-korjaaja">Korjannut ${escapeHtml(korjaus.nimi || "?")}` +
          `${korjaus.juurisyy ? " · " + escapeHtml(JUURISYY_NIMI[korjaus.juurisyy] || korjaus.juurisyy) : ""}</span></div>`
        : "";
      // Hyväksyntä: ihmisen korjaus on aina hyväksytty, LLM-vastauksen voi
      // peukuttaa. Pelkkä visuaalinen tila — Korjaa toimii yhä.
      const hyvaksytty = !!korjaus || !!v.hyvaksyja;
      let hyvaksyHtml = "";
      if (!korjaus && v.hyvaksyja) {
        hyvaksyHtml = `<button class="arvio-korjaa-nappi nappi-hyva peukku" title="Hyväksyjä: ${escapeHtml(v.hyvaksyja)}">👍</button> `;
      } else if (!korjaus && _vastusOnAnnettu(v)) {
        hyvaksyHtml = `<button class="arvio-korjaa-nappi arvio-hyvaksy-nappi" title="Hyväksy LLM:n tekemä arvio tästä">Hyväksy</button> `;
      }
      return `<td class="arviointi-vastaus${hyvaksytty ? " hyvaksytty" : ""}" data-i="${i}">` +
        `<span class="arvio-teksti">${_renderArviointiSolu(kys, v)}</span>` + korjausHtml + hyvaksyHtml +
        `<button class="arvio-korjaa-nappi${hyvaksytty ? " nappi-haalea" : ""}" data-lomake="arvio:${tid}:${k.KID}:${kys.KysID}">Korjaa</button></td>`;
    }).join("");
    return `<tr class="kurssi-rivi" data-kid="${k.KID}">
      <td>${kurssiLinkki(k)}</td>
      <td>${tasoTeksti(k.Taso)}</td>
      <td class="op">${escapeHtml(k.Opintopisteet ?? "—")}</td>${solut}</tr>`;
  }).join("");

  sisalto.innerHTML = "";
  sisalto.appendChild(taulu);
}
