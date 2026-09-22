#!/usr/bin/env bash
# Tarkistaa, että ajossa olevan kannan skeema vastaa tavoiteskeemaa
# (testit/fixtures/tavoiteskeema.sql = tuore asennus alustus.sql:stä).
# Aja repon juuresta koneella, jolla kanta pyörii: ./testit/skeematarkistus.sh
#
# Lukee yhteystiedot .env:stä ja käyttää compose-pinon mysql-palvelua, kuten
# ./asenna — ei vaadi mysql-clientiä isännälle eikä avaa portteja.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
source testit/skeemavedos.sh

# Moni tuotantokone ei ole lisännyt käyttäjää docker-ryhmään. Kokeillaan ensin
# ilman sudoa — turha sudo pyytäisi salasanaa vaikka oikeudet jo riittävät.
if command docker info >/dev/null 2>&1; then
    docker() { command docker "$@"; }
else
    docker() { sudo docker "$@"; }
fi

set -a; source .env; set +a

# < /dev/null: docker compose exec perii stdinin päätteestä ja voi muuten
# pysähtyä SIGTTIN:iin taustaprosessina — sama ansa kuin asennassa.
docker compose exec -T -e MYSQL_PWD="$DB_PASSWORD" mysql \
    mysqldump -u"$DB_USER" "${VEDOS_LIPUT[@]}" "$DB_NAME" < /dev/null \
    | normalisoi_vedos > /tmp/skeema_nyt.sql

if diff -u testit/fixtures/tavoiteskeema.sql /tmp/skeema_nyt.sql; then
    echo "OK: kannan skeema vastaa tavoiteskeemaa."
else
    echo
    echo "EROJA: '-' = tavoiteskeemassa muttei kannassa, '+' = kannassa ylimääräistä."
    exit 1
fi
