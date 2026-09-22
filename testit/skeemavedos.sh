# Jaettu apufunktio: normalisoi mysqldump-skeemavedos vertailukelpoiseksi
# (stdin -> stdout). Sourcetaan; ei ajeta suoraan.
#
# AUTO_INCREMENT-laskuri pois (ei ole skeemaa), rivinloppupilkut pois ja rivit
# aakkosjärjestykseen: sarakkeiden järjestys taulussa on kosmeettinen eikä
# migraatiopolku päädy samaan järjestykseen kuin squashattu alustus.sql.
normalisoi_vedos() { sed 's/ AUTO_INCREMENT=[0-9]*//; s/,$//' | sort; }

# mysqldumpin liput skeemavedokselle — samat joka paikassa, muuten vertailu
# eroaa kohinasta eikä skeemasta.
VEDOS_LIPUT=(--no-data --skip-comments --skip-dump-date --no-tablespaces)
