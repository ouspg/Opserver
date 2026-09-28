#!/usr/bin/env bash
# varmuuskopio → muutoksia kantaan (uusi taulu, poistettu rivi) → --palauta →
# kanta täsmälleen dumpin tilassa. Kertakäyttöinen MySQL-kontti; ajaa oikean
# skriptin, jonka `docker compose exec … mysql` ohjataan konttiin. Vaatii Dockerin.
set -euo pipefail
JUURI="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
KONTTI=varmuuskopiotesti
T=$(mktemp -d)
trap 'docker rm -f "$KONTTI" >/dev/null 2>&1 || true; rm -rf "$T"' EXIT

docker rm -f "$KONTTI" >/dev/null 2>&1 || true
docker run -d --name "$KONTTI" -e MYSQL_ROOT_PASSWORD=r -e MYSQL_DATABASE=opserverdb mysql:8.4 >/dev/null
sql() { docker exec -i -e MYSQL_PWD=r "$KONTTI" mysql -uroot -N opserverdb "$@"; }
for _ in $(seq 60); do sql -e "SELECT 1" >/dev/null 2>&1 && break; sleep 2; done

cp "$JUURI/varmuuskopio" "$T/"
printf 'DB_ROOT_PASSWORD=r\nDB_NAME=opserverdb\n' > "$T/.env"
mkdir "$T/bin"
cat > "$T/bin/docker" <<EOF
#!/usr/bin/env bash
# compose exec -T -e X mysql ohjelma … → docker exec -i -e X $KONTTI ohjelma …
[[ "\$1 \$2 \$3" == "compose exec -T" ]] || exit 99
exec $(command -v docker) exec -i "\$4" "\$5" $KONTTI "\${@:7}"
EOF
printf '#!/bin/sh\nexec "$@"\n' > "$T/bin/sudo"
chmod +x "$T/bin/"*

sql -e "CREATE TABLE Kurssi (id INT PRIMARY KEY, nimi VARCHAR(20)); INSERT INTO Kurssi VALUES (1,'a'),(2,'b');"
dumppi=$(PATH="$T/bin:$PATH" VARMUUSKOPIO_HAKEMISTO="$T/vk" "$T/varmuuskopio" testi)
sql -e "DELETE FROM Kurssi WHERE id=2; CREATE TABLE UusiTaulu (x INT);"
PATH="$T/bin:$PATH" "$T/varmuuskopio" --palauta "$dumppi"

virheita=0
[[ "$(sql -e 'SELECT COUNT(*) FROM Kurssi')" == 2 ]] || { echo "[FAIL] poistettu rivi ei palautunut"; virheita=1; }
[[ -z "$(sql -e "SHOW TABLES LIKE 'UusiTaulu'")" ]] || { echo "[FAIL] dumpin jälkeen luotu taulu jäi"; virheita=1; }
[[ "$dumppi" == "$T/vk/"*-testi.sql.gz ]] || { echo "[FAIL] tiedostonimi: $dumppi"; virheita=1; }
[[ $virheita -eq 0 ]] && echo "Varmuuskopio + palautus OK." || exit 1
