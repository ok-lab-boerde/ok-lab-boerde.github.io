"""Feuerwehren in der Börde: alle Feuerwehrhäuser aus OpenStreetMap auf einer Karte, je Gemeinde, mit Karten-Check.

Quelle: amenity=fire_station aus scripts/orte/.cache/poi.json (über fetch.py).
Wird von build.py aufgerufen und schreibt nach /feuerwehr/. Einsätze gibt es nicht als offene Daten, sie fehlen hier bewusst.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

from seiten import e, seite

KM_LON = 111.2 * math.cos(math.radians(52.2))


def kurzname(name: str) -> str:
    """„Freiwillige Feuerwehr Hohe Börde Ortsfeuerwehr Bebertal“ -> „Ortsfeuerwehr Bebertal“."""
    n = re.sub(r"\bOr(?:t|st)feuerwehr\b", "Ortsfeuerwehr", name)
    m = re.search(r"\b(Ortsfeuerwehr|Löschgruppe)\b.*", n)
    return m.group(0).strip() if m else n.strip()


def web(t: dict) -> str:
    u = (t.get("contact:website") or t.get("website") or "").split(";")[0].strip()
    return u if not u or u.startswith("http") else "https://" + u


def eintraege(elemente: list[dict], gemeinden: list[dict], verorten) -> tuple[list[dict], list[dict]]:
    """Gibt (aktive Feuerwehrhäuser, Einträge zum Prüfen) zurück."""
    roh, pruefen = [], []
    for el in elemente:
        t = el.get("tags", {})
        if t.get("amenity") != "fire_station":
            continue
        lat, lon = (el["lat"], el["lon"]) if "lat" in el else (el["center"]["lat"], el["center"]["lon"])
        g, o = verorten(lon, lat, gemeinden)
        if not g:
            continue
        ort = o["name"] if o else g["name"]
        name = t.get("name") or t.get("operator") or ""
        x = {"osm": f"{el['type']}/{el['id']}", "lat": round(lat, 5), "lon": round(lon, 5), "g": g, "ort": ort,
             "name": name, "kurz": kurzname(name) if name else f"Feuerwehrhaus {ort}",
             "werk": "Werkfeuerwehr" in name, "web": web(t),
             "facebook": t.get("contact:facebook", ""), "instagram": t.get("contact:instagram", ""),
             "strasse": " ".join(x for x in (t.get("addr:street"), t.get("addr:housenumber")) if x),
             "plz_ort": " ".join(x for x in (t.get("addr:postcode"), t.get("addr:city")) if x),
             "n_tags": len(t)}
        if t.get("disused:amenity") == "fire_station" or re.search(r"\balte[rs]?\b", name, re.I):
            x["grund"] = ("in OpenStreetMap zugleich als „nicht mehr genutzt“ markiert" if t.get("disused:amenity")
                          else "Name deutet auf ein altes, nicht mehr genutztes Gebäude hin")
            pruefen.append(x)
            continue
        roh.append(x)
    # Doppelte Einträge (Punkt und Gebäude derselben Wache) zusammenfassen: unter 150 m, der ausführlichere gewinnt
    roh.sort(key=lambda x: (-bool(x["name"]), -x["n_tags"], x["osm"]))
    aktiv: list[dict] = []
    for x in roh:
        dup = next((a for a in aktiv if math.hypot((a["lat"] - x["lat"]) * 111.2, (a["lon"] - x["lon"]) * KM_LON) < 0.15), None)
        if dup:
            for k in ("web", "facebook", "instagram", "strasse", "plz_ort"):
                dup[k] = dup[k] or x[k]
            continue
        aktiv.append(x)
    aktiv.sort(key=lambda x: (x["g"]["name"], x["werk"], x["ort"], x["kurz"]))
    for i, x in enumerate(aktiv):
        x["i"] = i
        x["fehlt"] = [k for k, da in (("Name", bool(x["name"])), ("Adresse", bool(x["strasse"])),
                                      ("Website", bool(x["web"] or x["facebook"] or x["instagram"]))) if not da]
    return aktiv, pruefen


def kurz_web(u: str) -> str:
    return re.sub(r"^https?://(www\.)?", "", u).split("/")[0]


def eintrag_html(x: dict) -> str:
    typ, oid = x["osm"].split("/")
    links = []
    if x["web"]:
        links.append(f'<a href="{e(x["web"])}" rel="noopener">{e(kurz_web(x["web"]))}</a>')
    if x["facebook"]:
        links.append(f'<a href="{e(x["facebook"])}" rel="noopener">Facebook</a>')
    if x["instagram"]:
        u = x["instagram"] if x["instagram"].startswith("http") else "https://instagram.com/" + x["instagram"].lstrip("@")
        links.append(f'<a href="{e(u)}" rel="noopener">Instagram</a>')
    adresse = ", ".join(a for a in (x["strasse"], x["plz_ort"]) if a)
    fehlt = (f'<p class="klein">In OpenStreetMap fehlt: {e(", ".join(x["fehlt"]))} · '
             f'<a href="https://www.openstreetmap.org/edit?editor=id&amp;{typ}={oid}" rel="nofollow">ergänzen</a></p>') if x["fehlt"] else ""
    werk = ' <span class="fw-art">Werkfeuerwehr</span>' if x["werk"] else ""
    voll = f'<p class="klein">{e(x["name"])}</p>' if x["name"] and x["name"] != x["kurz"] else ""
    return (f'<li class="fw-eintrag" id="fw-{x["i"]}" data-i="{x["i"]}" data-g="{e(x["g"]["slug"])}">'
            f'<h3>{e(x["kurz"])}{werk}</h3>{voll}'
            f'<p>{e(x["ort"])}{(" · " + e(adresse)) if adresse else ""}</p>'
            + (f'<p>{" · ".join(links)}</p>' if links else "") + fehlt
            + f'<p class="klein"><a href="https://www.openstreetmap.org/{typ}/{oid}">In OpenStreetMap ansehen</a></p></li>')


def uebersicht(aktiv: list[dict], pruefen: list[dict], gemeinden: list[dict], stand: str) -> str:
    n = len(aktiv)
    werk = sum(x["werk"] for x in aktiv)
    mit_web = sum(1 for x in aktiv if x["web"] or x["facebook"] or x["instagram"])
    mit_adr = sum(1 for x in aktiv if x["strasse"])
    je_g: dict[str, list[dict]] = {}
    for x in aktiv:
        je_g.setdefault(x["g"]["slug"], []).append(x)
    opt = "".join(f'<option value="{e(g["slug"])}">{e(g["name"])} ({len(je_g.get(g["slug"], []))})</option>'
                  for g in sorted(gemeinden, key=lambda g: g["name"]))
    liste = []
    for g in sorted(gemeinden, key=lambda g: g["name"]):
        xs = je_g.get(g["slug"], [])
        liste.append(f'<li class="fw-gemeinde" data-g="{e(g["slug"])}"><h2 id="g-{e(g["slug"])}">{e(g["name"])} '
                     f'<span class="anzahl">{len(xs)}</span></h2>'
                     + (f'<ul class="fw-liste">{"".join(eintrag_html(x) for x in xs)}</ul>' if xs
                        else '<p class="klein">Kein Feuerwehrhaus in OpenStreetMap eingetragen.</p>')
                     + f'<p class="klein"><a href="/orte/{e(g["slug"])}/">Ortsseite {e(g["name"])}</a></p></li>')
    # Ortsteile ohne eingetragenes Feuerwehrhaus (nicht jeder Ortsteil hat eine eigene Wehr)
    mit = {(x["g"]["slug"], x["ort"]) for x in aktiv}
    ohne = sorted((g["name"], o["name"]) for g in gemeinden for o in g["ortsteile"] if (g["slug"], o["name"]) not in mit)
    ohne_html = ", ".join(f"{e(o)} ({e(g)})" if o != g else e(o) for g, o in ohne)
    pruef_html = "".join(
        f'<li>{e(x["name"] or x["kurz"])}, {e(x["ort"])}: {e(x["grund"])} · '
        f'<a href="https://www.openstreetmap.org/{x["osm"]}">ansehen</a></li>' for x in pruefen)
    unvollst = [x for x in aktiv if x["fehlt"]]
    punkte = json.dumps([[x["lat"], x["lon"], x["kurz"], x["ort"], x["i"], int(x["werk"])] for x in aktiv],
                        ensure_ascii=False, separators=(",", ":"))

    inhalt = f"""<h1>Feuerwehren in der Börde</h1>
