#!/usr/bin/env bash
# Savutesti: varmistaa, että Docker-kontit (MySQL + WebUI) toimivat oikein.
# Aja: ./testit/savutesti.sh
# Oletus: kontit ovat jo käynnissä (docker compose up -d).

set -euo pipefail

WEBUI="http://localhost:12121"
VIRHEET=0

ok()   { printf "[OK]   %s\n" "$1"; }
fail() { printf "[FAIL] %s\n" "$1"; VIRHEET=$((VIRHEET + 1)); }

tarkista_http() {
    local kuvaus=$1
    local url=$2
    local odotettu_sisalto=${3:-}

    vastaus=$(curl -sf --max-time 5 "$url" 2>/dev/null) || { fail "$kuvaus — ei vastausta ($url)"; return; }

    if [[ -n "$odotettu_sisalto" ]] && ! echo "$vastaus" | grep -q "$odotettu_sisalto"; then
        fail "$kuvaus — vastaus ei sisällä '$odotettu_sisalto'"
    else
        ok "$kuvaus"
    fi
}

tarkista_kontti() {
    local kuvaus=$1
    local palvelu=$2
    local tila

    tila=$(docker compose ps --format "{{.State}}" "$palvelu" 2>/dev/null | head -1)
    if [[ "$tila" == "running" ]]; then
        ok "$kuvaus"
    else
        fail "$kuvaus — tila: '${tila:-ei löydy}'"
    fi
}

echo "=== kyberESR savutesti ==="
echo ""

# 1. Kontit
tarkista_kontti "MySQL-kontti käynnissä"  "mysql"
tarkista_kontti "WebUI-kontti käynnissä"  "webui"

echo ""

# 2. WebUI HTTP
tarkista_http "WebUI etusivu"                "$WEBUI/"                     "kyberESR"
tarkista_http "API /korkeakoulut vastaa"     "$WEBUI/api/korkeakoulut"     ""
tarkista_http "API /kurssit vastaa"          "$WEBUI/api/kurssit"          ""
tarkista_http "API /tutkimukset vastaa"      "$WEBUI/api/tutkimukset"      ""

# 3. MySQL-yhteys: kurssit-endpoint tekee DB-kyselyn — jo testattu yllä.
#    Lisätarkistus: tarkistetaan, että korkeakoulut-vastaus on JSON-taulukko.
vastaus_kk=$(curl -sf --max-time 5 "$WEBUI/api/korkeakoulut" 2>/dev/null) || vastaus_kk=""
if echo "$vastaus_kk" | python3 -c "import sys,json; d=json.load(sys.stdin); assert isinstance(d,list)" 2>/dev/null; then
    ok "MySQL-yhteys toimii (korkeakoulut palautti JSON-taulukon)"
else
    fail "MySQL-yhteys epäonnistui tai vastaus ei ole JSON-taulukko"
fi

echo ""

if [[ $VIRHEET -eq 0 ]]; then
    echo "Kaikki tarkistukset lapi. Kontit toimivat oikein."
    exit 0
else
    echo "$VIRHEET tarkistus epaonnistui."
    exit 1
fi
