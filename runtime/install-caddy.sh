#!/usr/bin/env bash
# Installs only the verified Caddy binary. Never touches user settings or certificates.
set -Eeuo pipefail
umask 077
export LC_ALL=C
BASE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
ARCHIVE="$BASE/caddy_2.11.4_linux_amd64.tar.gz"
EXPECTED=527fbf917c39189a1e3b31d34fa955601680b2d5c8055d2a87b8b9588dec7bb9
TMP=''
fail() { printf '[AMP-CADDY] INSTALLATIONSFEHLER: %s\n' "$*" >&2; exit 1; }
cleanup() { [[ -z "$TMP" ]] || rm -rf -- "$TMP"; }
trap cleanup EXIT
[[ "$(uname -s)" == Linux && "$(uname -m)" == x86_64 ]] || fail 'Diese Ausgabe benoetigt Linux x86_64.'
for tool in flock sha256sum tar mktemp; do command -v "$tool" >/dev/null || fail "Werkzeug fehlt: $tool"; done
[[ ! -L "$BASE/private" ]] || fail 'private darf kein symbolischer Link sein.'
mkdir -p -- "$BASE/private"
[[ -O "$BASE/private" ]] || fail 'private gehoert nicht dem AMP-Benutzer.'
chmod 700 -- "$BASE/private"
[[ ! -L "$BASE/private/runtime.lock" ]] || fail 'Ungueltige Lock-Datei.'
exec 9>"$BASE/private/runtime.lock"
flock -n 9 || fail 'Caddy laeuft noch. Vor Update nur die Caddy-Anwendung in AMP stoppen.'
[[ -f "$ARCHIVE" && ! -L "$ARCHIVE" ]] || fail 'Downloadarchiv fehlt. Downloadschritt in AMP pruefen.'
actual=$(sha256sum -- "$ARCHIVE"); actual=${actual%% *}
[[ "$actual" == "$EXPECTED" ]] || fail 'SHA-256 stimmt nicht. Vorhandenes Caddy und Zertifikate bleiben erhalten. Download erneut pruefen.'
TMP=$(mktemp -d "$BASE/.caddy-install.XXXXXXXX")
tar -xzf "$ARCHIVE" --no-same-owner --no-same-permissions -C "$TMP" -- caddy LICENSE
[[ -f "$TMP/caddy" && ! -L "$TMP/caddy" ]] || fail 'Archiv enthaelt kein regulaeres Caddy-Programm.'
chmod 755 -- "$TMP/caddy"
version=$("$TMP/caddy" version)
[[ "$version" == 'v2.11.4 '* || "$version" == 'v2.11.4' ]] || fail 'Unerwartete Programmversion.'
[[ ! -L "$BASE/caddy" && ! -L "$BASE/caddy.previous" ]] || fail 'Symbolische Links an Programmdateien nicht erlaubt.'
if [[ -f "$BASE/caddy" ]] && ! cmp -s -- "$BASE/caddy" "$TMP/caddy"; then cp -p -- "$BASE/caddy" "$BASE/caddy.previous"; fi
mv -f -- "$TMP/caddy" "$BASE/caddy"
# Keep the application license under an unambiguous filename.
[[ ! -L "$BASE/CADDY-LICENSE" ]] || fail 'Ungueltige Lizenzdatei.'
mv -f -- "$TMP/LICENSE" "$BASE/CADDY-LICENSE"
printf '[AMP-CADDY] Caddy v2.11.4 installiert; Archiv SHA-256 geprueft.\n'
printf '[AMP-CADDY] In Configuration -> HTTPS-Zugang Domain und Spielziel pruefen. Danach Start.\n'
