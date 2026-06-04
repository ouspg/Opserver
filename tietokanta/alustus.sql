CREATE TABLE IF NOT EXISTS Korkeakoulu (
    KKID     INT AUTO_INCREMENT PRIMARY KEY,
    KouluNimi VARCHAR(255) NOT NULL,
    OpsOsoite TEXT NOT NULL,
    OpsTyyppi ENUM('Peppi', 'Sisu') NOT NULL
);

CREATE TABLE IF NOT EXISTS Kurssi (
    KID           INT AUTO_INCREMENT PRIMARY KEY,
    KKID          INT NOT NULL,
    KurssiNimi    VARCHAR(255) NOT NULL,
    Taso          ENUM('yleis', 'perus', 'aine', 'syventävä'),
    Oppiaine      VARCHAR(255),
    Opintopisteet FLOAT,
    OpsKuvaus     TEXT,
    FOREIGN KEY (KKID) REFERENCES Korkeakoulu(KKID) ON DELETE CASCADE
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
