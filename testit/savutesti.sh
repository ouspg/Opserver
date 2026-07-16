#!/usr/bin/env bash
# Savutesti: varmistaa, että Docker-kontit (MySQL + WebUI) toimivat oikein.
# Aja: ./testit/savutesti.sh
# Oletus: kontit ovat jo käynnissä (docker compose up -d).

# EI set -e: savutesti kerää virheet itse (VIRHEET-laskuri) ja raportoi lopussa.
# set -e abortoisi ensimmäisen kaatuvan komennon kohdalla ENNEN yhteenvetoa —
# ja sourcattuna (esim. ./status) veisi koko interaktiivisen shellin hiljaa alas,
# jolloin "ei tulosta mitään". Ilman -e jokainen tarkistus ajetaan ja [FAIL]it näkyvät.
set -uo pipefail

# Projektin juuri = lähin hakemisto (nykyhakemistosta ylöspäin), jossa on
# docker-compose.yml. Riippumaton siitä miten skripti käynnistetään (suoraan
# testit/-alta, repo-juuresta tai status-wräpperin kautta sourcaten).
PROJO_JUURI="$PWD"
while [[ "$PROJO_JUURI" != "/" && ! -f "$PROJO_JUURI/docker-compose.yml" ]]; do
    PROJO_JUURI="$(dirname "$PROJO_JUURI")"
done
[[ -f "$PROJO_JUURI/docker-compose.yml" ]] || {
    echo "Ei löytynyt projektin juurta (docker-compose.yml) hakemistosta $PWD ylöspäin."
    exit 1
}

# WebUI-osoite: sama WEBUI_OSOITE-muuttuja kuin cliui (cliui/tutkimusnaytto.py).
# Ympäristö ohittaa .env:n, .env ohittaa oletuksen; loppukauttaviiva pois.
WEBUI="${WEBUI_OSOITE:-$(grep -E '^WEBUI_OSOITE=' "$PROJO_JUURI/.env" 2>/dev/null | tail -1 | cut -d= -f2-)}"
WEBUI="${WEBUI:-http://localhost:12121}"
WEBUI="${WEBUI%/}"

VIRHEET=0
AUTH_ARGS=()

# Värit: epäonnistumiset punaisella erottuvat heti silmämääräisesti. Pois päältä
# jos stdout ei ole pääte (putki/tiedosto) tai NO_COLOR on asetettu.
if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
    VARI_PUN=$'\033[31m'; VARI_VIH=$'\033[32m'; VARI_KEL=$'\033[33m'; VARI_L=$'\033[0m'
else
    VARI_PUN=''; VARI_VIH=''; VARI_KEL=''; VARI_L=''
fi

ok()   { printf "${VARI_VIH}[OK]${VARI_L}   %s\n" "$1"; }
fail() { printf "${VARI_PUN}[FAIL] %s${VARI_L}\n" "$1"; VIRHEET=$((VIRHEET + 1)); }
info() { printf "${VARI_KEL}[INFO]${VARI_L} %s\n" "$1"; }

