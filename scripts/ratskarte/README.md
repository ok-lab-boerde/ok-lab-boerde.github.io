# Ratskarte Wanzleben-Börde (Prototyp)

Zeigt öffentliche Tagesordnungspunkte von Stadtrat, Ausschüssen und Ortschaftsräten der Stadt
Wanzleben-Börde auf einer Karte, nach dem Vorbild der [Ratskarte Dresden](https://codefor.de/projekte/dd-ratskarte/).

```bash
python scripts/orte/fetch.py        # Orts- und Grenzdaten (falls noch nicht im Cache)
python scripts/ratskarte/fetch.py   # Sitzungen seit 2024 + Straßennamen aus OSM
python scripts/ratskarte/build.py   # schreibt ratskarte/index.html
```

## Quellen
- Ratsinformationssystem (SessionNet) der Stadt: <https://ratsinfo.kitu-genossenschaft.de/wzl_bi/>
  Gelesen werden nur der Sitzungskalender (`si0046.asp`) und die Tagesordnungen (`si0057.asp`), keine PDFs.
  Mindestens 3 s Pause zwischen Abrufen. Sitzungen älter als 60 Tage werden nur einmal geladen (Cache).
- Straßennamen: OpenStreetMap über Overpass (ODbL). Orte und Ortsteile aus `scripts/orte/.cache/`.

## Regeln
- Nur der **öffentliche Teil** der Tagesordnung; alles nach „Nicht öffentlicher Teil“ wird verworfen.
- Formalien (Eröffnung, Niederschrift, Berichte, Fragestunde …) und **Personalangelegenheiten**
  (Wahlen, Ehrungen, Berufungen, Titel mit „Herr“/„Frau“ …) werden ausgelassen, siehe `FORMAL` und `PERSONAL` in `build.py`.
- Straße: OSM-Straßenname steht wörtlich im Titel. Gibt es den Namen in mehreren Ortsteilen, entscheidet der im
  Titel genannte Ort oder der tagende Ortschaftsrat. Sonst wird nicht geraten.
- Ort: Ortsname im Titel, sonst der Ort des Ortschaftsrats. Der Gemeindename „Wanzleben-Börde“ zählt nicht als Ort.

## Weitere Gemeinden
Der Landkreis (ALLRIS, `kreistag.landkreis-boerde.de`) sperrt automatische Abrufe per `robots.txt`;
die OParl-Schnittstelle ist installiert, liefert aber einen Serverfehler. Für eine Erweiterung wäre
eine freigeschaltete OParl-Schnittstelle der saubere Weg.
