-- Migraatio 019: täydennä ketjusta puuttuvat käsin tehdyt muutokset.
-- Tutkimus.Slug ja uniikki_slug lisättiin aikanaan suoraan kehityskantaan, joten
-- ne päätyivät alustus.sql:n squashiin mutta eivät mihinkään migraatioon — vanha
-- kanta ei siksi migratoidu ajan tasalle (paljastui tuotantoasennuksessa
-- 2026-09-22). Sama koskee Opetusvuoden oletusarvoa.
--
-- Slug täytetään ennen uniikkia avainta: pelkkä DEFAULT '' törmäisi useamman
-- rivin kannassa "Duplicate entry" -virheeseen.
ALTER TABLE Kurssi MODIFY COLUMN Opetusvuosi VARCHAR(20) NOT NULL DEFAULT '';

ALTER TABLE Tutkimus ADD COLUMN Slug VARCHAR(100) NOT NULL DEFAULT '';

UPDATE Tutkimus SET Slug = CONCAT('tutkimus-', TID) WHERE Slug = '';

ALTER TABLE Tutkimus ADD UNIQUE KEY uniikki_slug (Slug);