# curl-kääre: lisää Basic Auth -tunnukset, jos autentikointi todettiin käytössä.
hae() {
    if [[ ${#AUTH_ARGS[@]} -gt 0 ]]; then
        curl -sf --max-time 5 "${AUTH_ARGS[@]}" "$@"
    else
        curl -sf --max-time 5 "$@"
    fi
}

# Probe: kokeile etusivua ilman tunnuksia. 401 => autentikointi päällä =>
# lataa WEBUI_AUTH_* .env:stä ja ota käyttöön lopuille pyynnöille.
maarita_autentikointi() {
    local koodi env_tiedosto kayttaja salasana
    koodi=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$WEBUI/" 2>/dev/null) || koodi=000
    if [[ "$koodi" != "401" ]]; then
        info "Autentikointi ei käytössä (etusivu palautti $koodi)"
        return
    fi
    env_tiedosto="$PROJO_JUURI/.env"
    kayttaja=$(grep -E '^WEBUI_AUTH_KAYTTAJA=' "$env_tiedosto" | cut -d= -f2-) || true
    salasana=$(grep -E '^WEBUI_AUTH_SALASANA=' "$env_tiedosto" | cut -d= -f2-) || true
    if [[ -n "$kayttaja" && -n "$salasana" ]]; then
        AUTH_ARGS=(-u "$kayttaja:$salasana")
        info "Autentikointi käytössä — käytetään .env:n tunnuksia"
    else
        fail "Autentikointi käytössä (401), mutta WEBUI_AUTH_* puuttuu .env:stä"
    fi
}

tarkista_http() {
    local nimi=$1
    local url=$2
    local odotettu_sisalto=${3:-}

    vastaus=$(hae "$url" 2>/dev/null) || { fail "$nimi ei vastaa ($url)"; return; }

    if [[ -n "$odotettu_sisalto" ]] && ! echo "$vastaus" | grep -q "$odotettu_sisalto"; then
        fail "$nimi — vastaus ei sisällä '$odotettu_sisalto'"
    else
        ok "$nimi"
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
    local kontti_id kontti_kuva uusin_kuva
    kontti_id=$(docker compose ps -q webui 2>/dev/null | head -1) || kontti_id=""
    if [[ -z "$kontti_id" ]]; then
        fail "WebUI-kuvan tuoreus — konttia ei löydy"
        return
    fi

    kontti_kuva=$(docker inspect "$kontti_id" --format '{{.Image}}' 2>/dev/null) || kontti_kuva=""
    uusin_kuva=$(docker inspect opserver-webui --format '{{.Id}}' 2>/dev/null) || uusin_kuva=""

    if [[ -z "$kontti_kuva" || -z "$uusin_kuva" ]]; then
        fail "WebUI-kuvan tuoreus — ei saatu image-tietoja"
        return
    fi

    if [[ "$kontti_kuva" != "$uusin_kuva" ]]; then
        fail "WebUI-kuva on vanhentunut — aja: docker compose up -d webui"
    else
        ok "WebUI-kuva ajan tasalla"
    fi
}

echo "=== Opserver savutesti ==="
echo ""

# 1. Kontit
tarkista_kontti "MySQL-kontti käynnissä"  "mysql"
tarkista_kontti "WebUI-kontti käynnissä"  "webui"

echo ""

# Autentikoinnin tunnistus: probe ilman tunnuksia, lataa .env:n tunnukset jos 401
maarita_autentikointi

echo ""

# 2. WebUI HTTP
tarkista_http "WebUI etusivu"                "$WEBUI/"                     "Opserver"
tarkista_http "API /korkeakoulut"            "$WEBUI/api/korkeakoulut"     ""
tarkista_http "API /kurssit"                 "$WEBUI/api/kurssit"          ""
tarkista_http "API /tutkimukset"             "$WEBUI/api/tutkimukset"      ""

# Raportti-endpoint: tarkistetaan jokaiselle tutkimukselle (jos niitä on).
# Erottele kolme tilaa: (a) /api/tutkimukset ei vastaa → FAIL (ei saa väittää
# ettei tutkimuksia ole, kun tosiasiassa endpoint on alhaalla); (b) vastaa mutta
# ei kelvollista tutkimuslistaa → FAIL; (c) kelvollinen mutta tyhjä lista → OK.
if ! tutkimukset_json=$(hae "$WEBUI/api/tutkimukset" 2>/dev/null); then
    fail "API /raportti — /api/tutkimukset ei vastaa, ei voi tarkistaa"
elif ! slugit=$(printf '%s' "$tutkimukset_json" | python3 -c \
        "import sys,json; d=json.load(sys.stdin); assert isinstance(d,list); [print(t['Slug']) for t in d]" 2>/dev/null); then
    fail "API /raportti — /api/tutkimukset ei palauttanut kelvollista tutkimuslistaa"
elif [[ -z "$slugit" ]]; then
    ok "API /raportti — ei tutkimuksia tarkistettavana"
else
    raportti_ok=true
    while IFS= read -r slug; do
        vastaus=$(hae "$WEBUI/api/tutkimukset/$slug/raportti" 2>/dev/null) || { raportti_ok=false; break; }
        printf '%s' "$vastaus" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'osiot' in d" 2>/dev/null || { raportti_ok=false; break; }
    done <<< "$slugit"
    if $raportti_ok; then
        ok "API /raportti vastaa oikein (kaikki tutkimukset)"
    else
        fail "API /raportti — virheellinen vastaus tutkimukselle '$slug'"
    fi
fi

echo ""

# 3. Kuvan tuoreus
tarkista_kuva_tuoreus

echo ""

# 4. MySQL-yhteys: kurssit-endpoint tekee DB-kyselyn — jo testattu yllä.
#    Lisätarkistus: tarkistetaan, että korkeakoulut-vastaus on JSON-taulukko.
vastaus_kk=$(hae "$WEBUI/api/korkeakoulut" 2>/dev/null) || vastaus_kk=""
if printf '%s' "$vastaus_kk" | python3 -c "import sys,json; d=json.load(sys.stdin); assert isinstance(d,list)" 2>/dev/null; then
    ok "MySQL-yhteys toimii (korkeakoulut palautti JSON-taulukon)"
else
    fail "MySQL-yhteys epäonnistui tai vastaus ei ole JSON-taulukko"
fi

echo ""

if [[ $VIRHEET -eq 0 ]]; then
    printf "${VARI_VIH}Kaikki tarkistukset lapi. Kontit toimivat oikein.${VARI_L}\n"
    exit 0
else
    printf "${VARI_PUN}%s tarkistus epaonnistui.${VARI_L}\n" "$VIRHEET"
    exit 1
fi
