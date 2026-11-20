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
