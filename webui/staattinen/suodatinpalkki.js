"use strict";

// Jaettu suodatinpalkki (yliopisto + taso + hakusana) ja sen suodatinnäkymät
// (luokitukset, arvioinnit).

// Jaetun suodatinpalkin tila (luokitukset, arvioinnit).
const tyhjaSuodatin = () => ({ kkid: null, taso: null, hakusana: null });

let _suodKoulut = null, _suodTasot = null;

async function _suodatinData() {
  if (!_suodKoulut) _suodKoulut = await haeJson("/api/korkeakoulut");
  if (!_suodTasot) _suodTasot = await haeJson("/api/tasot");
  return { koulut: _suodKoulut, tasot: _suodTasot };
}

function _suodatinParams(tila) {
  const p = new URLSearchParams();
  if (tila.kkid) p.set("kkid", tila.kkid);
  if (tila.taso) p.set("taso", tila.taso);
  if (tila.hakusana) p.set("hakusana", tila.hakusana);
  return p.toString();
}

// Tutkimussivun suodatinnäkymät (välilehdet): tila = jaetun suodatinpalkin tilaobjekti.
function rekisteroiTutkimusNakymat(otsikkoId, palkki, tila, onChange) {
  window.rekisteroiNakymat?.({
    otsikko: document.getElementById(otsikkoId),
    palkki,
    lue: () => ({ ...tila }),
    aseta: async (s, lataa = true) => {
      Object.assign(tila, tyhjaSuodatin(), s);
      await rakennaSuodatinPalkki(palkki, tila, onChange);
      if (lataa) await onChange();
    },
    nimea: suodatinNimi,
  });
}

// Rakentaa suodatinkontrollit elementtiin ja kutsuu onChange muutoksilla.
async function rakennaSuodatinPalkki(el, tila, onChange) {
  const { koulut, tasot } = await _suodatinData();
  el.innerHTML =
    `<select class="suod-koulu" title="Yliopisto"><option value="">Kaikki yliopistot</option>`
    + koulut.map((k) => `<option value="${k.KKID}">${escapeHtml(koulunLyhenne(k) || k.KouluNimi)}</option>`).join("")
    + `</select>`
    + `<select class="suod-taso" title="Taso"><option value="">Kaikki tasot</option>`
    + tasot.map((x) => `<option value="${escapeHtml(x)}">${escapeHtml(tasoNimi(x))}</option>`).join("")
    + `</select>`
    + `<input class="suod-haku" type="search" placeholder="Hae nimestä tai koodista…" />`;
  const koulu = el.querySelector(".suod-koulu");
  const taso = el.querySelector(".suod-taso");
  const haku = el.querySelector(".suod-haku");
  koulu.value = tila.kkid || ""; taso.value = tila.taso || ""; haku.value = tila.hakusana || "";
  // "+"-tilassa (uuden näkymän luonti) valinnat vain kerätään — lista on piilossa, ei latausta.
  const muuttui = () => { if (window.omaNakyma?.() !== "+") onChange(); };
  koulu.onchange = () => { tila.kkid = koulu.value || null; muuttui(); };
  taso.onchange = () => { tila.taso = taso.value || null; muuttui(); };
  let viive;
  haku.oninput = () => {
    clearTimeout(viive);
    viive = setTimeout(() => { tila.hakusana = haku.value.trim() || null; muuttui(); }, 300);
  };
}