<p class="lead">{n} Feuerwehrhäuser im Landkreis Börde auf einer Karte. Fast alle gehören zu Freiwilligen Feuerwehren: Ehrenamtliche, die Tag und Nacht ausrücken, wenn es brennt, bei Unfällen, Unwetter und Hochwasser.</p>
<p class="fw-notruf"><strong>Im Notfall immer 112 anrufen.</strong> Die Leitstelle alarmiert die zuständige Feuerwehr. Die Kontakte auf dieser Seite sind für Fragen und fürs Mitmachen, nicht für Notfälle.</p>

<div class="kacheln">
  <div class="kachel"><span class="zahl">{n}</span><span>Feuerwehrhäuser</span></div>
  <div class="kachel"><span class="zahl">{len(je_g)}</span><span>von {len(gemeinden)} Gemeinden</span></div>
  <div class="kachel"><span class="zahl">{werk}</span><span>{"Werkfeuerwehr" if werk == 1 else "Werkfeuerwehren"}</span></div>
  <div class="kachel"><span class="zahl">{mit_web}</span><span>mit Website oder Social Media</span></div>
</div>

<form class="suche" id="fw-filter" role="search" aria-label="Feuerwehren filtern">
  <label>Suche<input type="search" id="fw-q" placeholder="Ort oder Name" autocomplete="off"></label>
  <label>Gemeinde<select id="fw-g"><option value="">alle Gemeinden</option>{opt}</select></label>
