# Technik und Quellen

## Architektur

Die vorhandene AMP-AppConfigId und Repository-ID bleiben stabil. Das Settings-Manifest bietet Domain, Upstream und Betriebsart; E-Mail und abweichenden bestehenden Zertifikatsspeicher unter Erweitert. AMP uebergibt Werte als Umgebungsvariablen, nicht als Shellcode. Ports kommen ueber ihre AMP-Refs `HttpPort`/`HttpsPort`.

AMP startet `/bin/bash` mit einem versionierten Hilfsskript. Dieses prueft Werte, Pfade und exklusive Instanzsperre, erstellt eine Caddy-Konfiguration, validiert sie und ersetzt sich per `exec` durch `caddy run`. AMP-SIGTERM erreicht deshalb den selben Prozess. Es entsteht kein zusaetzlicher Hintergrunddienst. Die Vorlage ist fuer das persoenliche Repository gedacht, nicht als von CubeCoders angenommenes offizielles Template.

Die `Caddyfile` wird absichtlich nicht als JSON/INI im AMP-Metaconfig behandelt. Das leere Metaconfig-Manifest ist korrekt: Die Runtime generiert `private/Caddyfile.generated` mit geprueften Werten. Der Generator kann die KVP/Manifeste ueber Import Template laden; ein blosser Generator-Export ersetzt weder die getesteten Runtime-Dateien noch die CI. Keine neue Generator-Runde fuer den normalen Betreiber notwendig.

Caddy v2.11.4 wird samt exakter Archivpruefsumme festgelegt. Die Betriebsdateien werden aus einem bestimmten Git-Commit bezogen, nicht waehrend eines halbfertigen main-Updates gemischt. `runtime-version.json` dokumentiert Commit und Datei-Pruefsummen. Versionsupdates muessen diese Bindung gemeinsam aktualisieren und die Tests erneut ausfuehren. Kein taeglicher ungepruefter Wechsel auf `latest`.

Eine gezielte HTTP-308-Regel verhindert, dass ein intern genutzter Port 18443 in eine oeffentliche Umleitung geraet. Kein allgemeines Dateiserver-Root. Private Konfigurationspfade sind gesperrt; andere Spielpfade gehen unveraendert an den Upstream. `X-Real-IP` wird ersetzt, `Forwarded` entfernt. Die Spielanwendung muss nur unmittelbare vertrauenswuerdige Proxyadressen akzeptieren. Keine fremden IP-Header pauschal glauben.

Caddys native Speicherroutinen und Zertifikatserneuerung bleiben erhalten. Die Runtime migriert keine privaten Schluessel. Neue Instanzen verwenden ihren eigenen privaten Speicher; bestehende native Speicher werden anhand des bisherigen Betriebs beibehalten. Diese Wahl wird persistent fixiert. Ein ungewoehnliches altes Storage-/Importprofil verlangt eine explizite vorhandene Speicherangabe.

## Nachweisgrenzen

Unit-Tests mit einer kontrollierten Binary-Attrappe pruefen Eingaben und Dateiverhalten; das ist keine Caddy-Integration. Ein gesonderter GitHub-Test verwendet das echte verifizierte Caddy, einen lokalen Backendserver und eine nur im Testprozess vertraute CA. Er prueft HTTPS, Redirect, POST/Cookies/Origin, ueberschriebene Header, private Pfade, WebSocket-Upgrade, Neustart mit gleichem CA-Speicher und Backend-Ausfall. Keine echte Spielwelt wird gestartet; kein Beweis fuer Socket.IO-Spielregeln oder AMP-Lizenz-/Netzwerkmechanik.

Kein Zugriff auf Philipps privaten Server durch diesen Entwicklungsauftrag. Vor Produktion sind die tatsaechliche Template-Aktualisierung und zwei AMP-Felder zu pruefen. Caddy kann eine fehlende Spiel-.env beziehungsweise Deutschlanddaten nicht reparieren.

## Primaerquellen

- Ausgangsgenerator: https://iceofwraith.github.io/GenericConfigGen/
- AMP Generic-Modul, Settings, Ports, Update-Stufen: https://github.com/CubeCoders/AMP/wiki/Configuring-the-%27Generic%27-AMP-module
- Gezieltes Template-Update: https://discourse.cubecoders.com/t/how-to-update-amp-to-the-latest-version/2297
- Caddy Release: https://github.com/caddyserver/caddy/releases/tag/v2.11.4
- Caddy CLI und Signale: https://caddyserver.com/docs/command-line
- Caddy globale Ports/Storage/Admin: https://caddyserver.com/docs/caddyfile/options
- Caddy Reverse Proxy und WebSockets: https://caddyserver.com/docs/caddyfile/directives/reverse_proxy
- Zertifikate: https://caddyserver.com/docs/automatic-https
- Datenverzeichnisse: https://caddyserver.com/docs/conventions

Keine neuen gebuehrenpflichtigen Dienste, Plugins oder Konten. Caddy stammt aus dem offiziellen Projekt; seine Lizenz wird beim Installieren als CADDY-LICENSE erhalten. Dieses Repository enthaelt eigene Betriebsdateien und Tests, keine fremden Audio-/Bild-/Schluesseldateien.
