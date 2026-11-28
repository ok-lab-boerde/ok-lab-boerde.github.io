"""Börde-Quiz: Gemeinden und Orte des Landkreises auf der Karte finden.

Erzeugt `quiz/index.html` und `quiz/data.json` aus den Gemeindegrenzen (VG250) und den Ortsteilen und
Ortspunkten aus OpenStreetMap, die `scripts/orte` zwischenspeichert. Orte ändern sich selten; das Skript muss
nur gelegentlich laufen. Nur Standardbibliothek. Aufruf: python scripts/quiz/build.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "orte"))
import build as orte  # noqa: E402
import geo  # noqa: E402
from seiten import BASIS_URL, OSM_HINWEIS, e, seite  # noqa: E402

OUT = ROOT / "quiz"


def flaeche_km2(polys: list) -> float:
    """Fläche über eine einfache Abstandstreue Projektion (genau genug für eine Rangfolge)."""
    summe = 0.0
    for poly in polys:
        for i, ring in enumerate(poly):
            lat0 = sum(p[1] for p in ring) / len(ring)
            kx, ky = 111.32 * math.cos(math.radians(lat0)), 110.57
            a = 0.0
            for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
                a += (x1 * kx) * (y2 * ky) - (x2 * kx) * (y1 * ky)
            summe += abs(a) / 2 * (1 if i == 0 else -1)
    return summe


def zahl(n: float) -> str:
    return f"{n:,.0f}".replace(",", ".")


def main() -> None:
    gemeinden = orte.gemeinden_laden()
    orte.ortsteile_laden(gemeinden)
    punkte = orte.lade("ortspunkte.json")["elements"]

    daten_g, daten_ot, daten_orte = [], [], []
    for g in gemeinden:
        g["km2"] = flaeche_km2(g["polys"])
        daten_g.append({"name": g["name"], "slug": g["slug"]})
        for o in g["ortsteile"]:
            if o["level"] == "9" and o["name"] != g["name"]:
                daten_ot.append([o["name"], g["name"]])
    for p in punkte:
        t = p.get("tags", {})
        if t.get("place") not in ("town", "village") or not t.get("name"):
            continue
        g, _ = orte.verorten(p["lon"], p["lat"], gemeinden)
        if g:
            daten_orte.append([t["name"], g["name"], round(p["lon"], 5), round(p["lat"], 5)])
    daten_ot.sort()
    daten_orte.sort()

    OUT.mkdir(exist_ok=True)
    daten = {"quelle": "VG250 © GeoBasis-DE / BKG; Ortsteile und Orte © OpenStreetMap-Mitwirkende (ODbL)",
             "gemeinden": daten_g, "ortsteile": daten_ot, "orte": daten_orte}
    (OUT / "data.json").write_text(json.dumps(daten, ensure_ascii=False, separators=(",", ":")), "utf-8", newline="\n")

    groesste = max(gemeinden, key=lambda g: g["km2"])
    kleinste = min(gemeinden, key=lambda g: g["km2"])
    meiste = max(gemeinden, key=lambda g: len(g["ortsteile"]))
    ohne = [g["name"] for g in gemeinden if not [o for o in g["ortsteile"] if o["level"] == "9"]]
    n_ot = len(daten_ot)

    liste = "".join(
        f'<li><a href="/orte/{g["slug"]}/">{e(g["name"])}</a>'
        + (f'<span class="qz-ot">{e(", ".join(o["name"] for o in g["ortsteile"] if o["level"] == "9" and o["name"] != g["name"]))}</span>'
           if any(o["level"] == "9" and o["name"] != g["name"] for o in g["ortsteile"]) else "")
        + "</li>" for g in gemeinden)

    faq = [
        ("Wie viele Gemeinden hat der Landkreis Börde?",
         f"Der Landkreis Börde in Sachsen-Anhalt hat {len(gemeinden)} Gemeinden. Kreisstadt ist Haldensleben."),
        ("Welche ist die größte Gemeinde im Landkreis Börde?",
         f"Nach Fläche ist {groesste['name']} mit rund {zahl(groesste['km2'])} km² die größte Gemeinde, "
         f"{kleinste['name']} mit rund {zahl(kleinste['km2'])} km² die kleinste."),
        ("Welche Gemeinde hat die meisten Ortsteile?",
         f"{meiste['name']} mit {len(meiste['ortsteile'])} Ortsteilen laut OpenStreetMap."),
        ("Werden beim Quiz Daten gespeichert?",
         "Nein. Das Quiz läuft vollständig in deinem Browser. Es gibt keine Rangliste, kein Konto und keine Übertragung "
         "von Ergebnissen."),
    ]
    faq_html = "".join(f"<details><summary>{e(q)}</summary><p>{e(a)}</p></details>" for q, a in faq)

    inhalt = f"""<header class="qz-kopf">
  <h1>Börde-Quiz: Kennst du deinen Landkreis?</h1>
  <p class="lead">Wo liegt Hötensleben, wo Calvörde, und zu welcher Gemeinde gehört Groß Ammensleben? Finde die {len(gemeinden)} Gemeinden und {n_ot} Ortsteile des Landkreises Börde auf der Karte. Zehn Fragen pro Runde, ohne Anmeldung und ohne Rangliste.</p>
</header>

