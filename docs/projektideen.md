# Projektideen für die Börde

Eine Sammlung zum Start. Bei jeder Idee steht ein Hinweis, wie gut die Daten verfügbar sind.
**Bevor ein Projekt startet, müssen Datenquelle und Lizenz geprüft werden.** Die genannten Quellen sind Ausgangspunkte. Ob sie Daten für die Börde enthalten, ist nicht überprüft.

Status-Legende: 💡 Idee · 🔨 In Arbeit · ✅ Läuft · 📦 Abgeschlossen

---

## 1. Energiewende-Monitor Börde ✅
**Online:** https://ok-lab-boerde.github.io/energiewende/ (Code in `energiewende/` und `scripts/fetch_mastr.py`, monatliche Aktualisierung per GitHub Action)

Wind-, Solar- und Biogasanlagen im Landkreis in Zeitreihen: Was ist installiert, wie schnell geht der Ausbau voran, welche Gemeinde erzeugt wie viel? Nächster Schritt könnte eine Karte sein.
- **Daten:** Marktstammdatenregister der Bundesnetzagentur. Die Daten sind öffentlich und als Gesamtexport verfügbar.
- **Einstieg:** gut geeignet. Der Datenzugang ist gut und das Thema ist in der Börde sehr präsent.

## Unfallatlas Börde ✅
**Online:** https://ok-lab-boerde.github.io/unfallatlas/ (Code in `unfallatlas/` und `scripts/unfallatlas/build.py`, jährliche Aktualisierung im August per GitHub Action)

