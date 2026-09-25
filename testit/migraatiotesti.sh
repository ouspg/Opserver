#!/usr/bin/env bash
# Testaa asennan migraatioajurin kertakäyttöisellä MySQL-kontilla.
# Aja repon juuresta: ./testit/migraatiotesti.sh
#
# Kolme skenaariota:
#   vanha     — kanta alustettu vanhasta skeemasta (5 taulua, ei _migraatiot-esitäyttöä)
#               + migraatiot 001-003 merkitty ajetuiksi = tuotannon tila 2026-09-22,
#               jossa migraatio_004 kaatui "Table 'Vastaukset' doesn't exist".
#   edellinen — kanta alustettu haaran kantaversion (merge-base main) alustus.sql:stä:
#               ajaa haaran uudet migraatiot oikeasti olemassa olevia tauluja vasten.
#   tuore     — kanta alustettu nykyisestä alustus.sql + alustus_migraatiot.sql:stä.
#
# Kaikissa lopputuloksen on oltava sama: kaikki migraatiot merkitty ajetuiksi
# ja kaikki alustus.sql:n taulut olemassa.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
source testit/skeemavedos.sh

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

vedos() {
    docker exec -e MYSQL_PWD=t "$KONTTI" mysqldump -ut "${VEDOS_LIPUT[@]}" opserverdb \
        | normalisoi_vedos
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

# Vanha fixture ei sisällä uudempia tauluja lainkaan, jolloin asennan paikkaus luo
# ne suoraan lopullisessa muodossa ja tuore ALTER-migraatio ohitetaan duplikaattina —
# sen oikea polku ei koskaan tule ajetuksi. Siksi kolmas skenaario: kanta
# mainin (haaran kantaversion) alustus.sql:stä = kehitys-/tuotantokannan tila
# ennen tämän haaran migraatioita. Mainissa itsessään tämä = tuore kanta.
KANTAVERSIO=$(git merge-base HEAD origin/main 2>/dev/null || git merge-base HEAD main 2>/dev/null || echo HEAD)
echo "== skenaario: edellinen skeema ($(git rev-parse --short "$KANTAVERSIO"))"
kaynnista
git show "$KANTAVERSIO:tietokanta/alustus.sql" | aja_sql
git show "$KANTAVERSIO:tietokanta/alustus_migraatiot.sql" | aja_sql
aja_migraatiot
tarkista edellinen
vedos > "$TMP/edellinen.sql"

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
diff -u "$TMP/tuore.sql" "$TMP/edellinen.sql" \
    || { echo "Migratoitu edellinen skeema eroaa tuoreesta (- = puuttuu migratoidusta)"; virheita=1; }

# Tavoiteskeema on ./testit/skeematarkistus.sh:n vertailukohta ajossa oleville
# kannoille — pidetään se ajan tasalla tässä, ettei se pääse vanhenemaan.
diff -u testit/fixtures/tavoiteskeema.sql "$TMP/tuore.sql" \
    || { echo "testit/fixtures/tavoiteskeema.sql on vanhentunut — päivitä se tuoreen asennuksen vedoksella"; virheita=1; }

[[ $virheita -eq 0 ]] && echo "OK" || { echo "VIRHEITÄ"; exit 1; }
