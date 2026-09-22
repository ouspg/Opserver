-- Ajetaan VAIN tuoreelle kannalle (docker-entrypoint-initdb.d, alustus.sql:n
-- jälkeen aakkosjärjestyksessä). alustus.sql sisältää jo migraatiot 001-019
-- (squash), joten merkitään ne ajetuiksi, ettei asennan migraatioajuri yritä
-- ajaa niitä uudelleen (esim. migraatio_011:n ADD COLUMN ApiOsoite kaatuisi
-- "Duplicate column" -virheeseen).
--
-- ÄLÄ aja tätä olemassa olevalle kannalle: silloin oikeasti ajamattomat
-- migraatiot merkittäisiin tehdyiksi ja skeema jäisi jälkeen.
CREATE TABLE IF NOT EXISTS _migraatiot (
    nimi VARCHAR(64) PRIMARY KEY,
    ajettu DATETIME DEFAULT CURRENT_TIMESTAMP
);
INSERT IGNORE INTO _migraatiot (nimi) VALUES
    ('migraatio_001.sql'), ('migraatio_002.sql'), ('migraatio_003.sql'),
    ('migraatio_004.sql'), ('migraatio_005.sql'), ('migraatio_006.sql'),
    ('migraatio_007.sql'), ('migraatio_008.sql'), ('migraatio_009.sql'),
    ('migraatio_010.sql'), ('migraatio_011.sql'), ('migraatio_012.sql'),
    ('migraatio_013.sql'), ('migraatio_014.sql'), ('migraatio_015.sql'),
    ('migraatio_016.sql'), ('migraatio_017.sql'), ('migraatio_018.sql'),
    ('migraatio_019.sql');
