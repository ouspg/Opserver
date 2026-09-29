"use strict";

// Kurssit-näkymä: koko kurssilista suodattimineen, osissa ladattuna ja erissä renderöitynä.

let kaikki_kurssit = [];

let kurssit_jarjestys = { sarake: null, suunta: null };

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

// Täytä OPS-lukuvuosi-suodatin (uusin ensin), oletukseksi uusin
async function taytaLukuvuodet() {
  const sel = document.getElementById("suodatin-lukuvuosi");
  const vuodet = await haeJson("/api/lukuvuodet");
  sel.innerHTML = vuodet.map((v) => `<option value="${escapeHtml(v)}">${escapeHtml(v)}</option>`).join("");
  // Lista on uusin-ensin, joten ensimmäinen optio (oletusvalinta) on viimeisin vuosi
}

// Täytä taso-suodatin senhetkisen lukuvuoden + yliopiston mukaan (säilytä valinta)
async function taytaTasot(lukuvuosi, kkid) {
  const sel = document.getElementById("suodatin-taso");
  const valittu = sel.value;
  const params = new URLSearchParams();
  if (lukuvuosi) params.set("lukuvuosi", lukuvuosi);
  if (kkid) params.set("kkid", kkid);
  const tasot = await haeJson(`/api/tasot?${params}`);
  // Näytä raa'at arvot sellaisinaan: kannassa on rinnakkaisia muotoja
  // ("aine" ja "Aineopinnot"), eikä TASO_SUOMI-mappaus saa piilottaa niitä.
  sel.innerHTML = '<option value="">Kaikki tasot</option>'
    + tasot.map((t) => `<option value="${escapeHtml(t)}">${escapeHtml(t)}</option>`).join("");
  if (valittu && tasot.includes(valittu)) sel.value = valittu;  // säilytä jos yhä tarjolla
}

// Kurssilista osissa (tuotannossa ~7 Mt kerralla); pieni ensimmäinen osa, jotta
// rivit näkyvät heti, sitten isompia (vähemmän kiertoviiveitä). Taulukko renderöidään
// ensimmäisen osan jälkeen, sitten korkeintaan OSARENDER_VALI_MS välein ja
// lopuksi — koko listan uudelleenrakennus joka osalla olisi O(n²).
const KURSSIT_ENSIMMAINEN_OSA = 250;
const KURSSIT_OSA = 2000;

const KURSSIT_RIVIERA = 300;
let kurssit_lataus = 0;
let kurssit_kesken = false;
let kurssit_renderointi = 0;

async function lataaKurssit() {
  const lataus = ++kurssit_lataus;
  const sel = document.getElementById("suodatin-lukuvuosi");
  if (!sel.options.length) await taytaLukuvuodet();
  const kkid = document.getElementById("suodatin-koulu").value;
  taytaTasot(sel.value, kkid);  // ei awaitia: tasovalikko ei saa viivästää listaa
  const params = new URLSearchParams();
  if (sel.value) params.set("lukuvuosi", sel.value);
  if (kkid) params.set("kkid", kkid);
  kaikki_kurssit = [];
  kurssit_kesken = true;
  kurssit_renderointi++;  // edellisen listan erät eivät jatku latausrivin perään
  document.getElementById("kurssit-rungot").innerHTML = '<tr><td colspan="6">Ladataan kursseja…</td></tr>';
  let renderoity = 0;
  try {
    for (;;) {
      const koko = kaikki_kurssit.length ? KURSSIT_OSA : KURSSIT_ENSIMMAINEN_OSA;
      params.set("alku", kaikki_kurssit.length);
      params.set("koko", koko);
      const osa = await haeJson(`/api/kurssit?${params}`);
      await koulut_ladattu;
      if (lataus !== kurssit_lataus || location.pathname !== "/kurssit") return;  // suodatin vaihtui / poistuttiin
      kaikki_kurssit.push(...osa);
      kurssit_kesken = osa.length === koko;
      if (!kurssit_kesken || Date.now() - renderoity > OSARENDER_VALI_MS) {
        renderKurssit();
        renderoity = Date.now();
      }
      if (!kurssit_kesken) return;
    }
  } catch (_) {
    if (lataus !== kurssit_lataus) return;
    kurssit_kesken = false;
    renderKurssit();
    document.getElementById("kurssit-lkm").textContent += " — lataus keskeytyi (yhteysvirhe)";
  }
}

