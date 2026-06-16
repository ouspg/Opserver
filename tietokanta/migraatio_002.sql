-- Migraatio 002: Laajennetaan Oppiaine-kenttä TEXT:ksi (VARCHAR(255) liian lyhyt osalle Peppi-dataa).
ALTER TABLE Kurssi MODIFY COLUMN Oppiaine TEXT;
