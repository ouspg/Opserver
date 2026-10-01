#!/usr/bin/env bash
# Selaintestit (testit/selain/, headless Chromium) omaa MySQL-konttia vasten.
# Käynnistää tarvittaessa kontin opserver-selain-mysql (127.0.0.1:21414, jää käyntiin
# seuraavia ajoja varten; `docker rm -f opserver-selain-mysql` poistaa) ja asentaa
# playwrightin + Chromiumin .venv:iin. Jokainen ajo luo ja pudottaa oman kantansa.
# Muu kanta: SELAIN_DB_HOST/PORT/USER/PASSWORD. Lisäargumentit → pytest (esim. -k paikannus).
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
KONTTI=opserver-selain-mysql

if ! $PY -c "import playwright" 2>/dev/null; then
    $PY -m pip install -q -r testit/selain/requirements.txt
    $PY -m playwright install chromium-headless-shell
fi

if [[ -z "${SELAIN_DB_HOST:-}" ]]; then
    if [[ -z "$(docker ps -q -f name="^${KONTTI}$")" ]]; then
        docker start "$KONTTI" >/dev/null 2>&1 || docker run -d --name "$KONTTI" -p 127.0.0.1:21414:3306 \
            -e MYSQL_ROOT_PASSWORD=selain mysql:8.4 --skip-name-resolve >/dev/null
    fi
    for _ in $(seq 60); do
        $PY -c "import mysql.connector as m; m.connect(host='127.0.0.1', port=21414, user='root', password='selain')" \
            2>/dev/null && break
        sleep 2
    done
fi

OPSERVER_SELAIN=1 exec $PY -m pytest testit/selain "$@"
