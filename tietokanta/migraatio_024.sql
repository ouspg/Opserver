-- Migraatio 024: LLM:n arviointivastauksen hyväksyntä (HITL-B, peukutus).
--
-- HyvaksyjaNimi IS NULL → LLM-vastausta ei ole hyväksytty. Vain visuaalinen;
-- ihmisen korjaus (Malli IS NULL -rivi) on aina hyväksytty. LLM:n uusi vastaus
-- (aseta_vastaus) nollaa hyväksynnän. Ei KayttajaNimi-saraketta: se kuuluu
-- uniikkiavaimeen uniikki_kys_kid_kayttaja ja on LLM-rivillä aina ''.
ALTER TABLE Vastaukset
    ADD COLUMN HyvaksyjaNimi       VARCHAR(255) DEFAULT NULL,
    ADD COLUMN HyvaksyjaSahkoposti VARCHAR(255) DEFAULT NULL;
