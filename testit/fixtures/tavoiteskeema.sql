


  CONSTRAINT `ArvioKommentti_ibfk_1` FOREIGN KEY (`TID`) REFERENCES `Tutkimus` (`TID`) ON DELETE CASCADE
  CONSTRAINT `ArvioKommentti_ibfk_2` FOREIGN KEY (`KID`) REFERENCES `Kurssi` (`KID`) ON DELETE CASCADE
  CONSTRAINT `ArvioKommentti_ibfk_3` FOREIGN KEY (`KysID`) REFERENCES `Kysymykset` (`KysID`) ON DELETE CASCADE
  CONSTRAINT `HitlKorjaus_ibfk_1` FOREIGN KEY (`TID`) REFERENCES `Tutkimus` (`TID`) ON DELETE CASCADE
  CONSTRAINT `HitlKorjaus_ibfk_2` FOREIGN KEY (`KID`) REFERENCES `Kurssi` (`KID`) ON DELETE CASCADE
  CONSTRAINT `Kurssi_ibfk_1` FOREIGN KEY (`KKID`) REFERENCES `Korkeakoulu` (`KKID`) ON DELETE CASCADE
  CONSTRAINT `Kurssiarviointi_ibfk_1` FOREIGN KEY (`TID`) REFERENCES `Tutkimus` (`TID`) ON DELETE CASCADE
  CONSTRAINT `Kurssiarviointi_ibfk_2` FOREIGN KEY (`KID`) REFERENCES `Kurssi` (`KID`) ON DELETE CASCADE
  CONSTRAINT `Kurssiluokitus_ibfk_1` FOREIGN KEY (`TID`) REFERENCES `Tutkimus` (`TID`) ON DELETE CASCADE
  CONSTRAINT `Kurssiluokitus_ibfk_2` FOREIGN KEY (`KID`) REFERENCES `Kurssi` (`KID`) ON DELETE CASCADE
  CONSTRAINT `Kurssiluokitus_testi_ibfk_1` FOREIGN KEY (`TID`) REFERENCES `Tutkimus` (`TID`) ON DELETE CASCADE
  CONSTRAINT `Kurssiluokitus_testi_ibfk_2` FOREIGN KEY (`KID`) REFERENCES `Kurssi` (`KID`) ON DELETE CASCADE
  CONSTRAINT `Kysymykset_ibfk_1` FOREIGN KEY (`TID`) REFERENCES `Tutkimus` (`TID`) ON DELETE CASCADE
  CONSTRAINT `RaporttiOsio_ibfk_1` FOREIGN KEY (`TID`) REFERENCES `Tutkimus` (`TID`) ON DELETE CASCADE
  CONSTRAINT `RaporttiTuoreus_ibfk_1` FOREIGN KEY (`TID`) REFERENCES `Tutkimus` (`TID`) ON DELETE CASCADE
  CONSTRAINT `TutkimusKorkeakoulu_ibfk_1` FOREIGN KEY (`TID`) REFERENCES `Tutkimus` (`TID`) ON DELETE CASCADE
  CONSTRAINT `TutkimusKorkeakoulu_ibfk_2` FOREIGN KEY (`KKID`) REFERENCES `Korkeakoulu` (`KKID`) ON DELETE CASCADE
  CONSTRAINT `Vastaukset_ibfk_1` FOREIGN KEY (`KysID`) REFERENCES `Kysymykset` (`KysID`) ON DELETE CASCADE
  CONSTRAINT `Vastaukset_ibfk_2` FOREIGN KEY (`KID`) REFERENCES `Kurssi` (`KID`) ON DELETE CASCADE
  CONSTRAINT `Vastaukset_testi_ibfk_1` FOREIGN KEY (`TID`) REFERENCES `Tutkimus` (`TID`) ON DELETE CASCADE
  CONSTRAINT `Vastaukset_testi_ibfk_2` FOREIGN KEY (`KysID`) REFERENCES `Kysymykset` (`KysID`) ON DELETE CASCADE
  CONSTRAINT `Vastaukset_testi_ibfk_3` FOREIGN KEY (`KID`) REFERENCES `Kurssi` (`KID`) ON DELETE CASCADE
  KEY `KID` (`KID`)
  KEY `KID` (`KID`)
  KEY `KID` (`KID`)
  KEY `KID` (`KID`)
  KEY `KID` (`KID`)
  KEY `KID` (`KID`)
  KEY `KKID` (`KKID`)
  KEY `KysID` (`KysID`)
  KEY `KysID` (`KysID`)
  KEY `Kysymykset_ibfk_1` (`TID`)
  KEY `TID` (`TID`)
  KEY `Vastaukset_ibfk_2` (`KID`)
  KEY `idx_tid_ajo` (`TID`,`Ajo`)
  KEY `idx_tid_ajo` (`TID`,`Ajo`)
  PRIMARY KEY (`HID`)
  PRIMARY KEY (`KAID`)
  PRIMARY KEY (`KID`)
  PRIMARY KEY (`KKID`)
  PRIMARY KEY (`KLID`)
  PRIMARY KEY (`KomID`)
  PRIMARY KEY (`KysID`)
  PRIMARY KEY (`RID`)
  PRIMARY KEY (`TID`)
  PRIMARY KEY (`TID`)
  PRIMARY KEY (`TID`,`KKID`)
  PRIMARY KEY (`TLID`)
  PRIMARY KEY (`VTID`)
  PRIMARY KEY (`VasID`)
  PRIMARY KEY (`nimi`)
  UNIQUE KEY `uniikki_ajo_kys_kid` (`Ajo`,`KysID`,`KID`)
  UNIQUE KEY `uniikki_ajo_tid_kid` (`Ajo`,`TID`,`KID`)
  UNIQUE KEY `uniikki_kys_kurssi` (`KysID`,`KID`)
  UNIQUE KEY `uniikki_lahde_vuosi` (`KKID`,`LahdeId`,`Opetusvuosi`)
  UNIQUE KEY `uniikki_slug` (`Slug`)
  UNIQUE KEY `uniikki_tid_kid_kysid` (`TID`,`KID`,`KysID`)
  UNIQUE KEY `uniikki_tid_kid` (`TID`,`KID`)
  UNIQUE KEY `uniikki_tid_kid` (`TID`,`KID`)
  UNIQUE KEY `uniikki_tid_osio` (`TID`,`OsioAvain`)
  `Aikaleima` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP
  `Aikaleima` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
  `Aikaleima` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
  `Ajo` varchar(32) NOT NULL
  `Ajo` varchar(32) NOT NULL
  `ApiOsoite` text
  `Arviointi` text
  `Arviointikehote` text NOT NULL
  `Erakoko` int NOT NULL
  `Erakoko` int NOT NULL
  `HID` int NOT NULL AUTO_INCREMENT
  `Juurisyy` varchar(32) DEFAULT NULL
  `KAID` int NOT NULL AUTO_INCREMENT
  `KID` int NOT NULL
  `KID` int NOT NULL
  `KID` int NOT NULL
  `KID` int NOT NULL
  `KID` int NOT NULL
  `KID` int NOT NULL
  `KID` int NOT NULL
  `KID` int NOT NULL AUTO_INCREMENT
  `KKID` int NOT NULL
  `KKID` int NOT NULL
  `KKID` int NOT NULL AUTO_INCREMENT
  `KLID` int NOT NULL AUTO_INCREMENT
  `KayttajaNimi` varchar(255) NOT NULL
  `Kehotetiiviste` varchar(64) DEFAULT NULL
  `Kehotetiiviste` varchar(64) DEFAULT NULL
  `Kehotetiiviste` varchar(64) DEFAULT NULL
  `Kehotetiiviste` varchar(64) DEFAULT NULL
  `KomID` int NOT NULL AUTO_INCREMENT
  `Kommentti` text NOT NULL
  `Koodi` varchar(50) DEFAULT NULL
  `KouluNimi` varchar(255) NOT NULL
  `KurssiNimi` varchar(255) NOT NULL
  `KysID` int NOT NULL
  `KysID` int NOT NULL
  `KysID` int NOT NULL
  `KysID` int NOT NULL AUTO_INCREMENT
  `Kysymys` text NOT NULL
  `LahdeId` varchar(50) DEFAULT NULL
  `Laskentatiiviste` varchar(64) DEFAULT NULL
  `Lista` json DEFAULT NULL
  `Lista` json DEFAULT NULL
  `Lukuvuosi` varchar(9) DEFAULT NULL
  `LuokitteluMaarittely` json DEFAULT NULL
  `Luokittelu` enum('vapaa_teksti','luokittelu','asteikko','lista') NOT NULL DEFAULT 'vapaa_teksti'
  `Luokittelukehote` text NOT NULL
  `LuokittelunNimi` varchar(255) NOT NULL
  `Luokitteluperuste` text
  `Luokitteluperuste` text
  `Luokka` varchar(100) DEFAULT NULL
  `Luokka` varchar(100) DEFAULT NULL
  `Luotu` timestamp NULL DEFAULT CURRENT_TIMESTAMP
  `Luotu` timestamp NULL DEFAULT CURRENT_TIMESTAMP
  `Malli` varchar(120) DEFAULT NULL
  `Malli` varchar(120) DEFAULT NULL
  `Malli` varchar(120) DEFAULT NULL
  `Malli` varchar(120) DEFAULT NULL
  `Mukana` tinyint(1) DEFAULT NULL
  `Mukana` tinyint(1) DEFAULT NULL
  `Opetusvuosi` varchar(20) NOT NULL DEFAULT ''
  `Opintopisteet` varchar(30) DEFAULT NULL
  `Oppiaine` text
  `Oppiainerajaus` text
  `OpsKuvaus` mediumtext
  `OpsOsoite` text NOT NULL
  `OpsTyyppi` enum('Peppi','Sisu') NOT NULL
  `OsioAvain` varchar(50) NOT NULL
  `Perustelu` text
  `Perustelu` text NOT NULL
  `Pisteet` float DEFAULT NULL
  `Pisteet` float DEFAULT NULL
  `RID` int NOT NULL AUTO_INCREMENT
  `Raportointikehote` text
  `Sahkoposti` varchar(255) NOT NULL
  `Signatuuri` varchar(64) DEFAULT NULL
  `Slug` varchar(100) NOT NULL DEFAULT ''
  `TID` int NOT NULL
  `TID` int NOT NULL
  `TID` int NOT NULL
  `TID` int NOT NULL
  `TID` int NOT NULL
  `TID` int NOT NULL
  `TID` int NOT NULL
  `TID` int NOT NULL
  `TID` int NOT NULL
  `TID` int NOT NULL
  `TID` int NOT NULL AUTO_INCREMENT
  `TLID` int NOT NULL AUTO_INCREMENT
  `Tarkistettu` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
  `Taso` varchar(30) DEFAULT NULL
  `Tasorajaus` varchar(255) DEFAULT NULL
  `Teksti` mediumtext NOT NULL
  `UusiTila` tinyint(1) NOT NULL
  `VTID` int NOT NULL AUTO_INCREMENT
  `VasID` int NOT NULL AUTO_INCREMENT
  `Vastaus` text
  `Vastaus` text
  `Verkkosivu` text
  `ajettu` datetime DEFAULT CURRENT_TIMESTAMP
  `nimi` varchar(64) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;
