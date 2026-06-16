-- Lisää kysymystyyppi (vapaa_teksti / luokittelu / asteikko) ja
-- tyyppikohtainen määritelmä Kysymykset-tauluun sekä rakenteellisten
-- vastausten Pisteet ja Luokka -sarakkeet Vastaukset-tauluun.

ALTER TABLE Kysymykset
  ADD COLUMN Luokittelu ENUM('vapaa_teksti', 'luokittelu', 'asteikko')
             NOT NULL DEFAULT 'vapaa_teksti',
  ADD COLUMN LuokitteluMaarittely JSON NULL;

ALTER TABLE Vastaukset
  ADD COLUMN Pisteet FLOAT NULL,
  ADD COLUMN Luokka  VARCHAR(100) NULL;
