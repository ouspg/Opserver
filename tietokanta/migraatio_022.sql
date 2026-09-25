-- Migraatio 022: HITL-vastaukset samaan Vastaukset-tauluun, ArvioKommentti pois.
--
-- Arviointien HITL oli pelkkä vapaa kommentti (ArvioKommentti), joka ei koskenut
-- tekoälyn vastaukseen eikä tuottanut rakenteisia arvoja (luokka/pisteet/lista)
-- eikä tekijä-/juurisyytietoa. Nyt ihmisen korjaus on oikea vastaus samassa
-- taulussa kuin LLM:n vastaus, ja WebUI näyttää ihmisen arvon kun se on.
--
-- Rivin alkuperä: Malli IS NULL  → ihmisen korjaus (KayttajaNimi/Sahkoposti/
--                                  Aikaleima kertovat kuka ja milloin)
--                 Malli IS NOT NULL → LLM:n vastaus (myös tyhjä merkkijono)
--
-- HUOM uniikki avain: LLM- ja HITL-rivi ovat samalla (KysID, KID) -parilla, joten
-- entinen uniikki_kys_kurssi (KysID, KID) on korvattava. Uusi avain ottaa
-- käyttäjän mukaan: LLM-rivillä KayttajaNimi = '' → yksi rivi per (kysymys,
-- kurssi) kuten ennen, joten aseta_vastaus:n ON DUPLICATE KEY UPDATE toimii
-- entiseen tapaan. Ihmisillä yksi rivi per korjaaja → uusi korjaus päivittää
-- saman henkilön aiemman, eri henkilöiden korjaukset näkyvät erikseen.

-- JÄRJESTYS ON MERKITSEVÄ. asenna:n migraatiorunner käsittelee tiedoston yhtenä
-- yksikkönä: jos jokin lause kaatuu "Duplicate column/key" -virheeseen, se
-- tulkitsee KOKO migraation jo sovelletuksi ja jättää loput lauseet ajamatta.
-- Tuoreella kannalla alustus.sql (initdb.d / "puuttuvien taulujen paikkaus") on
-- jo luonut Vastaukset-taulun lopullisessa muodossaan, joten alla oleva
-- ADD COLUMN kaatuu juuri niin. Siksi kaikki lauseet jotka EIVÄT voi kaatua
-- duplikaattiin tulevat ensin — muuten ArvioKommentti jäisi tuoreisiin kantoihin
-- roikkumaan (havaittu migraatiotestillä).
DROP TABLE IF EXISTS ArvioKommentti;

ALTER TABLE Vastaukset
    ADD COLUMN TID          INT NULL,  -- NULL ensin; täytetään alla ja kiristetään
    ADD COLUMN KayttajaNimi VARCHAR(255) NOT NULL DEFAULT '',
    ADD COLUMN Sahkoposti   VARCHAR(255) NOT NULL DEFAULT '',
    ADD COLUMN Aikaleima    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ADD COLUMN Juurisyy     VARCHAR(32) DEFAULT NULL;

-- Olemassa olevat rivit ovat kaikki LLM:n vastauksia; tutkimus selviää kysymyksestä.
UPDATE Vastaukset v JOIN Kysymykset k ON k.KysID = v.KysID SET v.TID = k.TID;

ALTER TABLE Vastaukset MODIFY COLUMN TID INT NOT NULL;

-- Uusi avain ja vanhan pudotus SAMASSA lauseessa: Vastaukset_ibfk_1 (KysID)
-- nojaa vanhaan avaimeen, ja erillinen DROP INDEX kaatuu "Cannot drop index
-- needed in a foreign key constraint" (ERROR 1553) — havaittu mainin skeemaa vasten.
ALTER TABLE Vastaukset
    ADD UNIQUE KEY uniikki_kys_kid_kayttaja (KysID, KID, KayttajaNimi),
    DROP INDEX uniikki_kys_kurssi,
    ADD KEY idx_tid (TID),
    ADD CONSTRAINT Vastaukset_ibfk_3 FOREIGN KEY (TID) REFERENCES Tutkimus (TID) ON DELETE CASCADE;

-- (ArvioKommentti pudotettiin jo tiedoston alussa — ks. järjestysperustelu siellä.
-- Vapaa kommentti korvautuu rakenteisella korjauksella; kummassakaan kannassa
-- ei ollut yhtään riviä 2026-09-25, joten ihmisen työtä ei katoa.)