Verkehrsunfälle mit Personenschaden im Landkreis auf einer Karte (Punkte oder Heatmap) mit Filtern nach Jahr, Schwere, Beteiligten und Licht und einem Schalter für Fahrradunfälle. Dazu Diagramme nach Jahr, Wochentag und Uhrzeit sowie eine Gemeindetabelle.
- **Daten:** [Unfallatlas der Statistischen Ämter des Bundes und der Länder](https://unfallatlas.statistikportal.de/), Sachsen-Anhalt ab 2017. Kreisgrenze und Gemeindenamen aus VG250 (© GeoBasis-DE / BKG).
- **Lizenz:** Datenlizenz Deutschland – Namensnennung – Version 2.0. Kartenhintergrund © OpenStreetMap-Mitwirkende (ODbL).

## Betriebe in der Börde und Orte in der Börde ✅
**Online:** https://ok-lab-boerde.github.io/betriebe/ und https://ok-lab-boerde.github.io/orte/ (Code in `scripts/orte/`, wöchentliche Aktualisierung per GitHub Action)

Durchsuchbare Karte von rund 2.000 Betrieben mit eigener Seite je Betrieb, dazu Steckbriefe für alle 34 Gemeinden und ihre Ortsteile mit Betrieben, Vereinen, Kitas und Schulen, Bus und Bahn und Ausflugszielen.
- **Daten:** OpenStreetMap über die Overpass API. Gemeindegrenzen aus VG250 (© GeoBasis-DE / BKG).
- **Lizenz:** OpenStreetMap-Daten unter ODbL (© OpenStreetMap-Mitwirkende), VG250 unter Datenlizenz Deutschland – Namensnennung – Version 2.0.
- **Karten-Check** (https://ok-lab-boerde.github.io/betriebe/karten-check/): Je Betrieb sieht man, welche Angaben in OSM fehlen, mit Link zum Bearbeiten.
- **Leben in der Börde** (https://ok-lab-boerde.github.io/leben/): alle Städte und Dörfer im Vergleich, mit der Entfernung zur nächsten Kita, Schule, Arztpraxis, Apotheke, zum Supermarkt, Bahnhof und nach Magdeburg und Wolfsburg (Luftlinie). Glasfaser und echte Pendelzeiten fehlen noch.
- **Nächste Stufe:** einbettbares Widget für Gemeinde- und Firmenwebsites.

## Regional einkaufen in der Börde ✅
**Online:** https://ok-lab-boerde.github.io/regional/ (Code in `scripts/orte/regional.py`, wöchentlich mit Betrieben und Orten aktualisiert)

Hofläden, Automaten, Wochenmärkte, Saisonstände, Obst und Gemüse, Fleischereien, Bäckereien und Imker auf einer Karte. Bei jedem Eintrag gibt es Knöpfe zum Anrufen, Schreiben, für WhatsApp und die Route. Dazu kommen ein Saisonkalender und eine Anleitung, wie Betriebe sich selbst in OpenStreetMap eintragen.
- **Daten:** nur OpenStreetMap (ODbL). Ein eigenes Anmeldeformular gibt es bewusst nicht, aus Datenschutzgründen.
- **Hinweis:** In OSM stehen nur rund 10 Hofläden. Der Wert der Karte hängt daran, dass Betriebe sich eintragen. Dafür Betriebe ansprechen, etwa über Bauernverband, Gemeinden oder Lokalpresse, und auf die Anleitung verweisen.

## 2. Bus & Bahn in der Fläche 💡
Erreichbarkeitskarte: Wie lange braucht man von jedem Ort mit dem ÖPNV nach Haldensleben, Oschersleben oder Magdeburg, zum Beispiel werktags um 7 Uhr und am Sonntag? Lücken im ländlichen Raum werden so sichtbar.
- **Daten:** Fahrplandaten im GTFS-Format, z. B. der bundesweite Datensatz von DELFI. Zusätzlich OpenStreetMap.
- **Werkzeuge:** OpenTripPlanner oder r5py.

## 3. Ratsinfo durchsuchbar 💡
Beschlüsse und Vorlagen aus Kreistag und Stadträten an einem Ort und mit Volltextsuche. Optional mit Benachrichtigung zu Stichworten, z. B. „Schule“ oder den Namen bestimmter Straßen.
- **Daten:** Ratsinformationssysteme der Kommunen. Zu prüfen ist, ob sie eine OParl-Schnittstelle anbieten. Andernfalls müssen die Seiten ausgelesen werden.

## 4. Börde gießt 💡
Angelehnt an „Magdeburg gießt“: Bürger:innen übernehmen Patenschaften für Stadtbäume und tragen ein, wann sie gegossen haben.
- **Daten:** Baumkataster der Städte. Ob es veröffentlicht ist, muss bei der Verwaltung angefragt werden. Wetterdaten kommen vom DWD (Open Data).
- **Vorteil:** Der Code von „Gieß den Kiez“ (Berlin) und „Magdeburg gießt“ ist Open Source und lässt sich wiederverwenden.

## 6. Pegel & Hochwasser an Ohre, Aller und Bode 💡
Ein einfaches Dashboard mit den aktuellen Wasserständen und deren Verlauf an den Flüssen der Region.
- **Daten:** Landesbetrieb für Hochwasserschutz und Wasserwirtschaft (LHW) Sachsen-Anhalt. Für den Mittellandkanal und die Elbe gibt es PEGELONLINE der WSV mit offener API.

## 7. Netzabdeckung prüfen 💡
Wo gibt es Funklöcher und wo fehlt Glasfaser? Die offiziellen Karten werden mit Messungen aus der Bevölkerung verglichen.
- **Daten:** Breitbandatlas und Mobilfunk-Monitoring der Bundesnetzagentur sowie die Funkloch-App-Daten der BNetzA.

## 8. Wahlatlas Börde 💡
Ergebnisse der Kommunal-, Landtags- und Bundestagswahlen auf Gemeindeebene, als Karte und im Zeitvergleich. Später lässt sich daraus ein „Börde-O-Mat“ zur nächsten Kommunalwahl entwickeln.
- **Daten:** Statistisches Landesamt Sachsen-Anhalt (Wahlergebnisse).

---

## Wie geht's weiter?
1. 2–3 Ideen auswählen, für die es Mitstreiter:innen gibt.
2. Für jede gewählte Idee ein Issue mit Datenquelle, Ansprechpartner:in und nächstem Schritt anlegen.
3. Bei Daten, die nicht veröffentlicht sind, freundlich bei der Verwaltung anfragen oder über [FragDenStaat](https://fragdenstaat.de/) eine Anfrage stellen.