/*!50503 SET NAMES utf8mb4 */;
/*!50503 SET character_set_client = utf8mb4 */;
/*!50503 SET character_set_client = utf8mb4 */;
/*!50503 SET character_set_client = utf8mb4 */;
/*!50503 SET character_set_client = utf8mb4 */;
/*!50503 SET character_set_client = utf8mb4 */;
/*!50503 SET character_set_client = utf8mb4 */;
/*!50503 SET character_set_client = utf8mb4 */;
/*!50503 SET character_set_client = utf8mb4 */;
/*!50503 SET character_set_client = utf8mb4 */;
/*!50503 SET character_set_client = utf8mb4 */;
/*!50503 SET character_set_client = utf8mb4 */;
/*!50503 SET character_set_client = utf8mb4 */;
/*!50503 SET character_set_client = utf8mb4 */;
/*!50503 SET character_set_client = utf8mb4 */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `ArvioKommentti` (
CREATE TABLE `HitlKorjaus` (
CREATE TABLE `Korkeakoulu` (
CREATE TABLE `Kurssi` (
CREATE TABLE `Kurssiarviointi` (
CREATE TABLE `Kurssiluokitus_testi` (
CREATE TABLE `Kurssiluokitus` (
CREATE TABLE `Kysymykset` (
CREATE TABLE `RaporttiOsio` (
CREATE TABLE `RaporttiTuoreus` (
CREATE TABLE `TutkimusKorkeakoulu` (
CREATE TABLE `Tutkimus` (
CREATE TABLE `Vastaukset_testi` (
CREATE TABLE `Vastaukset` (
CREATE TABLE `_migraatiot` (
DROP TABLE IF EXISTS `ArvioKommentti`;
DROP TABLE IF EXISTS `HitlKorjaus`;
DROP TABLE IF EXISTS `Korkeakoulu`;
DROP TABLE IF EXISTS `Kurssi`;
DROP TABLE IF EXISTS `Kurssiarviointi`;
DROP TABLE IF EXISTS `Kurssiluokitus_testi`;
DROP TABLE IF EXISTS `Kurssiluokitus`;
DROP TABLE IF EXISTS `Kysymykset`;
DROP TABLE IF EXISTS `RaporttiOsio`;
DROP TABLE IF EXISTS `RaporttiTuoreus`;
DROP TABLE IF EXISTS `TutkimusKorkeakoulu`;
DROP TABLE IF EXISTS `Tutkimus`;
DROP TABLE IF EXISTS `Vastaukset_testi`;
DROP TABLE IF EXISTS `Vastaukset`;
DROP TABLE IF EXISTS `_migraatiot`;
