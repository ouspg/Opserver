-- Migraatio 018: RaporttiTuoreus-taulu — raportin tuoreustarkistus taustalle.
-- Lähdeaineiston tiivisteen (raporttitiiviste) uudelleenlaskenta on raskas
-- (per-yliopisto-tilastot + kaikki vastaukset + kommentit etäkannasta), joten
-- sitä ei lasketa synkronisesti joka status-katselulla. Sen sijaan viimeksi
-- laskettu tiiviste ja laskenta-aika tallennetaan tähän; "Näytä tilanne" lukee
-- tallennetun tuloksen halvalla ja vertaa sitä generoinnin tiivisteeseen
-- (RaporttiOsio.Laskentatiiviste). Raskas laskenta ajetaan taustalla.
--   Signatuuri  = lähdeaineiston tiiviste viimeisimmän tarkistuksen hetkellä
--   Tarkistettu = milloin tiiviste viimeksi laskettu (näytetään käyttäjälle)
CREATE TABLE IF NOT EXISTS RaporttiTuoreus (
    TID         INT          NOT NULL PRIMARY KEY,
    Signatuuri  VARCHAR(64)  NULL,
    Tarkistettu DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (TID) REFERENCES Tutkimus(TID) ON DELETE CASCADE
);
