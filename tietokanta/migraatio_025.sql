-- Migraatio 025: OpsKuvaus omaan tauluunsa (KurssiKuvaus).
--
-- Kuvaus (mediumtext, ka. 6,3 kB) mahtui InnoDB-riville, joten Kurssi-taulu oli
-- ~250 MB eikä mahtunut puskuriin (128 MB): jokainen Kurssin läpikäyvä kysely
-- (tilamäärät, odottaa/hylätty-listat, tasot) luki kuvaukset levyltä — tuotannossa
-- 9–22 s. Ilman kuvausta Kurssi on muutamia megatavuja; kuvaus haetaan vain
-- kurssinäkymään ja LLM-kutsuihin (mallit._KUVAUS_JOIN).
--
-- Idempotentti myös ilman _migraatiot-merkintää: tuoreessa asennuksessa
-- (alustus.sql) saraketta ei ole → siirto ja poisto ohitetaan.
CREATE TABLE IF NOT EXISTS KurssiKuvaus (
    KID       INT NOT NULL,
    OpsKuvaus MEDIUMTEXT,
    PRIMARY KEY (KID),
    CONSTRAINT KurssiKuvaus_ibfk_1 FOREIGN KEY (KID) REFERENCES Kurssi (KID) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

SET @on_sarake = (SELECT COUNT(*) FROM information_schema.COLUMNS
                  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Kurssi' AND COLUMN_NAME = 'OpsKuvaus');

SET @sql = IF(@on_sarake,
    'INSERT INTO KurssiKuvaus (KID, OpsKuvaus) SELECT KID, OpsKuvaus FROM Kurssi
     ON DUPLICATE KEY UPDATE OpsKuvaus = VALUES(OpsKuvaus)',
    'DO 0');
PREPARE lause FROM @sql; EXECUTE lause; DEALLOCATE PREPARE lause;

-- ALGORITHM=INPLACE rakentaa taulun uudelleen: oletus (INSTANT) vain piilottaisi
-- sarakkeen, ja kuvaukset jäisivät vanhoille riveille viemään tilaa.
SET @sql = IF(@on_sarake, 'ALTER TABLE Kurssi DROP COLUMN OpsKuvaus, ALGORITHM=INPLACE', 'DO 0');
PREPARE lause FROM @sql; EXECUTE lause; DEALLOCATE PREPARE lause;
