"use strict";

// Välilehtien vaihto
function vaihdaValilehti(nimi) {
  document.querySelectorAll("#valilehdet button").forEach((nappi) => {
    nappi.classList.toggle("aktiivinen", nappi.dataset.valilehti === nimi);
  });
  document.querySelectorAll(".nakyma").forEach((nakyma) => {
    nakyma.classList.toggle("aktiivinen", nakyma.id === nimi);
  });
}

document.querySelectorAll("#valilehdet button").forEach((nappi) => {
  nappi.addEventListener("click", () => vaihdaValilehti(nappi.dataset.valilehti));
});

// Korkeakoulut-välilehti
async function lataaKorkeakoulut() {
  const runko = document.getElementById("korkeakoulut-rungot");
  const vastaus = await fetch("/api/korkeakoulut");
  const koulut = await vastaus.json();
  runko.innerHTML = "";
  if (koulut.length === 0) {
    runko.innerHTML = '<tr><td colspan="3">Ei korkeakouluja.</td></tr>';
    return;
  }
  for (const k of koulut) {
    const rivi = document.createElement("tr");
    rivi.innerHTML = `<td>${k.KouluNimi}</td><td>${k.OpsTyyppi}</td><td>${k.OpsOsoite}</td>`;
    runko.appendChild(rivi);
  }
}

lataaKorkeakoulut();
