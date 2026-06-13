#!/usr/bin/env bash
# Savutesti: varmistaa, että Docker-kontit (MySQL + WebUI) toimivat oikein.
# Aja: ./testit/savutesti.sh
# Oletus: kontit ovat jo käynnissä (docker compose up -d).

set -euo pipefail

WEBUI="http://localhost:12121"
PROJO_JUURI="$(cd "$(dirname "$0")/.." && pwd)"
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

tarkista_kuva_tuoreus() {
    local kontti_id
    kontti_id=$(docker compose ps -q webui 2>/dev/null | head -1)
    if [[ -z "$kontti_id" ]]; then
        fail "WebUI-kuvan tuoreus — konttia ei löydy"
        return
    fi

    local kuva_sha kuva_aika_iso kuva_aika_trunc kuva_epoch lahde_epoch
    kuva_sha=$(docker inspect "$kontti_id" --format '{{.Image}}' 2>/dev/null)
    kuva_aika_iso=$(docker inspect "$kuva_sha" --format '{{.Created}}' 2>/dev/null)
    # "2024-06-13T10:23:45.123Z" → "2024-06-13T10:23:45"
    kuva_aika_trunc="${kuva_aika_iso%%.*}"
    kuva_epoch=$(TZ=UTC date -j -f "%Y-%m-%dT%H:%M:%S" "$kuva_aika_trunc" "+%s" 2>/dev/null)

    if [[ -z "$kuva_epoch" ]]; then
        fail "WebUI-kuvan tuoreus — ei saatu image-aikaa"
        return
    fi

    lahde_epoch=$(
        { find "$PROJO_JUURI/webui" "$PROJO_JUURI/tietokanta" -type f 2>/dev/null
          [[ -f "$PROJO_JUURI/requirements.txt" ]] && echo "$PROJO_JUURI/requirements.txt"
        } | xargs stat -f '%m' 2>/dev/null | sort -rn | head -1
    )

    if [[ -z "$lahde_epoch" ]]; then
        fail "WebUI-kuvan tuoreus — lähdetiedostoja ei löydy"
        return
    fi

    if [[ "$lahde_epoch" -gt "$kuva_epoch" ]]; then
        fail "WebUI-kuva on vanhentunut — aja: docker compose build webui && docker compose up -d webui"
    else
        ok "WebUI-kuva ajan tasalla"
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

echo ""

# 3. Kuvan tuoreus
tarkista_kuva_tuoreus

echo ""

# 4. MySQL-yhteys: kurssit-endpoint tekee DB-kyselyn — jo testattu yllä.
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
