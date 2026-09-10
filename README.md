# Caddy HTTPS fuer AMP

**Domain eintragen, interne Spieladresse kontrollieren, starten.** Caddy-Konfiguration und Zertifikatsverwaltung werden dann automatisch erledigt. Eigene, nicht von CubeCoders zertifizierte Vorlage fuer **Linux x86_64 / Debian 13, AMP ab 2.8.0.4**. Ein funktionsfaehiger Spielserver bleibt Voraussetzung.

## Einstellungen fuer Philipp

| AMP: Configuration → HTTPS-Zugang | Wert |
| --- | --- |
| Domain | `gaminglive.mooo.com` (ohne `https://`, ohne Port) |
| Interne Spieladresse | `127.0.0.1:7777`, **nur bei gemeinsamem Host-Netzwerk** |
| Betriebsart | `Spiel weiterleiten`; solange das Spiel repariert wird: `Nur HTTPS-Verbindungstest` |

Unter **HTTPS - Erweitert** sind Kontakt-E-Mail und Zertifikatsspeicher optional. Normal leer lassen. Ports bleiben in AMPs Netzwerkeinstellungen: HTTP **18080 TCP**, HTTPS **18443 TCP**. Nur wenn AMP andere Ports zuteilt, Routerweiterleitung passend mitaendern; die erzeugte Caddy-Konfiguration verwendet die tatsaechlich zugeteilten Ports.

## Bestehende Caddy-Instanz auf diese Vorlage umstellen

1. In der bisherigen **Caddy-Anwendung Stop** waehlen. Nicht die Spielwelt, Minecraft oder die gesamte AMP-Hauptverwaltung stoppen. Alte manuelle `Caddyfile`, AMP-Instanzeinstellungen und bisherigen Zertifikatsspeicher sichern. Private Schluessel niemals auf GitHub hochladen.
2. AMP-Hauptverwaltung → Configuration → Instance Deployment → Instance Management → Configuration Repositories: `Philipp284868/AMP-Caddy-HTTPS:main` beibehalten und **Fetch Latest** ausfuehren. Browser aktualisieren.
3. In **Instances** gezielt die **Update-Funktion der Caddy-Instanzkachel** fuer deren Generic-Modul/Vorlage ausfuehren. Das ist nicht dasselbe wie das Anwendungs-Update im Inneren der Instanz. **Kein Update All.** Danach die Instanz verwalten und pruefen, ob die neue Kategorie **HTTPS-Zugang** sichtbar ist. Fehlt sie, Templateaktualisierung/Deployment Log pruefen, nicht eine zweite Caddy-Instanz mit denselben Ports erstellen.
4. In der Caddy-Instanz **Status → Update** ausfuehren. Das laedt die festgelegten Betriebsdateien und Caddy, prueft SHA-256 und installiert das Programm. Die alte manuelle `Caddyfile` bleibt unveraendert. Eigene Einstellungen und Zertifikate werden nicht geloescht.
5. Unter **Configuration → HTTPS-Zugang** die obigen Werte eintragen, speichern und **Start**. Aenderungen danach mit **Stop → Start** anwenden. Kein manuelles Hochladen einer neuen `Caddyfile` mehr.

