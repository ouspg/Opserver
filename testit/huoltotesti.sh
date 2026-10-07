#!/usr/bin/env bash
# Caddyfilen päivityskatkokäytös kertakäyttökonteissa (vaatii Dockerin):
#   (i)  webui alhaalla < 30 s → pyyntö odottaa ja onnistuu, kun webui nousee
#   (ii) webui alhaalla > 30 s → 503 + Retry-After: HTML-huoltosivu, /api/* → JSON
# Ajaa oikean Caddyfilen, josta vain sivustoosoite vaihdetaan http://:8080:ksi ja
# ACME-tls-lohko poistetaan. Upstream = `caddy respond` aliaksella webui.
set -euo pipefail
JUURI="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
P=huoltotesti
KUVA=caddy:2-alpine
siivoa() { docker rm -f $P-caddy $P-webui >/dev/null 2>&1 || true; docker network rm $P >/dev/null 2>&1 || true; }
trap siivoa EXIT
siivoa

konfiguraatio=$(awk 'NR == 1 { print "http://:8080 {"; next }
                     /^\ttls \{/ { ohita = 1 }
                     ohita { if (/^\t\}/) ohita = 0; next }
                     { print }' "$JUURI/Caddyfile" | base64 | tr -d '\n')
docker network create $P >/dev/null
docker run -d --name $P-caddy --network $P -e CF="$konfiguraatio" $KUVA sh -c \
    'echo "$CF" | base64 -d > /tmp/Caddyfile && exec caddy run --adapter caddyfile --config /tmp/Caddyfile' >/dev/null
webui_ylos() {
    docker run -d --name $P-webui --network $P --network-alias webui $KUVA \
        caddy respond --listen :12121 --body ok >/dev/null
}
# Tuloste: "<status> <sekunnit>" + otsikot + runko
pyynto() {
    docker run --rm --network $P curlimages/curl -s -i -m 60 \
        -w '\n%{http_code} %{time_total}\n' "http://$P-caddy:8080$1"
}

virheita=0
tarkista() { grep -q -- "$2" <<< "$3" || { echo "[FAIL] $1: ei löydy '$2'"; echo "$3"; virheita=1; }; }

webui_ylos
for _ in $(seq 30); do pyynto / 2>/dev/null | grep -q '^200 ' && break; sleep 1; done
tarkista "perustila" '^200 ' "$(pyynto /)"

# (i) lyhyt katko: kontti poistetaan (kuten compose up uudelleenluonnissa) ja
# nostetaan 6 s kuluttua; pyyntö odottaa Caddyssä.
docker rm -f $P-webui >/dev/null
tulos=$(mktemp); pyynto /api/kurssit > "$tulos" & pid=$!
sleep 6; webui_ylos; wait $pid
lyhyt=$(cat "$tulos"); rm -f "$tulos"
tarkista "(i) lyhyt katko → 200" '^200 ' "$lyhyt"
tarkista "(i) lyhyt katko → upstreamin runko" '^ok' "$lyhyt"
aika=$(tail -1 <<< "$lyhyt" | cut -d' ' -f2)
awk -v t="$aika" 'BEGIN { exit !(t >= 4) }' || { echo "[FAIL] (i) pyyntö ei odottanut ($aika s)"; virheita=1; }

# (ii) pitkä katko: molemmat pyynnöt rinnakkain (kumpikin odottaa 30 s).
docker rm -f $P-webui >/dev/null
tulos=$(mktemp); pyynto /api/kurssit > "$tulos" & pid=$!
html=$(pyynto /kurssit); wait $pid
api=$(cat "$tulos"); rm -f "$tulos"
tarkista "(ii) HTML 503" '^503 ' "$html"
tarkista "(ii) HTML Retry-After" '^[Rr]etry-[Aa]fter: 10' "$html"
tarkista "(ii) HTML tyyppi" '^[Cc]ontent-[Tt]ype: text/html' "$html"
tarkista "(ii) HTML teksti" 'Palvelua päivitetään' "$html"
tarkista "(ii) HTML automaattinen lataus" 'http-equiv="refresh"' "$html"
tarkista "(ii) API 503" '^503 ' "$api"
tarkista "(ii) API Retry-After" '^[Rr]etry-[Aa]fter: 10' "$api"
tarkista "(ii) API tyyppi" '^[Cc]ontent-[Tt]ype: application/json' "$api"
tarkista "(ii) API runko" '{"huolto": true, "detail": "Palvelua päivitetään"}' "$api"

[[ $virheita -eq 0 ]] && echo "Huoltotesti OK (lyhyt katko odotti ${aika} s)." || exit 1
