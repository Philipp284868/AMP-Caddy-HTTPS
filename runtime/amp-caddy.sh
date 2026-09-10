#!/usr/bin/env bash
# AMP Caddy runtime. No eval, no shell-sourced user configuration, no network download.
set -Eeuo pipefail
umask 077
export LC_ALL=C
BASE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
PRIVATE="$BASE/private"
BIN="$BASE/caddy"
CONFIG="$PRIVATE/Caddyfile.generated"
TMP=''
fail() { printf '[AMP-CADDY] FEHLER: %s\n' "$*" >&2; exit 1; }
cleanup() { [[ -z "$TMP" ]] || rm -f -- "$TMP"; }
trap cleanup EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
mode=${1:-run}
[[ "$mode" == run || "$mode" == prepare ]] || fail 'Erlaubt: run oder prepare.'
[[ -x "$BIN" && -f "$BIN" && ! -L "$BIN" ]] || fail 'Caddy fehlt oder ist nicht ausfuehrbar. In AMP einmal Update ausfuehren.'
for tool in flock mktemp realpath; do command -v "$tool" >/dev/null || fail "Systemwerkzeug fehlt: $tool (Debian: util-linux/coreutils)."; done
# User values enter via environment variables, never interpolated into a shell command.
domain=${CADDY_DOMAIN:-}
upstream=${CADDY_UPSTREAM:-127.0.0.1:7777}
operation=${CADDY_MODE:-proxy}
email=${CADDY_ACME_EMAIL:-}
http=${CADDY_HTTP_PORT:-18080}
https=${CADDY_HTTPS_PORT:-18443}
bind=${CADDY_BIND_ADDRESS:-0.0.0.0}
storage_override=${CADDY_STORAGE_DIRECTORY:-}
check_dns() {
  local name=$1 label
  [[ "$name" =~ ^[A-Za-z0-9.-]+$ ]] || return 1
  [[ ${#name} -le 253 && "$name" != *..* && "$name" != .* && "$name" != *. ]] || return 1
  local -a labels
  IFS=. read -r -a labels <<< "$name"
  for label in "${labels[@]}"; do
    [[ ${#label} -ge 1 && ${#label} -le 63 && "$label" =~ ^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?$ ]] || return 1
  done
}
check_ipv4() {
  local ip=$1 octet
  [[ "$ip" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || return 1
  local -a octets
  IFS=. read -r -a octets <<< "$ip"
  for octet in "${octets[@]}"; do
    [[ ${#octet} -le 3 ]] && ((10#$octet <= 255)) || return 1
    [[ ${#octet} == 1 || ${octet:0:1} != 0 ]] || return 1
  done
}
check_port() { [[ "$1" =~ ^[1-9][0-9]{0,4}$ ]] && (( 10#$1 >= $2 && 10#$1 <= 65535 )); }
check_path() {
  [[ "$1" == /* && "$1" != *[$'\n\r\t']* && "$1" != *'"'* && "$1" != *\\* && "$1" != *'{'* && "$1" != *'}'* ]] || fail 'Speicherpfad muss absolut und ohne Steuerzeichen, Anfuehrungszeichen oder Platzhalter sein.'
}
[[ -n "$domain" ]] || fail 'In AMP unter HTTPS-Zugang die Domain eintragen, z.B. gaminglive.mooo.com (ohne https://).'
check_dns "$domain" && [[ "$domain" == *.* && ! "$domain" =~ ^[0-9.]+$ ]] || fail 'Domain ungueltig: nur einen DNS-Namen ohne https://, Port, Pfad, Leerzeichen oder Wildcard eingeben.'
domain=${domain,,}
[[ "$domain" != *.invalid && "$domain" != *.test && "$domain" != *.localhost && "$domain" != *.local && "$domain" != example.com && "$domain" != *.example.com ]] || fail 'Eine eigene oeffentliche Domain ist erforderlich; kein Test-/Beispielname.'
check_port "$http" 1024 && check_port "$https" 1024 && [[ "$http" != "$https" ]] || fail 'HTTP- und HTTPS-Port muessen verschieden und zwischen 1024 und 65535 sein.'
[[ "$operation" == proxy || "$operation" == test ]] || fail 'Betriebsart muss proxy oder test sein.'
[[ "$bind" =~ ^[0-9.]+$ ]] && check_ipv4 "$bind" || fail 'Diese Vorlage verwendet IPv4. Die AMP-Bind-Adresse muss eine gueltige IPv4-Adresse sein.'
if [[ -n "$email" ]]; then
  [[ ${#email} -le 254 && "$email" =~ ^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}$ ]] || fail 'ACME-E-Mail ungueltig; optional leer lassen.'
fi
[[ "$upstream" =~ ^([a-zA-Z0-9.-]+):([0-9]+)$ ]] || fail 'Spielziel als IPv4/DNS-Name:Port eingeben, z.B. 127.0.0.1:7777; ohne Protokoll oder Pfad.'
uphost=${BASH_REMATCH[1]}; upport=${BASH_REMATCH[2]}
check_dns "$uphost" && check_port "$upport" 1 || fail 'Hostname oder Port des internen Spielziels ist ungueltig.'
if [[ "$uphost" =~ ^[0-9.]+$ ]]; then check_ipv4 "$uphost" || fail 'IPv4-Adresse des Spielziels ist ungueltig.'; fi
[[ "${uphost,,}" != "$domain" ]] || fail 'Spielziel darf nicht dieselbe oeffentliche Domain sein (Proxy-Schleife). Internen Spielserver angeben.'
[[ "$upport" != "$http" && "$upport" != "$https" ]] || fail 'Spielport darf in dieser Vorlage keinem der beiden Caddy-Ports entsprechen.'
[[ ! -L "$PRIVATE" ]] || fail 'private darf kein symbolischer Link sein.'
mkdir -p -- "$PRIVATE"
[[ -O "$PRIVATE" ]] || fail 'private gehoert nicht dem AMP-Benutzer.'
chmod 700 -- "$PRIVATE"
[[ ! -L "$PRIVATE/runtime.lock" ]] || fail 'Ungueltige Lock-Datei.'
exec 9>"$PRIVATE/runtime.lock"
flock -n 9 || fail 'Diese Caddy-Installation laeuft bereits oder wird aktualisiert. Erst in AMP stoppen.'
# Keep previous certificate storage. Never copy, erase or silently replace certificates.
state_file="$PRIVATE/storage.path"
if [[ -e "$state_file" || -L "$state_file" ]]; then
  [[ -f "$state_file" && ! -L "$state_file" ]] || fail 'Ungueltige Speicherzuordnung.'
  storage=$(cat -- "$state_file")
  check_path "$storage"
  [[ -d "$storage" && -r "$storage" && -w "$storage" ]] || fail 'Bisheriger Zertifikatsspeicher fehlt/ist unzugreifbar. Mount/Rechte wiederherstellen; keinen neuen Speicher anlegen.'
  if [[ -n "$storage_override" ]]; then
    check_path "$storage_override"
    [[ "$(realpath -m -- "$storage_override")" == "$storage" ]] || fail 'Zertifikatsspeicher wurde geaendert. Fuer einen Umzug erst sichern und die dokumentierte Migration verwenden.'
  fi
else
  if [[ -n "$storage_override" ]]; then
    check_path "$storage_override"
    storage=$(realpath -m -- "$storage_override")
    [[ -d "$storage" ]] || fail 'Expliziter Zertifikatsspeicher existiert nicht. Einen vorhandenen persistenten Ordner verwenden.'
  else
    [[ -n ${HOME:-} ]] || fail 'HOME fehlt; Zertifikatsspeicher muss in AMP explizit angegeben werden.'
    native="${XDG_DATA_HOME:-$HOME/.local/share}/caddy"
    check_path "$native"
    if [[ -f "$BASE/Caddyfile" ]] && grep -Eq '^[[:space:]]*(storage[[:space:]]|import[[:space:]])' "$BASE/Caddyfile"; then
      fail 'Vorhandene Caddyfile nutzt storage/import. Ihren bisherigen Speicher zuerst als Zertifikatsspeicher in AMP angeben. Original bleibt unveraendert.'
    fi
    if [[ -d "$native/certificates" || -f "$BASE/Caddyfile" ]]; then
      storage=$(realpath -m -- "$native")
      [[ -d "$storage" ]] || fail 'Alte Caddyfile gefunden, aber ihr Standardspeicher fehlt. Bisherigen Speicher pruefen statt Zertifikate neu anzulegen.'
      printf '[AMP-CADDY] Vorhandener Caddy-Speicher wird beibehalten: %s\n' "$storage"
    else
      storage="$PRIVATE/caddy-data"
      [[ ! -L "$storage" ]] || fail 'Neuer Zertifikatsspeicher darf kein symbolischer Link sein.'
      mkdir -p -- "$storage"
      chmod 700 -- "$storage"
    fi
  fi
fi
check_path "$storage"
[[ -r "$storage" && -w "$storage" ]] || fail 'Zertifikatsspeicher nicht lesbar/schreibbar.'
# No pre-existing symlink may redirect generated files into another application.
for f in "$CONFIG" "$CONFIG.previous" "$state_file"; do [[ ! -L "$f" ]] || fail 'Symbolischer Link an einer verwalteten Konfigurationsdatei nicht erlaubt.'; done
TMP=$(mktemp "$PRIVATE/Caddyfile.pending.XXXXXXXX")
cat >"$TMP" <<EOF
# Automatisch erzeugt. Einstellungen in AMP bearbeiten, nicht diese Datei.
{
    admin off
    persist_config off
    http_port $http
    https_port $https
    auto_https disable_redirects
    default_bind $bind
    grace_period 10s
    servers {
        protocols h1 h2
    }
    storage file_system {
        root "$storage"
    }
EOF
[[ -z "$email" ]] || printf '    email %s\n' "$email" >>"$TMP"
printf '}\n\nhttp://%s {\n    redir https://%s{uri} 308\n}\n\nhttps://%s {\n' "$domain" "$domain" "$domain" >>"$TMP"
cat >>"$TMP" <<'EOF'
    @private path /.env* /.git /.git/* /private /private/* /Caddyfile /Caddyfile.* /GenericModule.kvp
    handle @private {
        respond "Nicht gefunden." 404
    }
EOF
if [[ "$operation" == test ]]; then
  cat >>"$TMP" <<'EOF'
    handle {
        respond "HTTPS funktioniert. Caddy ist bereit; dies ist nur der Verbindungstest, nicht das Spiel." 200
    }
EOF
else
  cat >>"$TMP" <<EOF
    handle {
        reverse_proxy $upstream {
            header_up X-Real-IP {remote_host}
            header_up -Forwarded
            transport http {
                dial_timeout 5s
            }
        }
    }
    handle_errors {
        header Cache-Control "no-store"
        respond "HTTPS-Zugang erreichbar. Der Spielserver ist momentan nicht erreichbar. Bitte spaeter erneut versuchen." 503
    }
EOF
fi
printf '}\n' >>"$TMP"
printf '[AMP-CADDY] Pruefe Konfiguration. Domain=%s; Modus=%s; intern=%s/%s; Spielziel=%s\n' "$domain" "$operation" "$http" "$https" "$upstream"
# A failed validation keeps both the original manual file and last good generated file.
"$BIN" validate --config "$TMP" --adapter caddyfile || fail 'Caddy-Konfiguration ungueltig. Letzte gueltige Konfiguration wurde nicht ersetzt.'
if [[ -f "$CONFIG" ]] && ! cmp -s -- "$TMP" "$CONFIG"; then cp -p -- "$CONFIG" "$CONFIG.previous"; fi
mv -f -- "$TMP" "$CONFIG"; TMP=''
if [[ ! -f "$state_file" ]]; then
  TMP=$(mktemp "$PRIVATE/storage.pending.XXXXXXXX")
  printf '%s\n' "$storage" >"$TMP"
  mv -- "$TMP" "$state_file"; TMP=''
fi
printf '[AMP-CADDY] Konfiguration OK. Zertifikate: %s\n' "$storage"
printf '[AMP-CADDY] Oeffentlich: https://%s (ohne internen Port). Zertifikat/Internet/Spiel separat pruefen.\n' "$domain"
[[ "$mode" == run ]] || exit 0
# The exec preserves PID and the lock; SIGTERM reaches Caddy, not a detached child.
exec "$BIN" run --config "$CONFIG" --adapter caddyfile
