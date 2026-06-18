-- Tutkimukselle verkkosivun osoite (URL), joka linkitetään WebUI:ssa.
-- Valinnainen; TEXT välttää pituusrajat.

ALTER TABLE Tutkimus
  ADD COLUMN Verkkosivu TEXT NULL AFTER Lukuvuosi;
