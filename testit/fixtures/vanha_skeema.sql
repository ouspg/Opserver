CREATE TABLE IF NOT EXISTS Korkeakoulu (
    KKID     INT AUTO_INCREMENT PRIMARY KEY,
    KouluNimi VARCHAR(255) NOT NULL,
    OpsOsoite TEXT NOT NULL,
    OpsTyyppi ENUM('Peppi', 'Sisu') NOT NULL
);

CREATE TABLE IF NOT EXISTS Kurssi (
    KID           INT AUTO_INCREMENT PRIMARY KEY,
    KKID          INT NOT NULL,
    LahdeId       VARCHAR(50),
    Koodi         VARCHAR(50),
    KurssiNimi    VARCHAR(255) NOT NULL,
    Taso          VARCHAR(30),
    Oppiaine      TEXT,
    Opintopisteet VARCHAR(30),
    Opetusvuosi   VARCHAR(20) NOT NULL,
    OpsKuvaus     MEDIUMTEXT,
    FOREIGN KEY (KKID) REFERENCES Korkeakoulu(KKID) ON DELETE CASCADE,
    UNIQUE KEY uniikki_lahde_vuosi (KKID, LahdeId, Opetusvuosi)
);

CREATE TABLE IF NOT EXISTS Tutkimus (
    TID              INT AUTO_INCREMENT PRIMARY KEY,
    LuokittelunNimi  VARCHAR(255) NOT NULL,
    Luokittelukehote TEXT NOT NULL,
    Tasorajaus       VARCHAR(255),
    Oppiainerajaus   VARCHAR(255),
    Arviointikehote  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS Kurssiluokitus (
    KLID              INT AUTO_INCREMENT PRIMARY KEY,
    TID               INT NOT NULL,
    KID               INT NOT NULL,
    Mukana            BOOLEAN,
    Luokitteluperuste TEXT,
    FOREIGN KEY (TID) REFERENCES Tutkimus(TID) ON DELETE CASCADE,
    FOREIGN KEY (KID) REFERENCES Kurssi(KID) ON DELETE CASCADE,
    UNIQUE KEY uniikki_tid_kid (TID, KID)
);

CREATE TABLE IF NOT EXISTS Kurssiarviointi (
    KAID      INT AUTO_INCREMENT PRIMARY KEY,
    TID       INT NOT NULL,
    KID       INT NOT NULL,
    Arviointi TEXT,
    Perustelu TEXT,
    FOREIGN KEY (TID) REFERENCES Tutkimus(TID) ON DELETE CASCADE,
    FOREIGN KEY (KID) REFERENCES Kurssi(KID) ON DELETE CASCADE,
    UNIQUE KEY uniikki_tid_kid (TID, KID)
);
