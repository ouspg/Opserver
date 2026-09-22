#!/usr/bin/env bash
# Testaa asennan migraatioajurin kertakäyttöisellä MySQL-kontilla.
# Aja repon juuresta: ./testit/migraatiotesti.sh
#
# Kaksi skenaariota:
#   vanha  — kanta alustettu vanhasta skeemasta (5 taulua, ei _migraatiot-esitäyttöä)
#            + migraatiot 001-003 merkitty ajetuiksi = tuotannon tila 2026-09-22,
#            jossa migraatio_004 kaatui "Table 'Vastaukset' doesn't exist".
#   tuore  — kanta alustettu nykyisestä alustus.sql + alustus_migraatiot.sql:stä.
#
# Molemmissa lopputuloksen on oltava sama: kaikki migraatiot merkitty ajetuiksi
# ja kaikki alustus.sql:n taulut olemassa.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."

KONTTI=migraatiotesti
KUVA=mysql:8.4
TMP=$(mktemp -d)
siivoa() { docker rm -f "$KONTTI" >/dev/null 2>&1 || true; }
trap 'siivoa; rm -rf "$TMP"' EXIT
virheita=0

# Kontin sisällä ajava mysql-client; sama rajapinta kuin asennan aja_sql.
aja_sql() { docker exec -i -e MYSQL_PWD=t "$KONTTI" mysql -ut opserverdb "$@"; }

kaynnista() {
    siivoa
    docker run -d --name "$KONTTI" \
        -e MYSQL_ROOT_PASSWORD=r -e MYSQL_DATABASE=opserverdb \
        -e MYSQL_USER=t -e MYSQL_PASSWORD=t \
        "$KUVA" --skip-name-resolve >/dev/null
    for _ in $(seq 60); do
        aja_sql -e "SELECT 1" >/dev/null 2>&1 && return 0
        sleep 2
    done
    echo "MySQL ei noussut ajoissa"; exit 1
}

# Asennan migraatiolohko sellaisenaan (ei kopiota, joka voisi vanhentua):
# _migraatiot-taulun luonnista silmukan loppuun. Yllä määritelty aja_sql jää
# voimaan, koska lohko ei määrittele sitä uudelleen.
aja_migraatiot() {
    eval "$(sed -n '/^aja_sql -e "CREATE TABLE IF NOT EXISTS _migraatiot/,/^done$/p' asenna)"
}

# Skeemavedos vertailua varten. Normalisoinnit: AUTO_INCREMENT-laskuri pois (ei
# skeemaa), rivit aakkosjärjestykseen ja rivinloppupilkut pois — sarakkeiden
# järjestys taulussa on kosmeettinen eikä migraatiopolku päädy samaan
# järjestykseen kuin squashattu alustus.sql.
vedos() {
    docker exec -e MYSQL_PWD=t "$KONTTI" mysqldump -ut --no-data --skip-comments \
        --skip-dump-date --no-tablespaces opserverdb \
        | sed 's/ AUTO_INCREMENT=[0-9]*//; s/,$//' | sort
}

tarkista() {
    local skenaario="$1"
    local puuttuvat
    puuttuvat=$(for t in tietokanta/migraatio_*.sql; do
        nimi=$(basename "$t")
        [[ -n "$(aja_sql -N -e "SELECT 1 FROM _migraatiot WHERE nimi='$nimi'")" ]] || echo "$nimi"
    done)
    [[ -z "$puuttuvat" ]] || { echo "[$skenaario] migraatioita ei merkitty ajetuiksi: $puuttuvat"; virheita=1; }
}

echo "== skenaario: vanha kanta (tuotannon tila)"
kaynnista
aja_sql < testit/fixtures/vanha_skeema.sql
aja_sql -e "CREATE TABLE _migraatiot (nimi VARCHAR(64) PRIMARY KEY, ajettu DATETIME DEFAULT CURRENT_TIMESTAMP);
            INSERT INTO _migraatiot (nimi) VALUES ('migraatio_001.sql'),('migraatio_002.sql'),('migraatio_003.sql')"
aja_migraatiot
tarkista vanha
vedos > "$TMP/vanha.sql"

echo "== skenaario: tuore kanta"
kaynnista
aja_sql < tietokanta/alustus.sql
aja_sql < tietokanta/alustus_migraatiot.sql
aja_migraatiot
tarkista tuore
vedos > "$TMP/tuore.sql"

# Ydinväite: migratoitu vanha kanta päätyy samaan skeemaan kuin tuore asennus.
diff -u "$TMP/tuore.sql" "$TMP/vanha.sql" \
    || { echo "Migratoitu vanha kanta eroaa tuoreesta (- = puuttuu vanhasta)"; virheita=1; }

[[ $virheita -eq 0 ]] && echo "OK" || { echo "VIRHEITÄ"; exit 1; }
