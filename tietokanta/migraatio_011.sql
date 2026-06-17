-- Lisää korkeakoulun API-origin-osoite, jonka "Lisää korkeakoulu" -toiminto
-- selvittää opinto-opasjärjestelmästä (Peppi: frontendin julistama backendUrl;
-- Sisu: sama origin kuin opinto-opas). Haku lukee kohdepalvelintiedon tästä
-- sarakkeesta — ei kovakoodattuja per-korkeakoulu-osoitteita koodissa.

ALTER TABLE Korkeakoulu
  ADD COLUMN ApiOsoite TEXT NULL AFTER OpsOsoite;
