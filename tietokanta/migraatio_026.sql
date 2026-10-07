-- Migraatio 026: lista-arvojen yhdistämispäätökset (raportin esikäsittely).
--
-- ListaYhdistys: käyttäjän kuittaamat ehdotukset lista-tyypin kysymysten arvojen
-- yhdistämisestä (Lahde → Kohde). Hyvaksytty=1 sovelletaan automaattisesti
-- seuraavalla raportin generoinnilla (arviointien uudelleenajo tuottaa taas raakoja
-- arvoja); Hyvaksytty=0 = hylätty ehdotus, jota ei näytetä uudelleen.
-- utf8mb4_bin: oletuskollaatio (ai_ci) pitäisi "ai" ja "AI" samana avaimena.
--
-- ListaLlmKasitelty: LLM:n jo käsittelemän (ja kuitatun) arvojoukon tiiviste per
-- kysymys → samaa joukkoa ei lähetetä LLM:lle uudelleen.
CREATE TABLE IF NOT EXISTS ListaYhdistys (
    TID        INT NOT NULL,
    KysID      INT NOT NULL,
    Lahde      VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
    Kohde      VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
    Hyvaksytty TINYINT(1) NOT NULL,
    Aikaleima  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (KysID, Lahde, Kohde),
    KEY idx_tid (TID),
    CONSTRAINT ListaYhdistys_ibfk_1 FOREIGN KEY (TID) REFERENCES Tutkimus (TID) ON DELETE CASCADE,
    CONSTRAINT ListaYhdistys_ibfk_2 FOREIGN KEY (KysID) REFERENCES Kysymykset (KysID) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS ListaLlmKasitelty (
    KysID     INT NOT NULL,
    TID       INT NOT NULL,
    Tiiviste  VARCHAR(64) NOT NULL,
    Aikaleima DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (KysID),
    KEY idx_tid (TID),
    CONSTRAINT ListaLlmKasitelty_ibfk_1 FOREIGN KEY (TID) REFERENCES Tutkimus (TID) ON DELETE CASCADE,
    CONSTRAINT ListaLlmKasitelty_ibfk_2 FOREIGN KEY (KysID) REFERENCES Kysymykset (KysID) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
