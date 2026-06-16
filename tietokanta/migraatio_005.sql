-- Migraatio 005: Lisätään HitlKorjaus-taulu ihminen-silmukassa -annotointeja varten.
-- Tallentaa ihmisen tekemät luokittelun ohitukset: kuka, milloin, miksi, mihin suuntaan.
CREATE TABLE IF NOT EXISTS HitlKorjaus (
    HID          INT AUTO_INCREMENT PRIMARY KEY,
    TID          INT NOT NULL,
    KID          INT NOT NULL,
    UusiTila     TINYINT(1) NOT NULL,
    Perustelu    TEXT NOT NULL,
    KayttajaNimi VARCHAR(255) NOT NULL,
    Sahkoposti   VARCHAR(255) NOT NULL,
    Aikaleima    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (TID) REFERENCES Tutkimus(TID) ON DELETE CASCADE,
    FOREIGN KEY (KID) REFERENCES Kurssi(KID) ON DELETE CASCADE
);
