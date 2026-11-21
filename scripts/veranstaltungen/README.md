# Veranstaltungskalender

```bash
python scripts/veranstaltungen/fetch.py   # Termine laden (.cache/termine.json, Detailseiten 3 Tage im Cache)
python scripts/veranstaltungen/build.py   # veranstaltungen/index.html, termine.json, kalender/*.ics
```

Täglich per GitHub Action (`.github/workflows/veranstaltungen.yml`). Die Ortsliste für die Zuordnung
(`orte.json`) erneuert der wöchentliche Lauf mit `build.py --nur-orte`, weil der tägliche Lauf ohne den
großen OSM-Abruf auskommen soll.

## Quellen (Stufe 1)
| Quelle | Wie | Abstand |
|---|---|---|
| Landkreis Börde, `/erleben/veranstaltungen` | Liste, ICS je Termin, Adresse aus der Detailseite | 2 s |
| Verwaltungsportal: Niedere Börde, VG Obere Aller, VG Elbe-Heide | Liste `/veranstaltungen`, schema.org-Event der Detailseite | 2 s |
| Stadt Wanzleben-Börde, `/de/aktuelles/veranstaltungen.html` | Freitext: Zeile mit Datum, dann Titel, dann Ort | 15 s (Crawl-delay) |
| Ratsinfo Wanzleben-Börde | künftige öffentliche Sitzungen aus dem Sitzungskalender | 3 s |

Nicht dabei, weil `robots.txt` den Export sperrt: Haldensleben, Barleben (bitte um Freigabe).
Andere Gemeinden haben keinen maschinenlesbaren Kalender oder es fehlt noch ein eigener Leser.

## Regeln
- Übernommen werden nur Titel, Datum, Uhrzeit, Ort, Veranstalter und Link, keine Beschreibungen oder Bilder.
- Zuordnung: Ortsname in Adresse, Ort, Titel oder Veranstalter, beschränkt auf das Gebiet der Quelle.
  Einheitsgemeinden ohne Ortsangabe landen bei der Gemeinde. Termine des Landkreises ohne erkennbaren Ort
  bleiben im Gesamtkalender, aber ohne Gemeinde.
- Gleicher Tag und gleicher Titel aus zwei Quellen: nur einmal.
- Fällt eine Quelle aus, bleiben ihre letzten bekannten Termine erhalten.
