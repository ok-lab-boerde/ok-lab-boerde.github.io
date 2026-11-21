# Orte in der Börde

Steckbriefe für alle Gemeinden und Ortsteile im Landkreis Börde: Betriebe, Vereine und Sport, Kitas und Schulen, Gesundheit, Bus und Bahn, Ausflugsziele, dazu Zahlen aus dem Energiewende-Monitor und dem Unfallatlas.
Live: https://ok-lab-boerde.github.io/orte/

Alle Dateien in diesem Ordner außer dieser README werden von `scripts/orte/build.py` erzeugt und bei jedem Lauf gelöscht und neu geschrieben.

## Datenquelle

- OpenStreetMap über die Overpass API, © OpenStreetMap-Mitwirkende, Lizenz ODbL
  - Landkreis: Relation 62359 (`de:amtlicher_gemeindeschluessel=15083`)
  - Ortsteile: Grenzen mit `admin_level` 9 und 10
- Gemeindegrenzen: VG250, © GeoBasis-DE / BKG, Datenlizenz Deutschland – Namensnennung – 2.0

## Zuordnung

Jeder Betrieb und jedes Objekt wird über seine Lage der Gemeinde (VG250) und dem kleinsten passenden Ortsteil (OSM) zugeordnet. Ortsteile ohne Grenze in OSM erscheinen nicht als eigene Seite.

## Lokales Starten

Siehe `betriebe/README.md`. Danach http://localhost:8000/orte/ öffnen.
