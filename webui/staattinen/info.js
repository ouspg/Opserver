"use strict";

// Opserver-infomodaali: logon klikkaus avaa Opserver.md:n infosivun ja ajossa olevan version.
{

// Markdownin perusosajoukko (otsikot, kappaleet, listat, **lihavointi**, *kursiivi*, `koodi`,
// [linkki](https://…), ---). Teksti escapoidaan ensin, joten HTML ei koskaan suoritu.
// ponytail: ei taulukoita/sisäkkäisiä listoja/koodilohkoja — kirjasto, jos infosivu tarvitsee niitä.
function markdownHtml(md) {
  const rivinsisainen = (s) => escapeHtml(s)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>")
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  const html = [];
  let kappale = [], lista = null;
  const sulje = () => {
    if (kappale.length) html.push(`<p>${rivinsisainen(kappale.join(" "))}</p>`);
    if (lista) html.push(`</${lista}>`);
    kappale = []; lista = null;
  };
  for (const rivi of md.split("\n")) {
    let m;
    if (!rivi.trim()) {
      sulje();
    } else if ((m = /^(#{1,4})\s+(.*)$/.exec(rivi))) {
      sulje();
      html.push(`<h${m[1].length}>${rivinsisainen(m[2])}</h${m[1].length}>`);
    } else if (/^\s*-{3,}\s*$/.test(rivi)) {
      sulje();
      html.push("<hr>");
    } else if ((m = /^\s*([-*]|\d+\.)\s+(.*)$/.exec(rivi))) {
      const tyyppi = /\d/.test(m[1]) ? "ol" : "ul";
      if (lista !== tyyppi) { sulje(); html.push(`<${tyyppi}>`); lista = tyyppi; }
      html.push(`<li>${rivinsisainen(m[2])}</li>`);
    } else if (lista) {  // listakohdan jatkorivi
      html[html.length - 1] = html[html.length - 1].replace(/<\/li>$/, ` ${rivinsisainen(rivi.trim())}</li>`);
    } else {
      kappale.push(rivi.trim());
    }
  }
  sulje();
  return html.join("\n");
}

const modaali = document.getElementById("info-modaali");
let ladattu = false;

async function avaaInfo() {
  modaali.classList.remove("piilotettu");
  if (ladattu) return;
  const teksti = document.getElementById("info-teksti");
  const versio = document.getElementById("info-versio");
  teksti.innerHTML = '<p class="tulossa">Ladataan…</p>';
  try {
    const data = await haeJson("/api/info");
    teksti.innerHTML = markdownHtml(data.teksti);
    const commit = escapeHtml(data.versio);
    const linkki = /^[0-9a-f]{7,40}$/.test(data.versio)
      ? `<a href="https://github.com/ouspg/Opserver/commit/${commit}" target="_blank" rel="noopener">${commit}</a>`
      : commit;
    versio.innerHTML = `Versio ${linkki}${data.paiva ? ` · ${escapeHtml(data.paiva)}` : ""}`;
    ladattu = true;
  } catch (_) {
    teksti.innerHTML = '<p class="tulossa">Tietojen lataus epäonnistui — sulje ja yritä uudelleen.</p>';
  }
}

document.getElementById("info-nappi").addEventListener("click", avaaInfo);
kytkeSulkeminen(modaali, () => modaali.classList.add("piilotettu"));
window.markdownHtml = markdownHtml;  // testattavuus (selaintesti)
}
