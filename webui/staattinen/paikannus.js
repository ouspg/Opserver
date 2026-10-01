"use strict";

// Kurssin paikannus kurssilistoihin: "Paikanna kurssi [ ]" + autocomplete (enintään 10).
// Näkymä antaa: hae(teksti) → Promise<[kurssi]> ({ KID, KurssiNimi, Koodi, KKID }),
// siirry(kurssi) → Promise (esim. oikealle sivulle) ja runko (tbody, rivit data-kid).
// Tab/Enter valitsee korostetun (oletus ensimmäinen), nuolet vaihtavat, Esc sulkee.
// Valinnan jälkeen rivi vieritetään näkyviin ja korostetaan hetkeksi.
{
  const VIIVE_MS = 150;

  function lisatieto(k) {
    const koulu = kaikki_koulut.find((x) => x.KKID === k.KKID);
    return [k.Koodi, koulu && koulunLyhenne(koulu)].filter(Boolean).join(" · ");
  }

  window.luoPaikannin = function (sailio, { hae, siirry, runko }) {
    sailio.innerHTML = `<label>Paikanna kurssi <span class="paikannus-kentta">
        <input type="text" autocomplete="off" spellcheck="false" role="combobox"
          aria-autocomplete="list" aria-expanded="false">
        <ul class="paikannus-lista piilotettu" role="listbox"></ul></span></label>`;
    const kentta = sailio.querySelector("input"), lista = sailio.querySelector("ul");
    let osumat = [], valittu = 0, hakuNro = 0, ajastin = null;

    const piirra = () => {
      lista.innerHTML = osumat.map((k, i) =>
        `<li role="option" data-i="${i}"${i === valittu ? ' class="valittu" aria-selected="true"' : ""}>`
        + `${escapeHtml(k.KurssiNimi)} <span class="paikannus-lisa">${escapeHtml(lisatieto(k))}</span></li>`).join("");
      lista.classList.toggle("piilotettu", !osumat.length);
      kentta.setAttribute("aria-expanded", String(osumat.length > 0));
    };
    const sulje = () => { osumat = []; piirra(); };

    // Uusin haku voittaa: hitaan vastauksen myöhästyminen ei korvaa uudemman tulosta.
    async function etsi() {
      clearTimeout(ajastin);
      ajastin = null;
      const teksti = kentta.value.trim(), nro = ++hakuNro;
      const tulos = teksti ? await hae(teksti).catch(() => []) : [];
      if (nro !== hakuNro) return null;
      osumat = tulos; valittu = 0; piirra();
      return osumat;
    }

    async function valitse(k) {
      sulje();
      kentta.value = k.KurssiNimi;
      await siirry(k);
      const rivi = await odotaEhtoa(() => runko.querySelector(`tr[data-kid="${k.KID}"]`));
      if (!rivi) return;
      rivi.scrollIntoView({ block: "center" });
      rivi.classList.remove("paikannettu");
      void rivi.offsetWidth;  // animaatio alusta, jos sama rivi valitaan uudelleen
      rivi.classList.add("paikannettu");
    }

    kentta.addEventListener("input", () => {
      clearTimeout(ajastin);
      ajastin = setTimeout(etsi, VIIVE_MS);
    });
    kentta.addEventListener("keydown", async (e) => {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        if (!osumat.length) return;
        e.preventDefault();
        valittu = (valittu + (e.key === "ArrowDown" ? 1 : osumat.length - 1)) % osumat.length;
        piirra();
      } else if (e.key === "Enter" || (e.key === "Tab" && !e.shiftKey && kentta.value.trim())) {
        e.preventDefault();
        // Kirjoitettu juuri ennen Enteriä (viive kesken): haetaan heti.
        const tulos = ajastin || !osumat.length ? await etsi() : osumat;
        if (tulos?.length) valitse(tulos[Math.min(valittu, tulos.length - 1)]);
      } else if (e.key === "Escape") {
        sulje();
      }
    });
    lista.addEventListener("mousedown", (e) => {  // mousedown: ennen kentän blur-sulkemista
      const li = e.target.closest("li");
      if (!li) return;
      e.preventDefault();
      valitse(osumat[+li.dataset.i]);
    });
    kentta.addEventListener("blur", sulje);
  };
}
