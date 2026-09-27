-- Migraatio 023: LLM:n luokittelupäätöksen hyväksyntä (HITL-A, peukutus).
--
-- KayttajaNimi IS NULL → LLM-päätöstä ei ole hyväksytty. Hyväksyntä on vain
-- visuaalinen: HitlKorjaus-ohitus toimii kuten ennenkin. LLM:n uusi päätös
-- (aseta_luokitus) nollaa hyväksynnän.
--
-- Yksi lause: tuotannossa sarakkeet lisättiin käsin ennen migraatiota, jolloin
-- lause kaatuu "Duplicate column" -virheeseen ja runner merkitsee tämän ajetuksi.
ALTER TABLE Kurssiluokitus
    ADD COLUMN KayttajaNimi VARCHAR(255) DEFAULT NULL,
    ADD COLUMN Sahkoposti   VARCHAR(255) DEFAULT NULL;
