"use strict";

// Korkeakoulut-näkymä: koulut, opinto-opaslinkit ja haettujen kurssien kausitiilet.

// "YYYY-YYYY" tai "YYYY-YY" (Sisu/HY) -> [alkuvuosi, loppuvuosi]; null jos virheellinen
function parsiVuodet(kausi) {
  const m = /^(\d{4})-(\d{2,4})$/.exec((kausi || "").trim());
  if (!m) return null;
  const alku = parseInt(m[1], 10);
  let loppu;
  if (m[2].length === 2) {
    loppu = Math.floor(alku / 100) * 100 + parseInt(m[2], 10);
    if (loppu < alku) loppu += 100;
  } else {
    loppu = parseInt(m[2], 10);
  }
  return [alku, loppu];
}

// Opinto-opas-linkki muodossa "Sisu: sisu.helsinki.fi" (tyyppi tekstiin, https:// pois)
function opasLinkki(k) {
  const tyyppi = escapeHtml(k.OpsTyyppi || "");
  if (!k.OpsOsoite) return tyyppi;
  const host = k.OpsOsoite.replace(/^https?:\/\//, "").replace(/\/+$/, "");
  return `<a href="${encodeURI(k.OpsOsoite)}" target="_blank" rel="noopener" class="ops-linkki">`
    + `${tyyppi}: ${escapeHtml(host)}</a>`;
}

// Vaihteleva pastellisävy vuoden mukaan (todennäköisesti täydet kaudet)
function pastelli(vuosi) {
  const hue = (vuosi * 47) % 360;
  return `hsl(${hue}, 62%, 88%)`;
}

// Vuosisarakkeiden solut yhdelle koululle: kukin OPS-kausi vie colspan = vuosien
// määrä ja näkyy tiilenä. Pastelli kun kurssimäärä on lähellä rivin suurinta
// (todennäk. kaikki haettu), harmaa kun selvästi vähemmän tai kautta ei ole haettu.
function vuosiSolut(kaudet, minV, maxV) {
  const maxLkm = kaudet.reduce((m, k) => Math.max(m, k.lkm), 0);
  let html = "";
  let col = minV;
  while (col < maxV) {
    const kausi = kaudet.find((x) => x.alku <= col && col < x.loppu);
    if (kausi) {
      const span = Math.min(kausi.loppu, maxV) - col;
      const taysi = maxLkm > 0 && kausi.lkm >= 0.5 * maxLkm;
      const tiili = taysi
        ? `<span class="kk-tiili kk-tiili-taysi" style="background:${pastelli(col)}">${kausi.lkm} kpl</span>`
        : `<span class="kk-tiili kk-tiili-vajaa">${kausi.lkm} kpl</span>`;
      html += `<td class="kk-solu" colspan="${span}">${tiili}</td>`;
      col += span;
    } else {
      html += `<td class="kk-solu"><span class="kk-tiili kk-tiili-eihaettu">ei haettu</span></td>`;
      col += 1;
    }
  }
  return html;
}

async function lataaKorkeakoulut() {
  const otsikko = document.getElementById("korkeakoulut-otsikko");
  const runko = document.getElementById("korkeakoulut-rungot");
  const koulut = await haeJson("/api/korkeakoulut");
  kaikki_koulut = koulut;

  // Parsi kunkin koulun kaudet ja koko aineiston vuosiväli
  let minV = Infinity, maxV = -Infinity;
  for (const k of koulut) {
    k._kaudet = [];
    for (const kausi of (k.KurssitKausittain || [])) {
      const v = parsiVuodet(kausi.Opetusvuosi);
      if (v) k._kaudet.push({ alku: v[0], loppu: v[1], lkm: kausi.lkm });
    }
    k._kaudet.sort((a, b) => a.alku - b.alku);
    for (const kk of k._kaudet) { minV = Math.min(minV, kk.alku); maxV = Math.max(maxV, kk.loppu); }
  }
  const onVuosia = maxV > minV;
  const vuodet = [];
  if (onVuosia) for (let s = minV; s < maxV; s++) vuodet.push(s);

  // Otsikko (kaksirivinen kun vuosisarakkeita on)
  if (onVuosia) {
    otsikko.innerHTML =
      `<tr><th rowspan="2">Nimi</th><th rowspan="2">Opinto-opas</th>`
      + `<th colspan="${vuodet.length}" class="kk-kurssit-otsikko">Järjestelmään haetut kurssit</th></tr>`
      + `<tr>${vuodet.map((s) => `<th class="kk-vuosi">${s}-${s + 1}</th>`).join("")}</tr>`;
  } else {
    otsikko.innerHTML = `<tr><th>Nimi</th><th>Opinto-opas</th></tr>`;
  }

  // Rungot
  runko.innerHTML = "";
  if (koulut.length === 0) {
    runko.innerHTML = `<tr><td colspan="${2 + vuodet.length}">Ei korkeakouluja.</td></tr>`;
    return;
  }
  for (const k of koulut) {
    const rivi = document.createElement("tr");
    rivi.innerHTML = `<td class="kk-nimi">${escapeHtml(k.KouluNimi)}</td>`
      + `<td class="kk-opas">${opasLinkki(k)}</td>`
      + (onVuosia ? vuosiSolut(k._kaudet, minV, maxV) : "");
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
