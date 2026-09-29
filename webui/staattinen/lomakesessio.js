"use strict";

// Jaettu korjauslomake: HITL-modaalit (luokituksen Hylkää/Sisällytä, arvion Korjaa)
// yhteismuokattavina. Saman päätöksen modaalin avanneet näkevät samat kenttien arvot,
// toistensa pallurat ja tekstikursorit. Ensimmäisen avaajan arvot (esim. nimi ja
// sähköposti) alustavat lomakkeen; myöhemmin liittyvät saavat ne. Muut käyttäjät näkevät
// avoimen lomakkeen napin kohdalla (pallura napin alla + sykkivä korostus).
//
// Kentät merkitään modaalissa data-jaettu="nimi" (radioryhmässä sama nimi jokaisella).
// Erikoiskentät (arvion kohdelista) annetaan { lue(), aseta(arvo) } -parina.
// Napit, jotka avaavat lomakkeen, merkitään data-lomake="<avain>".
{
  const LAHETYS_VALI_MS = 60;
  let _avain = null, _modaali = null, _erikois = {}, _tallennettu = null;
  let _alustettu = false, _aloittaja = false, _sovelletaan = false;
  let _muokkaajat = [], _odottava = null, _ajastin = null;
  const _kuunnellut = new WeakSet();

  const laheta = (viesti) => window.lahetaWs?.(viesti);
  const omaId = () => window._omaId;

  function kentat() {
    const nimet = new Set([..._modaali.querySelectorAll("[data-jaettu]")].map((e) => e.dataset.jaettu));
    Object.keys(_erikois).forEach((k) => nimet.add(k));
    return [...nimet];
  }

  function lue(k) {
    if (_erikois[k]) return _erikois[k].lue();
    const els = [..._modaali.querySelectorAll(`[data-jaettu="${k}"]`)];
    if (els[0]?.type === "radio") return els.find((e) => e.checked)?.value ?? null;
    return els[0]?.value ?? null;
  }

  function aseta(k, v) {
    _sovelletaan = true;  // erikoiskentän uudelleenrakennus ei saa lähettää muutosta takaisin
    try {
      if (_erikois[k]) {
        if (JSON.stringify(_erikois[k].lue()) !== JSON.stringify(v)) _erikois[k].aseta(v);
        return;
      }
      const els = [..._modaali.querySelectorAll(`[data-jaettu="${k}"]`)];
      if (els[0]?.type === "radio") { els.forEach((e) => { e.checked = e.value === v; }); return; }
      const el = els[0];
      if (!el || el.value === (v ?? "")) return;
      const oma = document.activeElement === el;
      const [alku, loppu] = [el.selectionStart, el.selectionEnd];
      el.value = v ?? "";
      if (oma) try { el.setSelectionRange(alku, loppu); } catch (_) { /* select/number */ }
    } finally {
      _sovelletaan = false;
    }
  }

  function kursori(el) {
    try { return el.selectionStart ?? 0; } catch (_) { return 0; }
  }

  // Lähetys harvennettuna; arvon muutos ei huku perään tulevan pelkän kursorisiirron alle.
  function jonoon(kentta, arvollinen, el) {
    if (_odottava && _odottava.kentta !== kentta) laheta(_odottava);
    const arvo = arvollinen ? { arvo: lue(kentta) }
               : (_odottava?.kentta === kentta && "arvo" in _odottava ? { arvo: _odottava.arvo } : {});
    _odottava = { tyyppi: "lomake-arvo", avain: _avain, kentta, kursori: el ? kursori(el) : 0, ...arvo };
    clearTimeout(_ajastin);
    _ajastin = setTimeout(() => { if (_odottava) laheta(_odottava); _odottava = null; }, LAHETYS_VALI_MS);
  }

  function kenttaNimi(el) {
    const e = el?.closest?.("[data-jaettu]");
    return e && _modaali?.contains(e) ? e.dataset.jaettu : null;
  }

  function kuuntele(modaali) {
    if (_kuunnellut.has(modaali)) return;
    _kuunnellut.add(modaali);
    const arvoMuuttui = (e) => {
      const k = modaali === _modaali && kenttaNimi(e.target);
      if (k && !_sovelletaan) jonoon(k, true, e.target);
    };
    const kursoriLiikkui = (e) => {
      const k = modaali === _modaali && kenttaNimi(e.target);
      if (k && !_sovelletaan) jonoon(k, false, e.target);
    };
    modaali.addEventListener("input", arvoMuuttui);
    modaali.addEventListener("change", arvoMuuttui);
    modaali.addEventListener("keyup", kursoriLiikkui);
    modaali.addEventListener("click", kursoriLiikkui);
    modaali.addEventListener("focusin", kursoriLiikkui);
    modaali.addEventListener("scroll", () => piirraKursorit(), true);
  }

  // --- Muokkaajien pallurat ja kursorit modaalissa ---

  function sisalto() {
    return _modaali.querySelector(".modaali-sisalto") || _modaali;
  }

  function piirraMuokkaajat() {
    let rivi = _modaali.querySelector(".lomake-muokkaajat");
    if (!rivi) {
      rivi = document.createElement("div");
      rivi.className = "lomake-muokkaajat";
      (sisalto().querySelector("h2") || sisalto().firstChild).after(rivi);
    }
    rivi.innerHTML = "";
    const muut = _muokkaajat.filter((m) => m.id !== omaId() && m.profiili);
    if (!muut.length) return;
    rivi.append("Muut käyttäjät täällä: ");
    for (const m of muut) {
      const c = window.luoPallura(m, 16);
      const nimi = document.createElement("span");
      nimi.className = "lomake-muokkaaja";
      nimi.append(c, ` ${m.nimimerkki || "?"}`);
      rivi.append(nimi);
    }
  }

  // Kursorin pikselisijainti kentän sisällä peilielementillä (sama tyyli, teksti kursoriin asti).
  function kursoriPiste(el, sijainti) {
    const tyyli = getComputedStyle(el);
    const peili = document.createElement("div");
    const monirivi = el.tagName === "TEXTAREA";
    peili.style.cssText = `position:absolute;top:-9999px;left:-9999px;visibility:hidden;
      white-space:${monirivi ? "pre-wrap" : "pre"};word-wrap:break-word;overflow:hidden;
      width:${el.offsetWidth}px;font:${tyyli.font};padding:${tyyli.padding};border:${tyyli.border};
      box-sizing:${tyyli.boxSizing};line-height:${tyyli.lineHeight};letter-spacing:${tyyli.letterSpacing};`;
    peili.textContent = el.value.slice(0, sijainti);
    const merkki = document.createElement("span");
    merkki.textContent = "|";
    peili.appendChild(merkki);
    document.body.appendChild(peili);
    const [p, m] = [peili.getBoundingClientRect(), merkki.getBoundingClientRect()];
    document.body.removeChild(peili);
    return { x: m.left - p.left - el.scrollLeft, y: m.top - p.top - el.scrollTop, korkeus: m.height };
  }

  function piirraKursorit() {
    if (!_modaali) return;
    let kerros = sisalto().querySelector(":scope > .lomake-kursorit");
    if (!kerros) {
      kerros = document.createElement("div");
      kerros.className = "lomake-kursorit";
      sisalto().appendChild(kerros);
    }
    kerros.innerHTML = "";
    const pohja = kerros.getBoundingClientRect();
    for (const m of _muokkaajat) {
      if (m.id === omaId() || !m.kentta || !m.profiili) continue;
      const el = _modaali.querySelector(`[data-jaettu="${CSS.escape(m.kentta)}"]`);
      if (!el || !(el.tagName === "TEXTAREA" || ["text", "email", "search"].includes(el.type))) continue;
      const r = el.getBoundingClientRect();
      const p = kursoriPiste(el, m.kursori || 0);
      if (p.y < 0 || p.y > r.height - 4 || p.x < 0 || p.x > r.width) continue;  // vieritetty näkyvistä
      const merkki = document.createElement("div");
      merkki.className = "lomake-kursori";
      merkki.title = m.nimimerkki || "?";
      merkki.style.cssText = `left:${r.left - pohja.left + p.x}px;top:${r.top - pohja.top + p.y}px;`
        + `height:${p.korkeus || 16}px;border-color:${m.profiili.taustavari || "#c0392b"}`;
      merkki.appendChild(window.luoPallura(m, 12));
      kerros.appendChild(merkki);
    }
  }

  // --- Julkinen rajapinta ---

  function liity() {
    const arvot = {};
    for (const k of kentat()) arvot[k] = lue(k);
    laheta({ tyyppi: "lomake-liity", avain: _avain, arvot });
  }

  window.avaaLomakesessio = function (avain, modaali, { erikois = {}, tallennettu = null } = {}) {
    if (_avain) window.suljeLomakesessio();
    _avain = avain; _modaali = modaali; _erikois = erikois; _tallennettu = tallennettu;
    _alustettu = false; _aloittaja = false; _muokkaajat = []; _odottava = null;
    kuuntele(modaali);
    liity();
    piirraMuokkaajat();
    window.lahetaTilaNyt?.();
  };

  window.suljeLomakesessio = function () {
    if (!_avain) return;
    clearTimeout(_ajastin);
    _odottava = null;
    laheta({ tyyppi: "lomake-poistu", avain: _avain });
    _muokkaajat = [];
    piirraMuokkaajat();
    piirraKursorit();
    _avain = null;
    window.lahetaTilaNyt?.();
  };

  // Tallennus onnistui → muiden saman lomakkeen modaalit sulkeutuvat ja päivittyvät.
  window.lomakeTallennettu = () => { if (_avain) laheta({ tyyppi: "lomake-tallennettu", avain: _avain }); };
  // Erikoiskenttä muuttui (esim. listan kohta lisättiin/poistettiin).
  window.lomakeMuuttui = (kentta) => { if (_avain && !_sovelletaan) jonoon(kentta, true, null); };
  // Oliko lomake tämän käyttäjän alustama (nimi/sähköposti ovat hänen omansa)?
  window.lomakeOlenAloittaja = () => !_avain || _aloittaja;
  window.omaLomake = () => _avain;
  // WebSocket yhdisti uudelleen → palvelin ei muista jäsenyyttä.
  window.lomakeUudelleenliity = () => { if (_avain) { _alustettu = false; liity(); } };

  window.lomakeKuuntelija = function (viesti) {
    if (!_avain || viesti.avain !== _avain) return;
    if (viesti.tyyppi === "lomake-tallennettu") { _tallennettu?.(viesti); return; }
    _muokkaajat = viesti.muokkaajat || [];
    if (!_alustettu) {
      // Ensimmäinen vastaus: palvelimen arvot (ensimmäisen avaajan) kaikkiin kenttiin.
      _aloittaja = _muokkaajat.length === 1;
      for (const [k, v] of Object.entries(viesti.arvot || {})) aseta(k, v);
      _alustettu = true;
    } else if (viesti.lahettaja && viesti.lahettaja !== omaId()) {
      // Toisen muutos: vain hänen muuttamansa kenttä (ei ylikirjoiteta omaa kesken olevaa kirjoitusta).
      const kentta = _muokkaajat.find((m) => m.id === viesti.lahettaja)?.kentta;
      if (kentta && kentta in (viesti.arvot || {})) aseta(kentta, viesti.arvot[kentta]);
    }
    piirraMuokkaajat();
    piirraKursorit();
  };

  // Muille näkyvä indikaatio: pallurat napin alle + sykkivä korostus jokaiseen
  // nappiin, jonka lomakkeen joku muu on avannut (kaikissa suodatetuissa näkymissä).
  window.paivitaLomakePallurat = function (muut) {
    const perAvain = {};
    for (const k of muut) if (k.lomake && k.profiili) (perAvain[k.lomake] ||= []).push(k);
    document.querySelectorAll("[data-lomake]").forEach((nappi) => {
      const kayttajat = perAvain[nappi.dataset.lomake] || [];
      const tunniste = JSON.stringify(kayttajat.map((k) => [k.id, k.taso, k.nimimerkki, k.profiili]));
      if (nappi.dataset.lomakeTila === tunniste) return;
      nappi.dataset.lomakeTila = tunniste;
      nappi.classList.toggle("lomake-auki", kayttajat.length > 0);
      let rivi = nappi.nextElementSibling?.classList.contains("lomake-pallurat") ? nappi.nextElementSibling : null;
      if (!kayttajat.length) { rivi?.remove(); return; }
      if (!rivi) {
        rivi = document.createElement("span");
        rivi.className = "lomake-pallurat";
        nappi.after(rivi);
      }
      rivi.innerHTML = "";
      for (const k of kayttajat) {
        const c = window.luoPallura(k, 10);
        c.title = `${k.nimimerkki || "?"} muokkaa tätä`;
        rivi.appendChild(c);
      }
    });
  };
}
