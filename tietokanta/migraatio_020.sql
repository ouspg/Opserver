-- Migraatio 020: vuosirajaus indeksoitavaksi.
--
-- Vuosirajaus jäsensi OPS-kauden kyselyn sisällä
-- (CAST(SUBSTRING_INDEX(Opetusvuosi,'-',1))...), jolloin sarake oli funktion
-- sisällä eikä mikään indeksi kelvannut: jokainen ehdokashaku ja tilannesivun
-- kysely luki koko Kurssi-taulun. Mitattu geopalvelin1:llä (26 k riviä):
-- luokittelun ehdokashaku 2,4 s, tilannesivu 2,7 s.
--
-- Sama jäsennys siirretään generoituihin sarakkeisiin, jotka voidaan indeksoida.
-- VIRTUAL (ei STORED): sarakkeita ei talleteta eikä taulua rakenneta uudelleen,
-- joten ALTER ei lukitse kirjoituksia kesken pipeline-ajon. Indeksi materialisoi
-- arvot silti, joten haku on yhtä nopea kuin tavallisella sarakkeella.
--
-- Lausekkeet peilaavat mallit._vuosi_kattaa_sql:n entistä logiikkaa merkki
-- merkiltä (myös YYYY-YY-lyhytmuodon): kelvoton/tyhjä Opetusvuosi antaa 0, joka
-- ei läpäise mitään lukuvuosirajausta — sama käytös kuin ennen.

-- _utf8mb4-etuliite merkkijonovakioissa on PAKOLLINEN: generoidun sarakkeen
-- lauseke tallentuu skeemaan sellaisena kuin se jäsennetään, ja ilman etuliitettä
-- se saa yhteyden oletusmerkistön (migraatioajossa _latin1, initdb.d:ssä
-- _utf8mb4). Silloin migratoitu kanta ja tuore asennus eroaisivat pysyvästi
-- toisistaan ja skeematarkistus hylkäisi asennuksen. (Havaittu migraatiotestillä.)
ALTER TABLE Kurssi
    ADD COLUMN VuosiAlku SMALLINT UNSIGNED
        GENERATED ALWAYS AS (CAST(SUBSTRING_INDEX(Opetusvuosi, _utf8mb4'-', 1) AS UNSIGNED)) VIRTUAL,
    ADD COLUMN VuosiLoppu SMALLINT UNSIGNED
        GENERATED ALWAYS AS (
            CASE WHEN CHAR_LENGTH(SUBSTRING_INDEX(Opetusvuosi, _utf8mb4'-', -1)) = 4
                 THEN CAST(SUBSTRING_INDEX(Opetusvuosi, _utf8mb4'-', -1) AS UNSIGNED)
                 ELSE CAST(SUBSTRING_INDEX(Opetusvuosi, _utf8mb4'-', 1) AS UNSIGNED) DIV 100 * 100
                      + CAST(SUBSTRING_INDEX(Opetusvuosi, _utf8mb4'-', -1) AS UNSIGNED) END
        ) VIRTUAL;

-- (KKID, VuosiAlku, VuosiLoppu): tutkimuksen rajaus osuu korkeakouluun
-- tasavertaisuudella ja vuoteen alueena — juuri se yhdistelmä jota
-- _tutkimus_kurssi_scope kysyy.
ALTER TABLE Kurssi ADD INDEX idx_kkid_vuosi (KKID, VuosiAlku, VuosiLoppu);
