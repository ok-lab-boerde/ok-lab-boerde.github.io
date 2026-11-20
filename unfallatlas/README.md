# Unfallatlas Börde

Karte der Verkehrsunfälle mit Personenschaden im Landkreis Börde.
Live: https://ok-lab-boerde.github.io/unfallatlas/

## Datenquellen

| Was | Quelle | Lizenz |
| --- | --- | --- |
| Unfälle | [Unfallatlas der Statistischen Ämter des Bundes und der Länder](https://unfallatlas.statistikportal.de/), Open Data unter [opengeodata.nrw.de/…/unfallatlas](https://www.opengeodata.nrw.de/produkte/transport_verkehr/unfallatlas/) | Datenlizenz Deutschland – Namensnennung – 2.0 |
| Kreisgrenze, Gemeindenamen | Verwaltungsgebiete 1:250 000 (VG250), © GeoBasis-DE / BKG, über den [WFS des BKG](https://sgx.geodatenzentrum.de/wfs_vg250) | Datenlizenz Deutschland – Namensnennung – 2.0 |
| Kartenhintergrund | © OpenStreetMap-Mitwirkende, Kacheln von tile.openstreetmap.org | ODbL |

Sachsen-Anhalt ist im Unfallatlas **ab 2017** enthalten. Enthalten sind nur polizeilich erfasste Unfälle mit Personenschaden.

## Aufbereitung

`scripts/unfallatlas/build.py` (nur Python-Standardbibliothek):

1. liest die Dateiliste des Open-Data-Verzeichnisses und lädt alle `Unfallorte<Jahr>_EPSG25832_CSV.zip`,
2. überspringt Jahre ohne Sachsen-Anhalt,
3. filtert auf `ULAND = 15`, `UREGBEZ = 0`, `UKREIS = 83`,
4. vereinheitlicht die Spaltennamen, die sich zwischen den Jahren unterscheiden:
   - `ULICHTVERH` / `LICHT` (2017)
   - `IstSonstige` / `IstSonstig`
   - `IstGkfz` fehlt 2017. Lkw sind dort in „Sonstige“ enthalten, deshalb ist das Bit `gkfz_unbekannt` gesetzt,
5. holt Kreisgrenze und Gemeindenamen aus dem VG250-WFS,
6. schreibt:
   - `data/unfaelle.json`: kompakt. `felder` beschreibt die Spalten, `beteiligt` ist eine Bitmaske (siehe `bits`), Koordinaten haben 5 Nachkommastellen
   - `data/stand.json`: Datenstand der Quelle, Jahre, Anzahl je Jahr, Quellenangaben
   - `data/kreisgrenze.geojson`

Rohdaten werden nicht gespeichert. Die GitHub Action `.github/workflows/unfallatlas-daten.yml` läuft jedes Jahr am 15. August und lässt sich manuell auslösen. Sie committet nur bei Änderungen.

## Lokal starten

```bash
python scripts/unfallatlas/build.py
python -m http.server 8000
```

Dann http://localhost:8000/unfallatlas/ öffnen.

## Bibliotheken (lokal in `vendor/`)

- [Leaflet](https://leafletjs.com/) 1.9.4 (BSD-2-Clause)
- [Leaflet.markercluster](https://github.com/Leaflet/Leaflet.markercluster) 1.5.3 (MIT)
- [Leaflet.heat](https://github.com/Leaflet/Leaflet.heat) 0.2.0 (BSD-2-Clause)