Die genaue Darstellung der Kachelaktionen haengt von AMP ab. Hintergrund: [CubeCoders: Generic-Konfigurationen aktualisieren](https://discourse.cubecoders.com/t/how-to-update-amp-to-the-latest-version/2297). Ein blosser Fetch aktualisiert die Repositoryliste, aber nicht nachweislich jede laufende Instanzkonfiguration.

## Neue Instanz

Vorlagenrepository wie oben einbinden. **Philipp / Caddy HTTPS** auswaehlen; bei Erstellung zunaechst **Do Nothing**. Instanz verwalten → **Update** → Domain/Spieladresse einstellen → **Start**. Caddy wird nicht als zweiter Systemdienst installiert und benoetigt keine root-Rechte fuer die hohen internen Ports. Benoetigt werden Bash, GNU coreutils, tar und flock (util-linux), in der vorgesehenen Debian-Umgebung uebliche Systemwerkzeuge.

## Was automatisch passiert

- Offizielles Caddy v2.11.4 wird geladen und das Archiv gegen eine festgelegte SHA-256 geprueft, bevor das Programm ersetzt wird.
- Domain, Spielziel, Ports und optionale Werte werden vor Verwendung streng geprueft. Kein `eval` und keine als Shellcode ausgefuehrten Einstellungen.
- `private/Caddyfile.generated` wird erzeugt und mit `caddy validate` geprueft. Die letzte gueltige Konfiguration bleibt bei fehlerhaften Eingaben erhalten; der Start endet mit einer konkreten Meldung.
- HTTP wird mit Status 308 auf die richtige HTTPS-Domain **ohne interne Portnummer** umgeleitet. API, Geodaten, Cookies und WebSocket-Verbindungen gehen ueber denselben Proxy.
- Caddy laeuft im Vordergrund; AMP kann ihn per SIGTERM geordnet stoppen. Kein Schlafmodus, kein oeffentlicher Adminport 2019, kein UDP-/HTTP3-Port in dieser IPv4-Vorlage.
- Fehlt das Spielziel, zeigt HTTPS im Proxybetrieb eine eindeutige **503-Meldung**, keine angeblich funktionierende Spielseite. Testbetrieb zeigt nur eine statische Testseite.

## Netzwerk und Spiel bleiben getrennte Voraussetzungen

Fuer den vorhandenen IPv4-Aufbau: FRITZ!Box **extern 80 → Server 18080**, **extern 443 → Server 18443**, jeweils TCP. Oeffentliche Adresse: **https://gaminglive.mooo.com**. DNS muss auf den erreichbaren Anschluss zeigen. Einen unpassenden AAAA-Eintrag nicht stehen lassen, wenn IPv6 fuer diese Seite nicht bereitgestellt wird. Routerverwaltung, AMP-Port 8080 und Spielport 7777 nicht als Ersatz fuer HTTPS veroeffentlichen. Keine Exposed-Host-Freigabe.

Caddy und Spiel in getrennten Containern: `127.0.0.1` zeigt in den jeweiligen Container, nicht automatisch zur anderen Instanz. Als Ziel den wirklich aus Caddy erreichbaren Host-/Containernamen mit Spielport verwenden; gegebenenfalls feste Host-Portveroeffentlichung. Der Spielserver muss dort lauschen. Rechte, Netzwerk und persistente Mounts koennen nicht aus GitHub automatisch eingerichtet oder bestaetigt werden.

In der **vorhandenen** Spielkonfiguration nur die Netzwerkwerte anpassen, **DATA_DIR/GEODATA_DIR erhalten**. [Netzwerkbeispiel](examples/leitstellen-network.env.example). Die geloeschte Spielkonfiguration muss unabhaengig von Caddy korrekt wiederhergestellt werden; diese Vorlage legt keine neue Spielwelt an.

## Zertifikate und Sicherungen

Beim Upgrade wird ein bisheriger nativer Caddy-Speicher beibehalten (bei Philipps beobachtetem Aufbau `/home/amp/.local/share/caddy`). Sonst entsteht fuer eine frische Instanz `serverfiles/private/caddy-data`. Die gewaehlte absolute Zuordnung steht in `private/storage.path` und wird bei spaeteren Starts wiederverwendet.

Ein fehlender alter Speicher oder ein unbekanntes `storage`/`import` in der alten `Caddyfile` wird **nicht** durch stilles Neuerstellen von Zertifikaten kaschiert. Dann bisherigen Speicher unter HTTPS - Erweitert angeben bzw. den Mount wiederherstellen. Die Vorlage kopiert oder loescht keine privaten Schluessel. Ein konfigurierter externer Speicher muss bereits existieren und les-/schreibbar sein.

AMP-Backups muessen die Instanzkonfiguration und `private/` enthalten. Liegt der wiederverwendete Speicher **ausserhalb** des AMP-Dateibereichs, muss er **zusaetzlich** gesichert bzw. dauerhaft gemountet werden; er ist nicht automatisch im Instanzbackup. Nicht alle `/home/amp`-Zertifikate fuer ein einzelnes Spiel loeschen. Details: [Betrieb und Fehlerhilfe](docs/BETRIEB.md).

## Pruefung und Grenzen

[GitHub Actions](https://github.com/Philipp284868/AMP-Caddy-HTTPS/actions) prueft Bash/Manifeste, ungueltige Eingaben, Bestandsschutz und eine echte Caddy-TLS-/Proxy-/WebSocket-Verbindung mit isolierter Test-CA. Keine oeffentliche ACME-Ausstellung oder Installation der Test-CA im System. Tests: `python3 tests/test_system.py`; fuer echte Integration `CADDY_TEST_BINARY=/absoluter/pfad/caddy python3 tests/test_system.py`. Ohne Binary wird dieser eine Test sichtbar uebersprungen, nicht als bestanden ausgegeben.

Der private AMP-Import, automatische Portzuweisung, die reale Spielanmeldung, FRITZ!Box und oeffentliche Zertifikatserneuerung muessen auf dem tatsaechlichen Server abschliessend geprueft werden. Ein gruener Caddy-Prozessstatus allein bestaetigt sie nicht. Der urspruengliche Generator ist nur Ausgangspunkt; [technische Details und Quellen](docs/TECHNIK.md). Kein Sicherheitsversprechen fuer die dahinterliegende Spielanwendung.
