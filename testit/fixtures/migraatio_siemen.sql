-- Pieni siemendata migraatiotestin 'edellinen'-skenaarioon: yksi rivi per keskeinen
-- taulu, jotta dataan koskevat migraatiolauseet (UPDATE + MODIFY … NOT NULL tms.)
-- ajetaan oikeita rivejä vasten. Vain pakolliset sarakkeet, ettei uusi oletusarvollinen
-- sarake riko tätä. Kohdistuu tämän commitin alustus.sql:ään; migraatiotesti ajaa
-- kantaversion (merge-base) kopion sen omaa skeemaa vasten ja nykyisen tuoreeseen
-- kantaan — skeemaa muuttava PR päivittää tämän uuteen skeemaan.
INSERT INTO Korkeakoulu (KKID, KouluNimi, OpsOsoite, OpsTyyppi) VALUES (1, 'Testi-yo', 'https://example.invalid', 'Peppi');
INSERT INTO Kurssi (KID, KKID, LahdeId, Koodi, KurssiNimi, Taso, Opetusvuosi) VALUES (1, 1, 'L1', 'T001', 'Testikurssi', 'perus', '2025-2026');
INSERT INTO KurssiKuvaus (KID) VALUES (1);
INSERT INTO Tutkimus (TID, LuokittelunNimi, Luokittelukehote, Arviointikehote) VALUES (1, 'Testi', 'k', 'a');
INSERT INTO TutkimusKorkeakoulu (TID, KKID) VALUES (1, 1);
INSERT INTO Kysymykset (KysID, TID, Kysymys) VALUES (1, 1, 'Kysymys?');
INSERT INTO Kurssiluokitus (TID, KID) VALUES (1, 1);
INSERT INTO Kurssiarviointi (TID, KID) VALUES (1, 1);
INSERT INTO Vastaukset (KysID, KID, TID) VALUES (1, 1, 1);
INSERT INTO HitlKorjaus (TID, KID, UusiTila, Perustelu, KayttajaNimi, Sahkoposti) VALUES (1, 1, 1, 'p', 'n', 'n@example.invalid');
INSERT INTO RaporttiOsio (TID, OsioAvain, Teksti) VALUES (1, 'yhteenveto', 't');
