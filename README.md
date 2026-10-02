# where2watch

Streamingangebote über Ländergrenzen hinweg finden — direkt im Terminal. Eine Flutter-Web-Vorschau mit Watchlist ist ebenfalls enthalten.

## Terminal-Anwendung

Nur Python 3.10+ nötig. Kein Flutter-Build, Browser oder laufender Webserver erforderlich.

```bash
# Ohne Zugangsdaten ausprobieren (erfundene Angebote, acht Demo-Titel)
./where2watch --demo Interstellar
./where2watch --demo Dune --country US,CA --provider Netflix --abo

# Echte Filmdaten und weltweite Streamingangebote
export TMDB_READ_ACCESS_TOKEN='your-read-access-token'
./where2watch Interstellar
./where2watch "House of the Dragon"

# Ohne Namen: interaktive Suchfrage
./where2watch

# Für Skripte
./where2watch Interstellar --json
./where2watch Dune --year 2021 --pick 1
./where2watch --help
```

Die Ausgabe enthält Titel, Typ, Jahr, Beschreibung, Bewertung und alle gemeldeten Länder mit Anbietern und Angebotsarten. Im Live-Modus kommen – soweit vorhanden – Originaltitel, Genres, Laufzeit, Veröffentlichung, Regie/Schöpfer, Besetzung, Serienumfang, Status und Originalsprachen hinzu. Originalsprachen sind keine Aussage über verfügbare Streaming-Tonspuren. Die Links führen zu TMDB-Angebotsübersichten, nicht direkt zum Stream.

Bei mehreren Treffern fragt die CLI nach einer Nummer. Bei `--json` oder ohne interaktives Terminal gibt sie die Kandidaten auf stderr aus; `--pick N` wählt einen davon. Die Suche verwendet die erste TMDB-Ergebnisseite. `--country DE,US` filtert Länder; `--provider NAME` filtert Anbieternamen ohne Beachtung der Groß-/Kleinschreibung und ist mehrfach möglich. Ohne Filter werden alle gemeldeten Länder angezeigt.

Ohne Token zeigt die CLI eine Fehlermeldung mit Einrichtungshinweis; sie wechselt **nicht automatisch auf erfundene Daten**. Nur `--demo` verwendet Beispielangebote. Exit-Codes: `0` Erfolg, `1` keine Treffer, `2` Eingabe-/Datenquellenfehler, `130` Abbruch. Ein Titel ohne gemeldete Angebote bleibt ein erfolgreiches Suchergebnis.

## Flutter-Web-Vorschau

Voraussetzung: Flutter Stable und Python 3.10+.

```bash
flutter pub get
flutter build web --release
python3 server/server.py
```

Öffnen: http://localhost:8096. Der Python-Server liefert Web-App und API unter derselben Origin aus. Für die Vorschau auf einem mobilen Gerät kann ein Reverse Proxy wie Tailscale Serve verwendet werden.

```bash
tailscale serve --bg --https=9448 http://127.0.0.1:8096
```

## Demo und echte Daten

Ohne Zugangsdaten startet der Server im **Demo-Modus**. Die acht Titel verwenden echte Poster, aber **erfundene Anbieter- und Länderangebote**. Sie sind ausschließlich zur Demonstration der Bedienung gedacht. Keine Verfügbarkeits- oder VPN-Zugriffsgarantie.

Mit einem TMDB API Read Access Token wird automatisch der Live-Modus verwendet:

```bash
export TMDB_READ_ACCESS_TOKEN='your-read-access-token'
python3 server/server.py
```

Token ausschließlich im Server-Prozess setzen, niemals im Flutter-Build oder Repository speichern. Der Adapter lädt Trends bzw. Suchergebnisse und Streamingangebote nach Land. Antworten werden sechs Stunden im Prozess zwischengespeichert; Anbieterfehler werden als Fehler angezeigt, nicht als fehlende Verfügbarkeit. Die Detailseite kann über den von TMDB gelieferten Link zu deren Angebotsübersicht führen. TMDB liefert keine direkten Stream-Links.

Live-Suche liefert bis zu 20 Titel pro Anfrage. Länder- und Anbieterfilter wirken auf diese Ergebnisse, nicht auf den vollständigen weltweiten Katalog. Es gibt noch keine Staffel-, Sprach-, Preis-, Benachrichtigungs- oder VPN-Verifikation. Watchlist und Dienstauswahl liegen lokal im Browser; keine Konten oder Synchronisierung. Gespeicherte Titel bleiben in der Watchlist erhalten; Live-Angebote werden beim Öffnen erneut abgefragt.

## Prüfen

```bash
flutter analyze
flutter test
python3 -m unittest discover -s server -p 'test_*.py'
python3 -m unittest discover -s tests -p 'test_*.py'
```

## Datenquellen

Poster und Live-Filmdaten: [TMDB](https://www.themoviedb.org/).
This product uses the TMDB API but is not endorsed or certified by TMDB.

Live-Streamingdaten: JustWatch via [TMDB Watch Providers](https://developer.themoviedb.org/reference/movie-watch-providers). Die Oberfläche zeigt Attribution im Bereich „Über & Datenquellen“. Nutzung und insbesondere kommerzielle Veröffentlichung müssen die Bedingungen der Datenanbieter erfüllen. Die Open-Source-Lizenz des Codes gewährt keine Rechte an Postern oder externen Katalogdaten.

## Dauerhafte Vorschau auf diesem Server

Die veröffentlichte Vorschau liegt getrennt vom Worktree unter `/srv/projects/where2watch-preview`. Der systemd-Dienst aus `deploy/where2watch-preview.service` startet den Python-Server auf Port 8096. Tailscale Serve veröffentlicht ihn auf HTTPS-Port 9448 ausschließlich im Tailnet. Für Live-Daten kann `TMDB_READ_ACCESS_TOKEN` in `/etc/where2watch-preview.env` gesetzt und der Dienst neu gestartet werden. Die Datei darf nicht ins Repository gelangen.
