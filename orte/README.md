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

## Alltag und „Leben in der Börde“

Jeder Steckbrief hat einen Abschnitt „Alltag“: die nächste Kita, Grundschule, weiterführende Schule, Arztpraxis, Apotheke, der nächste Supermarkt und Bahnhof sowie die Entfernung zu den Hauptbahnhöfen Magdeburg und Wolfsburg. Gemessen wird in Luftlinie vom Ortspunkt in OSM (`place=city|town|village`), nur zu Einrichtungen im Landkreis.

`/leben/` (erzeugt, Skript `/assets/leben.js`) zeigt dieselben Werte für alle Städte und Dörfer in einer filterbaren Tabelle. Weiler (`place=hamlet`) sind dort nicht aufgeführt.

Schulen werden über `isced:level` und den Namen eingeordnet: Grundschule (ISCED 1 oder „Grundschule“), weiterführend (ISCED 2/3 oder Sekundarschule, Gymnasium, Gemeinschafts- und Gesamtschule). Förderschulen und Akademien zählen nicht mit.

Glasfaser und echte Pendelzeiten fehlen noch, weil es dafür keine offenen Daten je Ort gibt, die wir verwenden dürfen.