function renderKurssit() {
  const taso = document.getElementById("suodatin-taso").value;
  const suodatettu = taso ? kaikki_kurssit.filter((k) => k.Taso === taso) : kaikki_kurssit;
  const ryhmat = ryhmitaKurssit(suodatettu);
  const runko = document.getElementById("kurssit-rungot");
  const lkm = Object.keys(ryhmat).length;
  document.getElementById("kurssit-lkm").textContent = `${lkm} kurssia${kurssit_kesken ? " — ladataan lisää…" : ""}`;
  varustaJarjestys(document.querySelector("#s-kurssit thead"), kurssit_jarjestys, renderKurssit);
  const kierros = ++kurssit_renderointi;  // keskeyttää edellisen renderöinnin erät
  if (lkm === 0) {
    runko.innerHTML = '<tr><td colspan="6">Ei kursseja.</td></tr>';
    return;
  }
  const ryhmatLista = Object.values(ryhmat);
  if (kurssit_jarjestys.sarake) {
    const vertaa = vertaaKursseja(kurssit_jarjestys.sarake, kurssit_jarjestys.suunta);
    ryhmatLista.sort((a, b) => vertaa(a[0], b[0]));
  }
  // Rivit merkkijonoina ja delegoitu klikkikäsittelijä (alla): ~10 000 riviä ilman
  // rivikohtaisia elementtejä ja kuuntelijoita.
  const rivit = ryhmatLista.map((versiot) => {
    const uusin = versiot[0];
    const vuosiSolmu = versiot.length > 1
      ? `<select class="vuosivalinta">${versiot.map((v) =>
          `<option value="${v.KID}">${escapeHtml(v.Opetusvuosi)}</option>`).join("")}</select>`
      : escapeHtml(uusin.Opetusvuosi);
    return `<tr class="kurssi-rivi" data-kid="${uusin.KID}">
      <td>${escapeHtml(uusin.KurssiNimi)}</td>
      <td class="koodi">${koodiJaOpasLinkki(uusin)}</td>
      ${kurssiMetaSolut(uusin)}
      <td>${vuosiSolmu}</td></tr>`;
  });
  // DOMiin erissä: koko listan asettelu kerralla jumitti sivun ~1 s (8 700 riviä),
  // erä ~50 ms. Kaikki rivit päätyvät lopulta DOMiin (selaimen haku toimii).
  let i = 0;
  const era = () => {
    if (kierros !== kurssit_renderointi) return;
    runko.insertAdjacentHTML("beforeend", rivit.slice(i, i += KURSSIT_RIVIERA).join(""));
    if (i < rivit.length) setTimeout(era);
  };
  runko.innerHTML = "";
  era();
}

// Rivin klikkaus avaa kurssin (valitun vuoden version); linkki ja vuosivalinta eivät.
document.getElementById("kurssit-rungot").addEventListener("click", (e) => {
  const rivi = e.target.closest("tr.kurssi-rivi");
  if (!rivi || e.target.closest("a, select")) return;
  const valinta = rivi.querySelector(".vuosivalinta");
  avaaModaali(parseInt(valinta ? valinta.value : rivi.dataset.kid));
});

function rekisteroiKurssitNakymat() {
  const lv = document.getElementById("suodatin-lukuvuosi");
  const koulu = document.getElementById("suodatin-koulu");
  const taso = document.getElementById("suodatin-taso");
  const aseta = async (s, lataa = true) => {
    if (!lv.options.length) await taytaLukuvuodet();
    lv.value = s.lukuvuosi || lv.options[0]?.value || "";
    koulu.value = s.kkid || "";
    // taytaTasot säilyttää valinnan vain jos se on jo selectin arvo
    taso.innerHTML = `<option value="${escapeHtml(s.taso || "")}"></option>`;
    if (lataa) await lataaKurssit();
    else await taytaTasot(lv.value, koulu.value);
  };
  window.rekisteroiNakymat?.({
    otsikko: document.querySelector("#s-kurssit h2"),
    palkki: document.getElementById("kurssit-suodatin"),
    lue: () => ({ lukuvuosi: lv.value || null, kkid: koulu.value || null, taso: taso.value || null }),
    aseta,
    // Oletuslukuvuotta (uusin) ei toisteta nimessä
    nimea: (s) => suodatinNimi({ ...s, lukuvuosi: s.lukuvuosi === lv.options[0]?.value ? null : s.lukuvuosi }),
  });
  aseta({});
}

// "+"-tilassa (uuden näkymän luonti) lista on piilossa: päivitä vain tasovalikko, älä lataa.
function kurssiSuodatinMuuttui() {
  if (window.omaNakyma?.() === "+") {
    taytaTasot(document.getElementById("suodatin-lukuvuosi").value, document.getElementById("suodatin-koulu").value);
  } else {
    lataaKurssit();
  }
}
document.getElementById("suodatin-lukuvuosi").addEventListener("change", kurssiSuodatinMuuttui);
document.getElementById("suodatin-koulu").addEventListener("change", kurssiSuodatinMuuttui);
document.getElementById("suodatin-taso").addEventListener("change", renderKurssit);
