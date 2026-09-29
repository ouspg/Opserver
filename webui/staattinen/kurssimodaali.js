"use strict";

// Kurssin tiedot -modaali (Peppi/Sisu-kuvaukset).

const KIELI_SUOMI = {
  "urn:code:language:fi": "suomi", "urn:code:language:en": "englanti",
  "urn:code:language:sv": "ruotsi",
};

function _monikielinen(arvo) {
  if (arvo && typeof arvo === "object") return arvo.fi || arvo.en || "";
  return arvo || "";
}

// Peppi: contentList-rakenne nimetyillä osioilla
function peppiKuvausOsat(data) {
  return (data.contentList || [])
    .filter((o) => (o.content?.valueFi || "").trim())
    .map((o) => ({
      otsikko: o.title?.valueFi || "",
      sisalto: puhdistaHtml((o.content?.valueFi || "").replace(/\n/g, "<br>")),
    }));
}

// Sisu: KORI-rajapinnan kentät kartoitettuna samoihin osioihin kuin Peppi
function sisuKuvausOsat(data) {
  const osat = [];
  const lisaa = (otsikko, sisalto) => {
    if (sisalto && sisalto.trim()) osat.push({ otsikko, sisalto: puhdistaHtml(sisalto) });
  };
  lisaa("Lyhyt kuvaus", _monikielinen(data.tweetText));
  lisaa("Osaamistavoitteet", _monikielinen(data.outcomes));
  lisaa("Sisältö", _monikielinen(data.content));
  lisaa(
    "Suoritustavat",
    (data.completionMethods || []).map((c) => _monikielinen(c.description)).filter(Boolean).join("<br>"),
  );
  lisaa("Esitietovaatimukset", _monikielinen(data.prerequisites));
  lisaa("Oppimateriaalit", _monikielinen(data.learningMaterial));
  lisaa(
    "Kurssikirjallisuus",
    (data.literature || []).map((l) => l.name).filter(Boolean).map((n) => `• ${escapeHtml(n)}`).join("<br>"),
  );
  const kielet = (data.possibleAttainmentLanguages || []).map((k) => KIELI_SUOMI[k] || k).join(", ");
  lisaa("Opetuskieli", escapeHtml(kielet));
  lisaa("Lisätiedot", _monikielinen(data.additional));
  return osat;
}

async function avaaModaali(kid) {
  const kurssi = await haeJson(`/api/kurssit/${kid}`);
  const opsUrl = kurssiUrl(kurssi);
  const nimi = escapeHtml(kurssi.KurssiNimi);
  const nimiHtml = opsUrl
    ? `<a href="${escapeHtml(opsUrl)}" target="_blank" rel="noopener">${nimi}</a>`
    : nimi;
  document.getElementById("modaali-otsikko").innerHTML =
    `${nimiHtml} (${escapeHtml(kurssi.Koodi || "—")})`;

  const koulu = kaikki_koulut.find((k) => k.KKID === kurssi.KKID);
  let kuvaus = "—";
  if (kurssi.OpsKuvaus) {
    try {
      const data = JSON.parse(kurssi.OpsKuvaus);
      const osat = koulu?.OpsTyyppi === "Sisu" ? sisuKuvausOsat(data) : peppiKuvausOsat(data);
      kuvaus = osat.length
        ? osat.map((o) => `<strong>${escapeHtml(o.otsikko)}</strong><br>${o.sisalto}`).join("<hr>")
        : "—";
    } catch {
      kuvaus = tekstiHtml(kurssi.OpsKuvaus);
    }
  }

  document.getElementById("modaali-teksti").innerHTML = `
    <table class="modaali-meta">
      <tr><th>Taso</th><td>${tasoTeksti(kurssi.Taso)}</td></tr>
      <tr><th>Oppiaine</th><td>${escapeHtml(kurssi.Oppiaine || "—")}</td></tr>
      <tr><th>Opintopisteet</th><td>${escapeHtml(kurssi.Opintopisteet ?? "—")}</td></tr>
      <tr><th>Opetusvuosi</th><td>${escapeHtml(kurssi.Opetusvuosi)}</td></tr>
    </table>
    <div class="ops-kuvaus">${kuvaus}</div>`;
  document.getElementById("modaali").classList.remove("piilotettu");
}

kytkeSulkeminen(document.getElementById("modaali"),
                () => document.getElementById("modaali").classList.add("piilotettu"));
