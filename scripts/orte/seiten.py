"""HTML-Bausteine für die erzeugten Seiten (Betriebe und Orte)."""
from __future__ import annotations

import json
import re
from html import escape

BASIS_URL = "https://oklab-boerde.de"
OSM_HINWEIS = ('Daten: © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap-Mitwirkende</a> '
               '(<a href="https://opendatacommons.org/licenses/odbl/">ODbL</a>)')


def e(text) -> str:
    return escape(str(text), quote=True)


MARKE = " | OK Lab Börde"
FUSS_PROJEKTE = [("Veranstaltungen", "/veranstaltungen/"), ("Feuerwehren", "/feuerwehr/"), ("Dürremonitor", "/duerre/"), ("Wahlatlas", "/wahlen/"), ("Leben in der Börde", "/leben/"),
                 ("Hofläden", "/regional/"), ("Zeitschichten", "/zeitschichten/"), ("Unfallatlas", "/unfallatlas/"),
                 ("Energiewende", "/energiewende/"), ("Ratskarte", "/ratskarte/")]


def ld_script(daten: dict) -> str:
    text = json.dumps(daten, ensure_ascii=False).replace("</", "<\\/")
    return f'<script type="application/ld+json">{text}</script>'


def brotkrumen_ld(brotkrumen: list[tuple[str, str | None]], pfad: str) -> str:
    """BreadcrumbList für Google; der letzte Eintrag (ohne Link) ist die Seite selbst."""
    if len(brotkrumen) < 2:
        return ""
    return ld_script({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i, "name": t, "item": f"{BASIS_URL}{u or pfad}"}
        for i, (t, u) in enumerate(brotkrumen, 1)]})


def kurzer_titel(titel: str) -> str:
    """Google kürzt Titel ab etwa 60–70 Zeichen. Zu lange Titel verlieren erst die Gemeinde in Klammern am Ende,
    dann den Markennamen (der steht ohnehin in og:site_name)."""
    if len(titel) > 70:
        titel = re.sub(r" \([^()]*\)(?=" + re.escape(MARKE) + "$|$)", "", titel)
    if len(titel) > 70 and titel.endswith(MARKE):
        titel = titel[: -len(MARKE)]
    return titel


def seite(*, titel: str, beschreibung: str, pfad: str, inhalt: str, brotkrumen: list[tuple[str, str]],
          index: bool = True, karte: bool = False, jsonld: dict | list | None = None, extra_head: str = "",
          quelle: str | None = None) -> str:
    robots = "index, follow" if index else "noindex, follow"
    krumen = " <span aria-hidden=\"true\">›</span> ".join(
        f'<a href="{e(u)}">{e(t)}</a>' if u else f'<span aria-current="page">{e(t)}</span>' for t, u in brotkrumen)
    leaflet_css = ('<link rel="stylesheet" href="/assets/vendor/leaflet/leaflet.css">\n'
                   '  <link rel="stylesheet" href="/assets/vendor/markercluster/MarkerCluster.css">') if karte else ""
    leaflet_js = ('<script src="/assets/vendor/leaflet/leaflet.js"></script>\n'
                  '  <script src="/assets/vendor/markercluster/leaflet.markercluster.js"></script>\n'
                  '  <script src="/assets/orte-karte.js"></script>') if karte else ""
    ld = "\n  ".join(ld_script(j) for j in (jsonld if isinstance(jsonld, list) else [jsonld])) if jsonld else ""
    krumen_ld = brotkrumen_ld(brotkrumen, pfad)
    titel = kurzer_titel(titel)
    og_titel = titel.removesuffix(MARKE)
    projekte = "".join(f'<li><a href="{u}">{t}</a></li>' for t, u in FUSS_PROJEKTE)
    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{e(titel)}</title>
  <meta name="description" content="{e(beschreibung)}">
  <meta name="robots" content="{robots}">
  <link rel="canonical" href="{BASIS_URL}{e(pfad)}">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="OK Lab Börde">
  <meta property="og:locale" content="de_DE">
  <meta property="og:title" content="{e(og_titel)}">
  <meta property="og:description" content="{e(beschreibung)}">
  <meta property="og:url" content="{BASIS_URL}{e(pfad)}">
  <meta property="og:image" content="{BASIS_URL}/assets/og-bild.jpg">
  <meta property="og:image:type" content="image/jpeg">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:image:alt" content="Logo und Schriftzug OK Lab Börde">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="icon" href="/assets/logo.svg" type="image/svg+xml">
  <link rel="stylesheet" href="/css/style.css">
  <link rel="stylesheet" href="/assets/orte.css">
  {leaflet_css}
  {ld}
  {krumen_ld}
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
    <p class="quelle">{quelle or OSM_HINWEIS + '. Ohne Gewähr. <a href="/betriebe/ueber-die-daten/">Über die Daten</a>'}</p>
  </main>
  <footer class="site-footer">
    <div class="wrap">
      <div>
        <p><strong>OK Lab Börde</strong></p>
        <p>Inhalte unter <a href="https://creativecommons.org/licenses/by/4.0/deed.de">CC BY 4.0</a>, Daten aus OpenStreetMap unter ODbL.</p>
      </div>
      <ul aria-label="Projekte">{projekte}</ul>
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
