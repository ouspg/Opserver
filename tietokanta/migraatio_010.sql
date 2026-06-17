-- Lisää 'lista'-kysymystyyppi: LLM palauttaa JSON-taulukon erillisiä kohtia
-- (esim. esitiedot, oppimistavoitteet) vapaan tekstin sijaan. Kohdat
-- tallennetaan rakenteellisesti Vastaukset.Lista-sarakkeeseen, perustelu
-- Vastaus-sarakkeeseen — kuten luokittelu/asteikko-tyypeillä.

ALTER TABLE Kysymykset
  MODIFY COLUMN Luokittelu ENUM('vapaa_teksti', 'luokittelu', 'asteikko', 'lista')
             NOT NULL DEFAULT 'vapaa_teksti';

ALTER TABLE Vastaukset
  ADD COLUMN Lista JSON NULL AFTER Luokka;