<section class="qz-spiel" aria-labelledby="qz-spiel">
  <h2 id="qz-spiel" class="qz-unsichtbar">Quiz</h2>
  <div class="qz-modi" role="group" aria-label="Spielart wählen">
    <button type="button" data-modus="gemeinde" aria-pressed="true"><strong>Gemeinden</strong><span>Klicke die gesuchte Gemeinde an</span></button>
    <button type="button" data-modus="ortsteil" aria-pressed="false"><strong>Ortsteile</strong><span>Zu welcher Gemeinde gehört der Ort?</span></button>
    <button type="button" data-modus="genau" aria-pressed="false"><strong>Punktgenau</strong><span>Tippe so nah wie möglich an den Ort</span></button>
  </div>
  <div class="qz-brett">
    <div class="qz-frage" aria-live="polite">
      <span id="qz-runde" class="qz-runde"></span>
      <span id="qz-text" class="qz-text">Wähle eine Spielart und starte.</span>
      <span id="qz-punkte" class="qz-punktestand"></span>
    </div>
    <div id="qz-karte" class="qz-karte"><noscript>Das Quiz braucht JavaScript.</noscript></div>
    <div class="qz-leiste">
      <p id="qz-rueck" class="qz-rueck" aria-live="polite"></p>
      <button type="button" id="qz-weiter" class="qz-knopf">Los geht's</button>
    </div>
  </div>
</section>

<section aria-labelledby="qz-gemeinden">
  <h2 id="qz-gemeinden">Die {len(gemeinden)} Gemeinden und ihre Ortsteile</h2>
  <p>Zum Üben oder Nachschlagen: alle Gemeinden des Landkreises Börde mit ihren Ortsteilen. Jede Gemeinde hat einen eigenen <a href="/orte/">Ortssteckbrief</a>. Für {e(", ".join(ohne))} sind in OpenStreetMap keine Ortsteile eingetragen. Fehlt etwas? Ortsteile lassen sich in <a href="https://www.openstreetmap.org/">OpenStreetMap</a> ergänzen.</p>
  <ul class="qz-liste">{liste}</ul>
</section>

<section class="qz-text-block" aria-labelledby="qz-wissen">
  <h2 id="qz-wissen">Gut zu wissen</h2>
  <p>Der Landkreis Börde entstand 2007 aus dem Ohrekreis und dem Bördekreis. Seit der Gemeindegebietsreform 2009/2010 gibt es {len(gemeinden)} Gemeinden, viele davon Einheitsgemeinden aus früher selbstständigen Dörfern. Die größte ist {e(groesste['name'])} mit rund {zahl(groesste['km2'])} km², die kleinste {e(kleinste['name'])} mit rund {zahl(kleinste['km2'])} km². Die meisten Ortsteile hat {e(meiste['name'])} mit {len(meiste['ortsteile'])}.</p>
  <p>Das Quiz eignet sich auch für den Heimatkunde-Unterricht. Alle Grenzen und Orte stammen aus offenen Daten und dürfen frei genutzt werden.</p>
</section>

<section class="qz-text-block" aria-labelledby="qz-faq">
  <h2 id="qz-faq">Häufige Fragen</h2>
  <div class="qz-faq">{faq_html}</div>
</section>"""

    jsonld = [
        {"@context": "https://schema.org", "@type": "Quiz", "name": "Börde-Quiz: Kennst du deinen Landkreis?",
         "description": f"Kartenquiz zu den {len(gemeinden)} Gemeinden und {n_ot} Ortsteilen im Landkreis Börde.",
         "url": f"{BASIS_URL}/quiz/", "inLanguage": "de", "isAccessibleForFree": True, "educationalLevel": "Grundschule bis Erwachsene",
         "about": {"@type": "Place", "name": "Landkreis Börde, Sachsen-Anhalt"},
         "creator": {"@type": "Organization", "name": "OK Lab Börde", "url": f"{BASIS_URL}/"}},
        {"@context": "https://schema.org", "@type": "FAQPage",
         "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]},
    ]
    quelle = ('Gemeindegrenzen: © GeoBasis-DE / BKG (VG250), <a href="https://www.govdata.de/dl-de/by-2-0">dl-de/by-2-0</a>. '
              f'Ortsteile und Orte: {OSM_HINWEIS}. Ohne Gewähr.')
    html = seite(titel="Börde-Quiz: Gemeinden und Orte im Landkreis Börde finden | OK Lab Börde",
                 beschreibung=(f"Kennst du die Börde? Finde die {len(gemeinden)} Gemeinden und {n_ot} Ortsteile des Landkreises "
                               "auf der Karte. Kostenloses Kartenquiz ohne Anmeldung, auch für den Unterricht."),
                 pfad="/quiz/", inhalt=inhalt, brotkrumen=[("Start", "/"), ("Börde-Quiz", None)], jsonld=jsonld,
                 extra_head='<link rel="stylesheet" href="/assets/quiz.css">\n  <script defer src="/assets/quiz.js"></script>',
                 quelle=quelle)
    (OUT / "index.html").write_text(html, "utf-8", newline="\n")
    print(f"{len(gemeinden)} Gemeinden, {n_ot} Ortsteile, {len(daten_orte)} Orte; größte {groesste['name']} "
          f"{groesste['km2']:.0f} km², kleinste {kleinste['name']} {kleinste['km2']:.0f} km²")


if __name__ == "__main__":
    main()
