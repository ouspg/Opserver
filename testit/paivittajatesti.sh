#!/usr/bin/env bash
# Automaattipäivittäjän logiikka: päivitys, palautus rikkinäisestä versiosta,
# ei uudelleenyritystä samalle versiolle, ei päivitystä jos sivu on jo rikki.
# Oikea git (paikallinen origin), stubatut asenna/varmuuskopio/savutesti/curl.
# Ei vaadi Dockeria eikä verkkoa.
set -euo pipefail

JUURI="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t
export LOKI="$T/loki"
virheita=0

# sudo -u X komento → komento; flock/sleep/pgrep neutraaleiksi; curl kirjaa issuen.
mkdir "$T/bin"
cat > "$T/bin/sudo" <<'EOF'
#!/usr/bin/env bash
[[ "$1" == -u ]] && shift 2
exec "$@"
EOF
printf '#!/bin/sh\nexit 0\n' > "$T/bin/flock"
printf '#!/bin/sh\nexit 0\n' > "$T/bin/sleep"
printf '#!/bin/sh\n[ -n "$PIPELINE_KAYNNISSA" ]\n' > "$T/bin/pgrep"
cat > "$T/bin/curl" <<'EOF'
#!/usr/bin/env bash
echo "issue: $(cat)" >> "$LOKI"
EOF
chmod +x "$T/bin"/*
export PATH="$T/bin:$PATH"

# Origin + tuotannon klooni. Versio on "rikki" jos siinä on RIKKI-tiedosto.
git init -q -b main "$T/origin"
cd "$T/origin"
cp "$JUURI/paivittaja" .
mkdir testit
cat > asenna <<'EOF'
#!/usr/bin/env bash
echo "asenna $(git rev-parse --short HEAD)" >> "$LOKI"
EOF
cat > varmuuskopio <<'EOF'
#!/usr/bin/env bash
echo "varmuuskopio $*" >> "$LOKI"; echo /tmp/dumppi.sql.gz
EOF
cat > testit/savutesti.sh <<'EOF'
#!/usr/bin/env bash
[[ ! -f RIKKI && -z "${SIVU_RIKKI:-}" ]]
EOF
chmod +x asenna varmuuskopio testit/savutesti.sh
git add -A && git commit -qm v1
git clone -q "$T/origin" "$T/tuotanto"
echo "GITHUB_ISSUE_TOKEN=x" > "$T/tuotanto/.env"

uusi_commit() { (cd "$T/origin" && "$@" && git add -A && git commit -qm "$RANDOM" && git rev-parse HEAD); }
aja() { : > "$LOKI"; (cd "$T/tuotanto" && ./paivittaja >/dev/null 2>&1) || true; }
head_() { git -C "$T/tuotanto" rev-parse HEAD; }
odota() {  # kuvaus, ehto
    if eval "$2"; then echo "[OK]   $1"; else echo "[FAIL] $1"; echo "--- loki:"; cat "$LOKI"; virheita=$((virheita + 1)); fi
}

hyva=$(uusi_commit touch uusi_ominaisuus)
PIPELINE_KAYNNISSA=1 aja
odota "pipeline käynnissä → lopetetaan heti (ei edes fetchiä)" \
    '[[ ! -s "$LOKI" && $(git -C "$T/tuotanto" rev-parse origin/main) != "$hyva" ]]'

aja
odota "uusi versio asennetaan" '[[ $(head_) == "$hyva" ]] && grep -q "asenna ${hyva:0:7}" "$LOKI"'
odota "varmuuskopio ennen asennusta" 'grep -q "^varmuuskopio" "$LOKI"'
odota "onnistuneesta ei issueta" '! grep -q issue "$LOKI"'

aja
odota "ei muutosta → ei asennusta" '! grep -q "^asenna" "$LOKI"'

rikki=$(uusi_commit touch RIKKI)
aja
odota "rikkinäinen versio palautetaan" '[[ $(head_) == "$hyva" ]]'
odota "kanta palautetaan dumpista" 'grep -q "varmuuskopio --palauta /tmp/dumppi.sql.gz" "$LOKI"'
odota "vanha versio asennetaan uudelleen" 'grep -q "asenna ${hyva:0:7}" "$LOKI"'
odota "issue luodaan" 'grep -q "issue:.*${rikki:0:7}" "$LOKI"'

aja
odota "samaa versiota ei yritetä uudelleen" '[[ ! -s "$LOKI" ]]'

korjattu=$(uusi_commit rm RIKKI)
SIVU_RIKKI=1 aja
odota "ei päivitetä jos sivu on jo rikki" '[[ $(head_) == "$hyva" ]] && ! grep -q "^asenna" "$LOKI"'
odota "rikkinäisestä sivusta issue" 'grep -q "issue:.*${korjattu:0:7}" "$LOKI"'
SIVU_RIKKI=1 aja
odota "issue vain kerran per versio" '! grep -q issue "$LOKI"'

aja
odota "seuraava versio asennetaan epäonnistuneen jälkeen" '[[ $(head_) == "$korjattu" ]]'

[[ $virheita -eq 0 ]] && echo "Kaikki läpi." || { echo "$virheita epäonnistui."; exit 1; }
