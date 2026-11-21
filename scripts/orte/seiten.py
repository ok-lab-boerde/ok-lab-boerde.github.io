"""HTML-Bausteine für die erzeugten Seiten (Betriebe und Orte)."""
from __future__ import annotations

import json
from html import escape

BASIS_URL = "https://ok-lab-boerde.github.io"
OSM_HINWEIS = ('Daten: © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap-Mitwirkende</a> '
               '(<a href="https://opendatacommons.org/licenses/odbl/">ODbL</a>)')


def e(text) -> str:
    return escape(str(text), quote=True)


def seite(*, titel: str, beschreibung: str, pfad: str, inhalt: str, brotkrumen: list[tuple[str, str]],
          index: bool = True, karte: bool = False, jsonld: dict | None = None, extra_head: str = "") -> str:
    robots = "index, follow" if index else "noindex, follow"
    krumen = " <span aria-hidden=\"true\">›</span> ".join(
        f'<a href="{e(u)}">{e(t)}</a>' if u else f'<span aria-current="page">{e(t)}</span>' for t, u in brotkrumen)
    leaflet_css = ('<link rel="stylesheet" href="/assets/vendor/leaflet/leaflet.css">\n'
                   '  <link rel="stylesheet" href="/assets/vendor/markercluster/MarkerCluster.css">') if karte else ""
    leaflet_js = ('<script src="/assets/vendor/leaflet/leaflet.js"></script>\n'
                  '  <script src="/assets/vendor/markercluster/leaflet.markercluster.js"></script>\n'
                  '  <script src="/assets/orte-karte.js"></script>') if karte else ""
    ld = (f'<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>' if jsonld else "")
    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{e(titel)}</title>
  <meta name="description" content="{e(beschreibung)}">
  <meta name="robots" content="{robots}">
  <link rel="canonical" href="{BASIS_URL}{e(pfad)}">
  <link rel="icon" href="/assets/logo.svg" type="image/svg+xml">
  <link rel="stylesheet" href="/css/style.css">
  <link rel="stylesheet" href="/assets/orte.css">
  {leaflet_css}
  {ld}
  {extra_head}
</head>
<body>
  <a class="skip" href="#main">Zum Inhalt springen</a>
  <header class="site-header">
    <div class="wrap">
      <a class="brand" href="/"><img src="/assets/logo.svg" alt=""><span>OK Lab <b>Börde</b></span></a>
      <nav aria-label="Hauptnavigation">
        <ul>
          <li><a href="/betriebe/">Betriebe</a></li>
          <li><a href="/orte/">Orte</a></li>
          <li><a href="/#projekte">Projekte</a></li>
          <li><a href="/#mitmachen">Mitmachen</a></li>
        </ul>
      </nav>
    </div>
  </header>
  <main id="main" class="wrap orte-main">
    <nav class="krumen" aria-label="Brotkrümelnavigation">{krumen}</nav>
{inhalt}
    <p class="quelle">{OSM_HINWEIS}. Ohne Gewähr. <a href="/betriebe/ueber-die-daten/">Über die Daten</a></p>
  </main>
  <footer class="site-footer">
    <div class="wrap">
      <div>
        <p><strong>OK Lab Börde</strong></p>
        <p>Inhalte unter <a href="https://creativecommons.org/licenses/by/4.0/deed.de">CC BY 4.0</a>, Daten aus OpenStreetMap unter ODbL.</p>
      </div>
      <ul>
        <li><a href="/impressum.html">Impressum</a></li>
        <li><a href="/datenschutz.html">Datenschutz</a></li>
        <li><a href="https://github.com/ok-lab-boerde/ok-lab-boerde.github.io">Quellcode</a></li>
      </ul>
    </div>
  </footer>
  {leaflet_js}
</body>
</html>
"""


def karte_div(daten: dict, hoehe: str = "", label: str = "Karte") -> str:
    style = f' style="height:{hoehe}"' if hoehe else ""
    return (f'<div class="ok-karte" role="region" aria-label="{e(label)}"{style}></div>\n'
            f'<script type="application/json" class="ok-karte-daten">{json.dumps(daten, ensure_ascii=False, separators=(",", ":"))}</script>')


def liste(eintraege: list[tuple[str, str | None, str]], leer: str = "Keine Einträge in OpenStreetMap.") -> str:
    """eintraege: (name, url oder None, zusatz)"""
    if not eintraege:
        return f'<p class="leer">{e(leer)}</p>'
    zeilen = []
    for name, url, zusatz in eintraege:
        n = f'<a href="{e(url)}">{e(name)}</a>' if url else e(name)
        z = f' <span class="zusatz">{e(zusatz)}</span>' if zusatz else ""
        zeilen.append(f"<li>{n}{z}</li>")
    return '<ul class="eintraege">' + "".join(zeilen) + "</ul>"
