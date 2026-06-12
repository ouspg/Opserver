-- Migraatio 003: Muutetaan Taso ENUMista VARCHAR(30) ja Opintopisteet FLOATista VARCHAR(30).
-- Tavoitteena nähdä raakadata opinto-oppaista ennen normalisointia.
ALTER TABLE Kurssi
    MODIFY COLUMN Taso          VARCHAR(30),
    MODIFY COLUMN Opintopisteet VARCHAR(30);
