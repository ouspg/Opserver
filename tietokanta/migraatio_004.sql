-- Migraatio 004: Lisätään Malli-sarake Kurssiluokitus- ja Vastaukset-tauluihin.
-- Tallentaa sen LLM-mallin nimen, jolla päätös tai vastaus on tuotettu.
ALTER TABLE Kurssiluokitus ADD COLUMN Malli VARCHAR(120) NULL;
ALTER TABLE Vastaukset      ADD COLUMN Malli VARCHAR(120) NULL;
