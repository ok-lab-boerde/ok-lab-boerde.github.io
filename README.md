# OK Lab Börde

Ein offenes Lab für **Offene Daten, Freie Software und Open Government** im Landkreis Börde
(Haldensleben, Oschersleben, Wanzleben, Wolmirstedt, Barleben, Hohe Börde, Oebisfelde-Weferlingen und Umgebung).

Vorbild sind die OK Labs im Netzwerk [Code for Germany](https://codefor.de/), etwa das
[OK Lab Magdeburg](https://codefor.de/magdeburg/). Das Netzwerk wird von der Open Knowledge Foundation Deutschland e. V. getragen.

## Inhalt dieses Repositorys

| Pfad | Inhalt |
| --- | --- |
| `index.html`, `css/`, `assets/` | Statische Website des Labs |
| `impressum.html`, `datenschutz.html` | Pflichtseiten (Platzhalter, **vor Veröffentlichung ausfüllen**) |
| `docs/projektideen.md` | Projektideen für die Börde mit möglichen Datenquellen |
| `energiewende/` | Energiewende-Monitor (Seite + `data.json`) |
| `scripts/fetch_mastr.py` | Lädt die Daten aus dem Marktstammdatenregister (`python scripts/fetch_mastr.py`) |
| `unfallatlas/` | Unfallatlas Börde (Karte, Daten, eigene [README](unfallatlas/README.md)) |
| `scripts/unfallatlas/build.py` | Bereitet die Unfallatlas-Daten auf |
| `betriebe/`, `orte/` | Betriebe-Karte mit Karten-Check und Ortssteckbriefe (größtenteils erzeugt, siehe [betriebe/README.md](betriebe/README.md)) |
| `wahlen/` | Wahlatlas Börde: alle Landtags-, Bundestags- und Europawahlen seit 1990 je Gemeinde, auf heutige Gemeinden umgerechnet, mit Zeitreise und Seite je Gemeinde (erzeugt von `scripts/wahlen/build.py`, nur nach neuen Wahlen) |
| `duerre/` | Dürremonitor Börde: tägliche Bodenfeuchte des DWD für vier Stationen mit Vergleich zu 1991–2020 und Erklärtexten (erzeugt von `scripts/duerre/build.py`) |
| `feuerwehr/` | Feuerwehren in der Börde: alle Feuerwehrhäuser aus OSM auf einer Karte, je Gemeinde, mit Karten-Check (erzeugt von `scripts/orte/feuerwehr.py`) |
| `regional/` | „Regional einkaufen“: Hofläden, Automaten, Märkte, mit Anleitung zum Eintragen in OSM (erzeugt, siehe [betriebe/README.md](betriebe/README.md)) |
| `ratskarte/` | Ratskarte Wanzleben-Börde (Prototyp): öffentliche Tagesordnungspunkte nach Straße und Ort (erzeugt von `scripts/ratskarte/`, siehe [scripts/ratskarte/README.md](scripts/ratskarte/README.md)) |
| `zeitschichten/` | Zeitschichten der Börde (Prototyp): historische Ereignisse auf der Karte mit Zeitreise. Daten in `zeitschichten/ereignisse.geojson` (von Hand gepflegt, Quelle je Ereignis), Gemeindegrenzen in `gemeinden.geojson` (aus VG250) |
| `veranstaltungen/` | Veranstaltungskalender: Gesamtkalender, `termine.json` für die Ortsseiten, Kalender-Abos `kalender/*.ics` (erzeugt täglich von `scripts/veranstaltungen/`, siehe [scripts/veranstaltungen/README.md](scripts/veranstaltungen/README.md)) |
| `leben/` | „Leben in der Börde“: alle Orte im Vergleich (erzeugt, siehe [orte/README.md](orte/README.md)) |
| `scripts/orte/` | Abruf aus OpenStreetMap (`fetch.py`) und Seitengenerator (`build.py`) |
| `assets/` | Logo, gemeinsame Stile und Bibliotheken für Kartenseiten |
| `sitemap.xml`, `robots.txt` | Für Suchmaschinen (Sitemap wird von `scripts/orte/build.py` erzeugt) |
| `.github/workflows/` | Automatische Aktualisierung: Energiewende monatlich, Unfallatlas jährlich im August, Betriebe und Orte wöchentlich |
| `logo/` | Original-Logo (PNG) |

## Website lokal ansehen

Die Seite kommt ohne Build-Schritt aus. Öffne `index.html` direkt im Browser oder starte einen kleinen Server:

```bash
python -m http.server 8000
```

Dann http://localhost:8000 aufrufen.

## Veröffentlichen (z. B. GitHub Pages)

1. Repository auf GitHub anlegen (z. B. Organisation `ok-lab-boerde`) und pushen.
2. Unter *Settings → Pages* den Branch `main` und den Ordner `/` auswählen.
3. Vorher alle Stellen mit `TODO` ausfüllen: Kontakt, Impressum, Datenschutz.

Die Seite lädt bewusst keine externen Schriften oder Skripte. So entstehen keine Datenübermittlungen an Dritte (DSGVO).

## Mitmachen

Alle sind willkommen: Entwickler:innen, Designer:innen, Daten-Interessierte, Verwaltung, Journalist:innen und neugierige Bürger:innen.
Ideen und Fragen bitte als Issue eintragen.

Wir orientieren uns am [Code of Conduct von Code for Germany](https://codefor.de/grundsaetze/).

## Lizenz

Inhalte: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.de) · Code: MIT (siehe `LICENSE`)
