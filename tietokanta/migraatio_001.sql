-- Migraatio 001: Lisää Kurssi-tauluun LahdeId, Koodi, Opetusvuosi-kentät
-- ja muuttaa OpsKuvaus-kentän MEDIUMTEXT:ksi (koko JSON-vastaus mahtuu).
-- Turvallinen ajaa tyhjälle taululle; idempotenttisuus varmistetaan
-- ennen ajoa tarkistamalla onko sarake jo olemassa.
ALTER TABLE Kurssi
    ADD COLUMN LahdeId     VARCHAR(50)  AFTER KKID,
    ADD COLUMN Koodi       VARCHAR(50)  AFTER LahdeId,
    ADD COLUMN Opetusvuosi VARCHAR(20)  NOT NULL DEFAULT '' AFTER Opintopisteet,
    MODIFY COLUMN OpsKuvaus MEDIUMTEXT,
    ADD UNIQUE KEY uniikki_lahde_vuosi (KKID, LahdeId, Opetusvuosi);
