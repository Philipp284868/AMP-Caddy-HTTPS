# Betrieb und Fehlerhilfe

## Start/Stop/Update

Nach erstmaligem Update werden nur Domain und internes Ziel benoetigt. Bei geaenderten Einstellungen stoppen/starten; kein `caddy reload`, da die Verwaltungs-API bewusst deaktiviert bleibt. Update nur bei gestoppter Caddy-Anwendung. Die Runtime-Locks verhindern zwei Starts derselben Installation und ein gleichzeitiges Ersetzen ihres laufenden Programms.

Der Start erzeugt erst einen temporaeren Entwurf, validiert ihn und ersetzt dann die verwaltete Konfiguration atomar. Eine vorherige gueltige Fassung bleibt als `private/Caddyfile.generated.previous` erhalten. Eine eigene Datei `Caddyfile` wird nicht veraendert oder weiterhin parallel geladen. Die aktuelle Konfiguration entsteht ausschliesslich aus AMP-Einstellungen.

Die Vorlage ist fuer eine Domain, einen internen HTTP-Upstream, IPv4 und die externe Weiterleitung 80/443 ausgelegt. Wildcards, mehrere Hosts, Pfadpraefixe und ein HTTPS-Backend sind bewusst nicht als scheinbar funktionierende Regler angeboten. DNS-Namen fuer Backends sind erlaubt, deren IPv4-Erreichbarkeit muss passen. TLS zum oeffentlichen Browser wird nicht abgeschwaecht. In getrennten oder nicht vertrauenswuerdigen Netzwerken waere eine gesonderte abgesicherte Backendverbindung erforderlich.

## Drei getrennte Pruefungen

1. AMP `Running` und `serving initial configuration`: Prozess/geladene Konfiguration.
2. Domain im externen Browser ohne Zertifikatswarnung: oeffentliches HTTPS. Mit aktivierter Test-Betriebsart nur statische Testmeldung.
3. Proxy-Betriebsart: `/api/health`, Spielanmeldung und echte Live-Verbindung pruefen. Eine 503-Meldung kann einen intakten Caddy mit gestopptem Spiel bedeuten.

Keine Zertifikatswarnungen umgehen. Fuer den Aussentest PC ueber Hotspot oder Mobilfunk verwenden. Ein Funktionieren nur im Heimnetz beweist keine allgemeine Erreichbarkeit.

## Typische Fehler

| Meldung/Symptom | Handlung |
| --- | --- |
| Domain fehlt/ungueltig | Nur den DNS-Namen ohne Protokoll, Port oder Pfad eingeben. |
| Runtime oder Caddy fehlt | Vorlage der Instanz aktualisieren, danach gezielt deren Anwendung-Update. |
| SHA-256 stimmt nicht | Download fehlgeschlagen/manipuliert oder Version unpassend; nicht weiter entpacken. Alte Binary bleibt erhalten. |
| `address already in use` | Portzuweisung und andere Webserver pruefen. Nicht willkuerlich einen fremden Dienst stoppen. |
| `bind: permission denied` | Keine niedrigen Ports im AMP-Prozess verwenden; passende hohe Portzuweisung kontrollieren. |
| 503: Spiel nicht erreichbar | NodejsAppRunner, Spielkonfiguration, Datenpfade und Upstream-Port pruefen; 8080 ist die AMP-Verwaltung, nicht das Spiel. |
| Anmeldung `Origin nicht erlaubt` | Oeffentliche HTTPS-Adresse in der effektiven Spielkonfiguration und eventuelle AMP-Umgebungswerte abgleichen. |
| Zertifikatspruefung fehlgeschlagen | DNS A/AAAA, reale IPv4-Erreichbarkeit, externe Standardports und Caddy-Konsole pruefen. Nicht staendig neu installieren. |
| Alte Zertifikate fehlen | Den bisherigen Speicher/Mount wiederherstellen. `private/storage.path` nicht einfach loeschen. |
| Keine neuen AMP-Einstellungsfelder | Fetch Latest aktualisiert nur die Quelle; auch Generic-Konfiguration ueber die gezielte Instanzkachel aktualisieren. |

## Sicherungen und bewusstes Speicherumziehen

Vor Updates private Instanzeinstellungen, alte manuelle Caddyfile und den in der Konsole/`private/storage.path` genannten Zertifikatsspeicher sichern. Zertifikate und ACME-Kontoschluessel nicht oeffentlich teilen. Ein Upgrade der Vorlage sichert nicht automatisch einen externen `/home/amp`-Speicher.

Normalerweise ist kein Speicherumzug erforderlich. Bei notwendigem Umzug: Caddy stoppen, konsistente private Sicherung anlegen, denselben Datenbestand samt Rechten an den Zielort uebertragen, den absolut aufgeloesten Pfad in `private/storage.path` und gegebenenfalls der AMP-Speicheroption gemeinsam abgleichen. Nur mit lokalem Serverzugriff/Berechtigungen; nie einen leeren neuen Ordner als Ersatz deklarieren. Original bis nach erfolgreicher Pruefung erhalten.

Bei einer neuen Containerinstanz muss der Zertifikatsspeicher im richtigen Namespace persistent eingebunden sein. Eine neue AMP-Instanz nicht parallel unter derselben Domain mit leeren Zertifikatsdaten und denselben Ports starten.

## Rueckkehr zur alten manuellen Caddyfile

Bei einem Templateproblem neue Runtime stoppen, vorher gesicherte Generic-Konfiguration der selben Instanz wiederherstellen und die unveraenderte alte Caddyfile verwenden. Keine parallele zweite Instanz, keine Zertifikats-/Spielstandloeschung. Eine `.previous`-Binary ist keine automatische Freigabe zu einem ungeprueften Downgrade.
