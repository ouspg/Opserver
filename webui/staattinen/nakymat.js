"use strict";

// Suodatetut näkymät välilehtinä (Kaikki | OULU | OULU (2) | +).
// Välilehdet ovat jaettua tilaa (palvelin välittää ne WebSocketilla), joten
// muiden käyttäjien pallurat voi näyttää sen välilehden kohdalla, jota he katsovat.
//
// Sivu rekisteröi itsensä: rekisteroiNakymat({ otsikko, palkki, lue, aseta, nimea })
//   otsikko = h2, jonka perään nauha tulee; palkki = suodatinkontrollit (näkyvät vain "+"-tilassa)
//   lue() → nykyinen suodatin; aseta(s) → ota suodatin käyttöön ja lataa; nimea(s) → välilehden nimi

let _nakymaKonf = null;
let _nakymaSivu = null;
let _valittuNakyma = null;   // null = Kaikki, "+" = uuden luonti, muuten välilehden id
let _jaetutNakymat = {};     // sivupolku → [{id, nimi, suodatin}]
let _nakymaMuut = [];        // muut käyttäjät (yhteistyo.js)

function _sivunNakymat() {
  return _jaetutNakymat[_nakymaSivu] || [];
}

function _renderNakymaNauha() {
  if (!_nakymaKonf || window.lahetyksiaKesken) return;  // ei korvata animoitua nappia
  const vanha = _nakymaKonf.otsikko.parentNode.querySelector(".nakyma-nauha");
  const nauha = document.createElement("div");
  nauha.className = "nakyma-nauha";
  const valilehdet = [{ id: null, nimi: "Kaikki" }, ..._sivunNakymat(), { id: "+", nimi: "+" }];
  for (const v of valilehdet) {
    const b = document.createElement("button");
    b.className = "nakyma-valilehti" + (v.id === _valittuNakyma ? " aktiivinen" : "");
    b.textContent = v.nimi;
    if (v.id === "+") b.title = "Luo uusi suodatettu näkymä";
    b.addEventListener("click", () => valitseNakyma(v.id));
    // Samalla välilehdellä olevat näkyvät leijuvina kursoreina, muut tässä.
    if (v.id !== _valittuNakyma) {
      for (const k of _nakymaMuut) {
        if (!k.profiili || k.sivu !== _nakymaSivu || (k.nakyma ?? null) !== v.id) continue;
        const c = document.createElement("canvas");
        c.width = c.height = 10;
        c.className = "nakyma-pallura";
        c.title = k.nimimerkki || "?";
        window.piirraYmpyra?.(c, k.profiili, !k.aktiivinen);
        b.appendChild(c);
      }
    }
    nauha.appendChild(b);
  }
  if (_valittuNakyma === "+") {
    const luo = document.createElement("button");
    luo.className = "nappi-pieni nakyma-luo";
    luo.textContent = "✓ Luo näkymä";
    luo.addEventListener("click", luoNakyma);
    nauha.appendChild(luo);
  }
  if (vanha) vanha.replaceWith(nauha);
  else _nakymaKonf.otsikko.after(nauha);
  _nakymaKonf.palkki.classList.toggle("piilotettu", _valittuNakyma !== "+");
}

async function valitseNakyma(id) {
  _valittuNakyma = id;
  _renderNakymaNauha();
  window.lahetaTilaNyt?.();
  const v = _sivunNakymat().find((n) => n.id === id);
  await _nakymaKonf.aseta(v ? { ...v.suodatin } : {});
}

async function luoNakyma(e) {
  const nappi = e.currentTarget;  // null awaitin jälkeen
  const suodatin = _nakymaKonf.lue();
  const pohja = _nakymaKonf.nimea(suodatin) || "Kaikki";
  const samoja = _sivunNakymat().filter((n) => n.nimi === pohja || n.nimi.startsWith(`${pohja} (`)).length;
  const nimi = samoja ? `${pohja} (${samoja + 1})` : pohja;
  const id = Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
  const uusi = { id, nimi, suodatin };
  try {
    await lahetaNapilla(nappi, "/api/nakymat", { sivu: _nakymaSivu, ...uusi });
  } catch (virhe) {
    nappi.textContent = `Virhe: ${virhe.message}`;
    return;
  }
  // Palvelimen broadcast tuo saman näkymän; lisää heti, ettei valinta odota sitä.
  const lista = (_jaetutNakymat[_nakymaSivu] ||= []);
  if (!lista.some((n) => n.id === id)) lista.push(uusi);
  _valittuNakyma = id;
  _renderNakymaNauha();
  window.lahetaTilaNyt?.();
}

window.rekisteroiNakymat = function (konf) {
  _nakymaKonf = konf;
  _nakymaSivu = location.pathname;
  _valittuNakyma = null;
  _renderNakymaNauha();
};

// Oma näkymä läsnäolotietoon: null (Kaikki) muilla kuin rekisteröidyllä sivulla.
window.omaNakyma = () => (location.pathname === _nakymaSivu ? _valittuNakyma : null);

window.nakymatKuuntelija = (data) => {
  _jaetutNakymat = data || {};
  _renderNakymaNauha();
};

// Kutsutaan jokaisella kursoriliikkeellä → renderöi vain kun pallurat muuttuvat
// (muuten nauhan uusiminen kesken klikkauksen hukkaisi klikin).
let _palluraAvain = "";
window.paivitaNakymaPallurat = (muut) => {
  _nakymaMuut = muut;
  const avain = JSON.stringify(muut.map((k) => [k.id, k.sivu, k.nakyma, k.aktiivinen, k.nimimerkki, k.profiili]));
  if (avain === _palluraAvain) return;
  _palluraAvain = avain;
  _renderNakymaNauha();
};
