-- Migraatio 017: RaporttiOsio.Laskentatiiviste — raportin tuoreustarkistus.
-- Tallennetaan generoinnin hetkellä hash siitä lähdeaineistosta, josta raportti
-- koottiin (per-yliopisto-tilastot, kysymykset, arviointien tila, kommentit,
-- kehotteet). CLIUI:n "Näytä tilanne" vertaa tallennettua tiivistettä nykyiseen
-- → yksiselitteinen "ajan tasalla / aineisto muuttunut generoinnin jälkeen",
-- myös aikaleimattomien taulujen (Kurssiluokitus, Vastaukset) osalta.
-- NULL = generoitu ennen tätä ominaisuutta → tuoreus tuntematon.
ALTER TABLE RaporttiOsio ADD COLUMN Laskentatiiviste VARCHAR(64) NULL;