</form>
<p class="treffer" id="fw-treffer" aria-live="polite"></p>
<div class="ok-karte" id="fw-karte" style="height:min(55vh,480px)" role="region" aria-label="Karte der Feuerwehrhäuser"></div>
<script type="application/json" id="fw-daten">{punkte}</script>
<ol class="fw-gemeinden" id="fw-liste">{"".join(liste)}</ol>

<section aria-labelledby="h-mit"><h2 id="h-mit">Mitmachen bei der Freiwilligen Feuerwehr</h2>
<p>Die Feuerwehren in der Börde sind fast überall ehrenamtlich und suchen Nachwuchs: für die Einsatzabteilung, aber auch für die Kinder- und Jugendfeuerwehr, die es in vielen Orten gibt. Vorkenntnisse braucht niemand, die Ausbildung übernimmt die Feuerwehr.</p>
<ul class="eintraege">
<li>Am einfachsten zum Dienstabend vorbeischauen oder die Wehr im eigenen Ort über ihre Website ansprechen.</li>
<li>Hat die Wehr keine eigene Website, hilft die Gemeinde- oder Verbandsgemeindeverwaltung weiter.</li>
<li>Auch Arbeitgeber können helfen: Wer Einsatzkräfte für Einsätze freistellt, sorgt dafür, dass die Feuerwehr tagsüber ausrücken kann.</li>
</ul></section>

<section class="korrektur" aria-labelledby="h-check"><h2 id="h-check">Karten-Check: Stimmen die Einträge?</h2>
<p>Alle Angaben stammen aus <a href="https://www.openstreetmap.org">OpenStreetMap</a>, der freien Karte, die alle bearbeiten können. Von {n} Feuerwehrhäusern haben {mit_adr} eine Adresse und {mit_web} eine Website oder ein Social-Media-Profil. Bei {len(unvollst)} fehlt mindestens eine Angabe, der Link „ergänzen“ in der Liste führt direkt zum Bearbeiten.</p>
{f'<h3>Bitte prüfen</h3><ul class="eintraege">{pruef_html}</ul><p class="klein">Diese Einträge erscheinen nicht auf der Karte.</p>' if pruefen else ""}
<details><summary>{len(ohne)} Ortsteile ohne eingetragenes Feuerwehrhaus</summary>
<p>Nicht jeder Ortsteil hat eine eigene Feuerwehr, oft rückt die Wehr aus dem Nachbarort aus. Gibt es in einem dieser Orte doch ein Feuerwehrhaus, fehlt es vermutlich nur in OpenStreetMap: {ohne_html}.</p></details>
<p class="klein">Änderungen in OpenStreetMap erscheinen hier nach der nächsten wöchentlichen Aktualisierung. Ohne eigenes Konto geht es über einen <a href="https://www.openstreetmap.org/note/new#map=10/52.2/11.35" rel="nofollow">Hinweis an der Karte</a>.</p>
</section>

<section aria-labelledby="h-einsatz"><h2 id="h-einsatz">Und die Einsätze?</h2>
<p>Wie oft welche Feuerwehr ausrückt, gibt es bisher nicht als offene Daten. Einzelne Zahlen stehen in Jahresberichten und den Brandschutzbedarfsplänen der Gemeinden. Wir bemühen uns, zusammengefasste Einsatzzahlen je Gemeinde zu bekommen. Genaue Einsatzorte werden wir nicht zeigen, denn sie verraten oft, wessen Haus gebrannt hat.</p>
</section>

<p class="klein">Datenstand: {e(stand)}, wöchentlich aktualisiert. Daten © OpenStreetMap-Mitwirkende, Lizenz ODbL. Gemeindegrenzen © GeoBasis-DE / BKG (VG250).</p>"""
    return seite(titel="Feuerwehren in der Börde – Karte aller Feuerwehrhäuser | OK Lab Börde",
                 beschreibung=f"{n} Feuerwehrhäuser im Landkreis Börde auf einer Karte, je Gemeinde mit Kontakt und Website. Fast alle sind Freiwillige Feuerwehren, die Nachwuchs suchen.",
                 pfad="/feuerwehr/", inhalt=inhalt, karte=True, extra_head='<script src="/assets/feuerwehr.js" defer></script>',
                 brotkrumen=[("Start", "/"), ("Feuerwehren", None)])


def erzeugen(elemente: list[dict], gemeinden: list[dict], verorten, stand: str, schreibe, out: Path) -> list[str]:
    aktiv, pruefen = eintraege(elemente, gemeinden, verorten)
    schreibe(out / "index.html", uebersicht(aktiv, pruefen, gemeinden, stand))
    return ["/feuerwehr/"]
