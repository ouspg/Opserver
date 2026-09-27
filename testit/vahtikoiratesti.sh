#!/usr/bin/env bash
# Vahtikoiran kova restart: MySQL:ää EI saa käynnistää uudelleen silloin kun se
# on itse kunnossa — kesken oleva kurssihaku kaatuu siihen. Ajaa oikean skriptin
# stub-dockerilla, ei tarvitse Dockeria eikä muuta ympäristöä.
set -euo pipefail

JUURI="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
TYOTILA="$(mktemp -d)"
TILA_TIEDOSTO="$JUURI/.vahtikoira_epakunnossa_alkoi"
trap 'rm -rf "$TYOTILA"; rm -f "$TILA_TIEDOSTO"' EXIT

cat > "$TYOTILA/sudo" <<'EOF'
#!/usr/bin/env bash
exec "$@"
EOF

# CURL_TILA=alhaalla: WebUI ei vastaa (timeout) — tilanne, jossa vanha
# vahtikoira restartoi myös terveen kannan. CURL_TILA=ylhaalla: Caddy vastaa,
# mutta kuten oikea Caddy vain domainin SNI:llä (https://localhost/ -> TLS-virhe 35).
cat > "$TYOTILA/curl" <<'EOF'
#!/usr/bin/env bash
[[ "$CURL_TILA" == alhaalla ]] && exit 28
[[ "$*" == *"--resolve esimerkki.fi:443:127.0.0.1"*"https://esimerkki.fi/"* ]] || exit 35
printf 401
EOF

cat > "$TYOTILA/docker" <<'EOF'
#!/usr/bin/env bash
case "$*" in
    "compose ps --status running --services") printf 'caddy\nmysql\nwebui\n' ;;
    "compose ps -q mysql")                    echo "mysql-kontti-id" ;;
    *inspect*)                                echo "$MYSQL_TERVEYS" ;;
    "compose up -d")                          : ;;
    "compose restart"*)                       kaikki="$*"; echo "${kaikki#compose restart }" > "$RESTART_LOKI" ;;
esac
EOF

chmod +x "$TYOTILA"/{sudo,curl,docker}
export PATH="$TYOTILA:$PATH"
export RESTART_LOKI="$TYOTILA/restart.txt"
export TUOTANTO_DOMAIN=esimerkki.fi CURL_TILA=alhaalla

aja() {
    MYSQL_TERVEYS="$1" : > "$RESTART_LOKI"
    echo "$(( $(date +%s) - 700 ))" > "$TILA_TIEDOSTO"   # epäkunnossa yli 10 min
    # stderr pois: vahtikoiran `date -Is` on GNU-muoto eikä toimi macOS:n
    # datella — skripti ajetaan tuotannossa Linuxilla, lokirivi ei ole testin asia.
    MYSQL_TERVEYS="$1" "$JUURI/vahtikoira" > /dev/null 2>&1
    cat "$RESTART_LOKI"
}

virheita=0
tarkista() {  # tarkista <kuvaus> <odotettu> <saatu>
    if [[ "$2" == "$3" ]]; then
        echo "  ok: $1"
    else
        echo "  VIRHE: $1 — odotettu '$2', saatiin '$3'"
        virheita=1
    fi
}

echo "vahtikoira: kova restart"
tarkista "terve mysql jätetään rauhaan" "caddy webui" "$(aja healthy)"
tarkista "epäterve mysql restartataan"  "caddy webui mysql" "$(aja unhealthy)"

echo "vahtikoira: terveystarkistus"
tarkista "vastaava Caddy tulkitaan terveeksi" 0 "$(CURL_TILA=ylhaalla "$JUURI/vahtikoira" --hiljaa >/dev/null 2>&1; echo $?)"

exit "$virheita"
