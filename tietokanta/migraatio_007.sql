-- Migraatio 007: Raportointikehote Tutkimus-tauluun + RaporttiOsio-taulu.
-- HUOM: ALTER saattaa epäonnistua jos sarake on jo olemassa — turvallista ohittaa.
ALTER TABLE Tutkimus
    ADD COLUMN Raportointikehote TEXT AFTER Arviointikehote;

CREATE TABLE IF NOT EXISTS RaporttiOsio (
    RID       INT AUTO_INCREMENT PRIMARY KEY,
    TID       INT          NOT NULL,
    OsioAvain VARCHAR(50)  NOT NULL,
    Teksti    MEDIUMTEXT   NOT NULL,
    Aikaleima DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (TID) REFERENCES Tutkimus(TID) ON DELETE CASCADE,
    UNIQUE KEY uniikki_tid_osio (TID, OsioAvain)
);
