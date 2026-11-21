# Betriebe in der Börde

Durchsuchbare Karte aller benannten Betriebe im Landkreis Börde, mit eigener Seite je Betrieb.
Live: https://ok-lab-boerde.github.io/betriebe/

## Inhalt

| Pfad | Inhalt |
| --- | --- |
| `index.html`, `app.js` | Kartenseite mit Suche, Filter nach Ort und Branche, „jetzt geöffnet“ (von Hand gepflegt) |
| `data/betriebe.json` | Kompakte Daten für die Karte (erzeugt) |
| `data/stand.json` | Datenstand, Prüfsumme, Anzahl Seiten (erzeugt) |
| `<gemeinde>/` | Betriebe je Gemeinde, `<gemeinde>/<betrieb>/` je Betrieb, `<gemeinde>/branche/<branche>/` je Branche (erzeugt) |
| `ueber-die-daten/` | Herkunft der Daten und Anleitung zum Ändern (erzeugt) |

Alles außer `index.html`, `app.js` und dieser README wird von `scripts/orte/build.py` erzeugt und bei jedem Lauf neu geschrieben. Bitte dort nichts von Hand ändern.

## Datenquelle

- OpenStreetMap über die Overpass API, © OpenStreetMap-Mitwirkende, Lizenz ODbL
- Gemeindegrenzen: VG250, © GeoBasis-DE / BKG, Datenlizenz Deutschland – Namensnennung – 2.0

Welche OSM-Tags zu welcher Branche gehören, steht in `scripts/orte/branchen.json`. Objekte, die auf Wunsch nicht erscheinen sollen, stehen in `scripts/orte/ausschluss.json`.

## Aufbereitung und lokales Starten

```bash
python scripts/orte/fetch.py
python scripts/orte/build.py
python -m http.server 8000
```

Dann http://localhost:8000/betriebe/ öffnen. `fetch.py` legt die Rohdaten in `scripts/orte/.cache/` ab (nicht im Repo). `build.py` arbeitet nur mit diesem Cache und kann beliebig oft laufen.

Die GitHub Action `.github/workflows/orte-daten.yml` läuft jeden Montag und lässt sich manuell auslösen. Die Ausgabe ist deterministisch, deshalb wird nur bei echten Änderungen in OpenStreetMap committet.

## Suchmaschinen

Betriebsseiten mit mindestens zwei von Öffnungszeiten, Telefon, Website und E-Mail stehen auf `index` und in der `sitemap.xml`. Alle anderen stehen auf `noindex, follow`. Jede Seite enthält strukturierte Daten (schema.org `LocalBusiness`).
