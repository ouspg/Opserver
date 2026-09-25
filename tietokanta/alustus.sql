-- Perusskeema — generoitu mysqldump --no-data:lla geopalvelin1:n migratoidusta
-- kannasta 2026-09-22 (squash migraatioista 001-019, ks. tietokanta/migraatio_*.sql).
-- FOREIGN_KEY_CHECKS=0: taulut eivät ole FK-riippuvuusjärjestyksessä (mysqldumpin oletus).
SET FOREIGN_KEY_CHECKS=0;


CREATE TABLE IF NOT EXISTS `HitlKorjaus` (
  `HID` int NOT NULL AUTO_INCREMENT,
  `TID` int NOT NULL,
  `KID` int NOT NULL,
  `UusiTila` tinyint(1) NOT NULL,
  `Perustelu` text NOT NULL,
  `KayttajaNimi` varchar(255) NOT NULL,
  `Sahkoposti` varchar(255) NOT NULL,
  `Aikaleima` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `Juurisyy` varchar(32) DEFAULT NULL,
  PRIMARY KEY (`HID`),
  KEY `TID` (`TID`),
  KEY `KID` (`KID`),
  CONSTRAINT `HitlKorjaus_ibfk_1` FOREIGN KEY (`TID`) REFERENCES `Tutkimus` (`TID`) ON DELETE CASCADE,
  CONSTRAINT `HitlKorjaus_ibfk_2` FOREIGN KEY (`KID`) REFERENCES `Kurssi` (`KID`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE IF NOT EXISTS `Korkeakoulu` (
  `KKID` int NOT NULL AUTO_INCREMENT,
  `KouluNimi` varchar(255) NOT NULL,
  `OpsOsoite` text NOT NULL,
  `ApiOsoite` text,
  `OpsTyyppi` enum('Peppi','Sisu') NOT NULL,
  PRIMARY KEY (`KKID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE IF NOT EXISTS `Kurssi` (
  `KID` int NOT NULL AUTO_INCREMENT,
  `KKID` int NOT NULL,
  `LahdeId` varchar(50) DEFAULT NULL,
  `Koodi` varchar(50) DEFAULT NULL,
  `KurssiNimi` varchar(255) NOT NULL,
  `Taso` varchar(30) DEFAULT NULL,
  `Oppiaine` text,
  `Opintopisteet` varchar(30) DEFAULT NULL,
  `Opetusvuosi` varchar(20) NOT NULL DEFAULT '',
  `OpsKuvaus` mediumtext,
  PRIMARY KEY (`KID`),
  UNIQUE KEY `uniikki_lahde_vuosi` (`KKID`,`LahdeId`,`Opetusvuosi`),
  CONSTRAINT `Kurssi_ibfk_1` FOREIGN KEY (`KKID`) REFERENCES `Korkeakoulu` (`KKID`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE IF NOT EXISTS `Kurssiarviointi` (
  `KAID` int NOT NULL AUTO_INCREMENT,
  `TID` int NOT NULL,
  `KID` int NOT NULL,
  `Arviointi` text,
  `Perustelu` text,
  PRIMARY KEY (`KAID`),
  UNIQUE KEY `uniikki_tid_kid` (`TID`,`KID`),
  KEY `KID` (`KID`),
  CONSTRAINT `Kurssiarviointi_ibfk_1` FOREIGN KEY (`TID`) REFERENCES `Tutkimus` (`TID`) ON DELETE CASCADE,
  CONSTRAINT `Kurssiarviointi_ibfk_2` FOREIGN KEY (`KID`) REFERENCES `Kurssi` (`KID`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE IF NOT EXISTS `Kurssiluokitus` (
  `KLID` int NOT NULL AUTO_INCREMENT,
  `TID` int NOT NULL,
  `KID` int NOT NULL,
  `Mukana` tinyint(1) DEFAULT NULL,
  `Luokitteluperuste` text,
  `Malli` varchar(120) DEFAULT NULL,
  `Kehotetiiviste` varchar(64) DEFAULT NULL,
  PRIMARY KEY (`KLID`),
  UNIQUE KEY `uniikki_tid_kid` (`TID`,`KID`),
  KEY `KID` (`KID`),
  CONSTRAINT `Kurssiluokitus_ibfk_1` FOREIGN KEY (`TID`) REFERENCES `Tutkimus` (`TID`) ON DELETE CASCADE,
  CONSTRAINT `Kurssiluokitus_ibfk_2` FOREIGN KEY (`KID`) REFERENCES `Kurssi` (`KID`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE IF NOT EXISTS `Kurssiluokitus_testi` (
  `TLID` int NOT NULL AUTO_INCREMENT,
  `Ajo` varchar(32) NOT NULL,
  `Erakoko` int NOT NULL,
  `TID` int NOT NULL,
  `KID` int NOT NULL,
  `Mukana` tinyint(1) DEFAULT NULL,
  `Luokitteluperuste` text,
  `Malli` varchar(120) DEFAULT NULL,
  `Kehotetiiviste` varchar(64) DEFAULT NULL,
  `Luotu` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`TLID`),
  UNIQUE KEY `uniikki_ajo_tid_kid` (`Ajo`,`TID`,`KID`),
  KEY `KID` (`KID`),
  KEY `idx_tid_ajo` (`TID`,`Ajo`),
  CONSTRAINT `Kurssiluokitus_testi_ibfk_1` FOREIGN KEY (`TID`) REFERENCES `Tutkimus` (`TID`) ON DELETE CASCADE,
  CONSTRAINT `Kurssiluokitus_testi_ibfk_2` FOREIGN KEY (`KID`) REFERENCES `Kurssi` (`KID`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE IF NOT EXISTS `Kysymykset` (
  `KysID` int NOT NULL AUTO_INCREMENT,
  `TID` int NOT NULL,
  `Kysymys` text NOT NULL,
  `Luokittelu` enum('vapaa_teksti','luokittelu','asteikko','lista') NOT NULL DEFAULT 'vapaa_teksti',
  `LuokitteluMaarittely` json DEFAULT NULL,
  PRIMARY KEY (`KysID`),
  KEY `Kysymykset_ibfk_1` (`TID`),
  CONSTRAINT `Kysymykset_ibfk_1` FOREIGN KEY (`TID`) REFERENCES `Tutkimus` (`TID`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE IF NOT EXISTS `RaporttiOsio` (
  `RID` int NOT NULL AUTO_INCREMENT,
  `TID` int NOT NULL,
  `OsioAvain` varchar(50) NOT NULL,
  `Teksti` mediumtext NOT NULL,
  `Aikaleima` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `Laskentatiiviste` varchar(64) DEFAULT NULL,
  PRIMARY KEY (`RID`),
  UNIQUE KEY `uniikki_tid_osio` (`TID`,`OsioAvain`),
  CONSTRAINT `RaporttiOsio_ibfk_1` FOREIGN KEY (`TID`) REFERENCES `Tutkimus` (`TID`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE IF NOT EXISTS `RaporttiTuoreus` (
  `TID` int NOT NULL,
  `Signatuuri` varchar(64) DEFAULT NULL,
  `Tarkistettu` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`TID`),
  CONSTRAINT `RaporttiTuoreus_ibfk_1` FOREIGN KEY (`TID`) REFERENCES `Tutkimus` (`TID`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE IF NOT EXISTS `Tutkimus` (
  `TID` int NOT NULL AUTO_INCREMENT,
  `LuokittelunNimi` varchar(255) NOT NULL,
  `Slug` varchar(100) NOT NULL DEFAULT '',
  `Lukuvuosi` varchar(9) DEFAULT NULL,
  `Verkkosivu` text,
  `Luokittelukehote` text NOT NULL,
  `Tasorajaus` varchar(255) DEFAULT NULL,
  `Oppiainerajaus` text,
  `Arviointikehote` text NOT NULL,
  `Raportointikehote` text,
  PRIMARY KEY (`TID`),
  UNIQUE KEY `uniikki_slug` (`Slug`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE IF NOT EXISTS `TutkimusKorkeakoulu` (
  `TID` int NOT NULL,
  `KKID` int NOT NULL,
  PRIMARY KEY (`TID`,`KKID`),
  KEY `KKID` (`KKID`),
  CONSTRAINT `TutkimusKorkeakoulu_ibfk_1` FOREIGN KEY (`TID`) REFERENCES `Tutkimus` (`TID`) ON DELETE CASCADE,
  CONSTRAINT `TutkimusKorkeakoulu_ibfk_2` FOREIGN KEY (`KKID`) REFERENCES `Korkeakoulu` (`KKID`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE IF NOT EXISTS `Vastaukset` (
  `VasID` int NOT NULL AUTO_INCREMENT,
  `KysID` int NOT NULL,
  `KID` int NOT NULL,
  `Vastaus` text,
  `Malli` varchar(120) DEFAULT NULL,
  `Kehotetiiviste` varchar(64) DEFAULT NULL,
  `Pisteet` float DEFAULT NULL,
  `Luokka` varchar(100) DEFAULT NULL,
  `Lista` json DEFAULT NULL,
  `TID` int NOT NULL,
  `KayttajaNimi` varchar(255) NOT NULL DEFAULT '',
  `Sahkoposti` varchar(255) NOT NULL DEFAULT '',
  `Aikaleima` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `Juurisyy` varchar(32) DEFAULT NULL,
  PRIMARY KEY (`VasID`),
  UNIQUE KEY `uniikki_kys_kid_kayttaja` (`KysID`,`KID`,`KayttajaNimi`),
  KEY `Vastaukset_ibfk_2` (`KID`),
  KEY `idx_tid` (`TID`),
  CONSTRAINT `Vastaukset_ibfk_3` FOREIGN KEY (`TID`) REFERENCES `Tutkimus` (`TID`) ON DELETE CASCADE,
  CONSTRAINT `Vastaukset_ibfk_1` FOREIGN KEY (`KysID`) REFERENCES `Kysymykset` (`KysID`) ON DELETE CASCADE,
  CONSTRAINT `Vastaukset_ibfk_2` FOREIGN KEY (`KID`) REFERENCES `Kurssi` (`KID`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE IF NOT EXISTS `Vastaukset_testi` (
  `VTID` int NOT NULL AUTO_INCREMENT,
  `Ajo` varchar(32) NOT NULL,
  `Erakoko` int NOT NULL,
  `TID` int NOT NULL,
  `KysID` int NOT NULL,
  `KID` int NOT NULL,
  `Vastaus` text,
  `Malli` varchar(120) DEFAULT NULL,
  `Kehotetiiviste` varchar(64) DEFAULT NULL,
  `Pisteet` float DEFAULT NULL,
  `Luokka` varchar(100) DEFAULT NULL,
  `Lista` json DEFAULT NULL,
  `Luotu` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`VTID`),
  UNIQUE KEY `uniikki_ajo_kys_kid` (`Ajo`,`KysID`,`KID`),
  KEY `KysID` (`KysID`),
  KEY `KID` (`KID`),
  KEY `idx_tid_ajo` (`TID`,`Ajo`),
  CONSTRAINT `Vastaukset_testi_ibfk_1` FOREIGN KEY (`TID`) REFERENCES `Tutkimus` (`TID`) ON DELETE CASCADE,
  CONSTRAINT `Vastaukset_testi_ibfk_2` FOREIGN KEY (`KysID`) REFERENCES `Kysymykset` (`KysID`) ON DELETE CASCADE,
  CONSTRAINT `Vastaukset_testi_ibfk_3` FOREIGN KEY (`KID`) REFERENCES `Kurssi` (`KID`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

SET FOREIGN_KEY_CHECKS=1;

-- HUOM: _migraatiot-taulun esitäyttö on OMASSA tiedostossaan
-- (alustus_migraatiot.sql), koska tämän tiedoston ajaa myös ./asenna
-- paikatakseen puuttuvat taulut vanhasta kannasta — esitäyttö merkitsisi
-- siinä tapauksessa ajamattomat migraatiot virheellisesti tehdyiksi.
