-- Migraatio 009: Kehotetiiviste LLM-tuloksiin idempotenttiutta varten.
-- Tallentaa SHA-256-tiivisteen kehotteesta (+ kysymysmäärittelystä), jolla
-- tulos tuotettiin. Ajossa voidaan ohittaa tulokset joiden tiiviste täsmää
-- nykyiseen kehotteeseen ja ajaa uudelleen vain muuttuneet — säästää LLM-kuluja.
-- HUOM: ALTER saattaa epäonnistua jos sarake on jo olemassa — turvallista ohittaa.
ALTER TABLE Kurssiluokitus
    ADD COLUMN Kehotetiiviste VARCHAR(64) AFTER Malli;

ALTER TABLE Vastaukset
    ADD COLUMN Kehotetiiviste VARCHAR(64) AFTER Malli;
