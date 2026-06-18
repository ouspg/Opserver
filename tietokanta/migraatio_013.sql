-- Tutkimuksen oppiainerajaus valitaan listalta, ja oppiaineita voi olla
-- mielivaltaisen monta — pilkulla eroteltu lista ylittää VARCHAR(255):n.
-- Levennetään TEXT-tyyppiseksi (Tasorajaus on kiinteä pieni joukko, ei muuteta).

ALTER TABLE Tutkimus
  MODIFY Oppiainerajaus TEXT;
