-- Migraatio 015: Testierä-taulut LLM-luokittelun ja -arvioinnin eräkoon
-- viritysajoille. Erillään oikeista tuloksista (Kurssiluokitus / Vastaukset),
-- jotta testiajot voi kirjata kuluttamatta tokeneita hukkaan ja poistaa
-- kohdennetusti ajotunnuksen (Ajo) mukaan oikeita tuloksia koskematta.

CREATE TABLE IF NOT EXISTS Kurssiluokitus_testi (
    TLID              INT AUTO_INCREMENT PRIMARY KEY,
    Ajo               VARCHAR(32) NOT NULL,
    Erakoko           INT NOT NULL,
    TID               INT NOT NULL,
    KID               INT NOT NULL,
    Mukana            BOOLEAN,
    Luokitteluperuste TEXT,
    Malli             VARCHAR(120),
    Kehotetiiviste    VARCHAR(64),
    Luotu             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (TID) REFERENCES Tutkimus(TID) ON DELETE CASCADE,
    FOREIGN KEY (KID) REFERENCES Kurssi(KID) ON DELETE CASCADE,
    UNIQUE KEY uniikki_ajo_tid_kid (Ajo, TID, KID),
    KEY idx_tid_ajo (TID, Ajo)
);

CREATE TABLE IF NOT EXISTS Vastaukset_testi (
    VTID            INT AUTO_INCREMENT PRIMARY KEY,
    Ajo             VARCHAR(32) NOT NULL,
    Erakoko         INT NOT NULL,
    TID             INT NOT NULL,
    KysID           INT NOT NULL,
    KID             INT NOT NULL,
    Vastaus         TEXT,
    Malli           VARCHAR(120),
    Kehotetiiviste  VARCHAR(64),
    Pisteet         FLOAT,
    Luokka          VARCHAR(100),
    Lista           JSON,
    Luotu           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (TID) REFERENCES Tutkimus(TID) ON DELETE CASCADE,
    FOREIGN KEY (KysID) REFERENCES Kysymykset(KysID) ON DELETE CASCADE,
    FOREIGN KEY (KID) REFERENCES Kurssi(KID) ON DELETE CASCADE,
    UNIQUE KEY uniikki_ajo_kys_kid (Ajo, KysID, KID),
    KEY idx_tid_ajo (TID, Ajo)
);
