-- Tutkimus kohdistetaan yhteen lukuvuoteen (esim. 2024-2025) ja valittuihin
-- korkeakouluihin. Meta-suodatus huomioi vain ne kurssit, jotka kuuluvat
-- valittuun korkeakouluun ja joiden OPS-kausi kattaa tutkimuksen lukuvuoden.
--
-- Lukuvuosi sallii NULL:n migraation ajaksi (vanha rivi täydennetään UI:sta);
-- sovellus vaatii sen ja vähintään yhden korkeakoulun ennen suodatuksen ajoa.

-- Ei AFTER Slug: Slug syntyy vasta migraatiossa 019 (se lisättiin aikanaan
-- käsin kehityskantaan), joten vanhassa kannassa viittaus kaatuisi tähän.
-- Sarakkeen järjestys on pelkkä kosmeettinen seikka.
ALTER TABLE Tutkimus
  ADD COLUMN Lukuvuosi VARCHAR(9) NULL;

CREATE TABLE IF NOT EXISTS TutkimusKorkeakoulu (
    TID  INT NOT NULL,
    KKID INT NOT NULL,
    PRIMARY KEY (TID, KKID),
    FOREIGN KEY (TID) REFERENCES Tutkimus(TID) ON DELETE CASCADE,
    FOREIGN KEY (KKID) REFERENCES Korkeakoulu(KKID) ON DELETE CASCADE
);
