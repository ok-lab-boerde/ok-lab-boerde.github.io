"""Erzeugt /ratskarte/: Welche Straßen und Orte in Wanzleben-Börde kommen in Tagesordnungen von Stadtrat,
Ausschüssen und Ortschaftsräten vor?

Liest scripts/ratskarte/.cache/ (siehe fetch.py) und die Orts- und Grenzdaten aus scripts/orte/.cache/.
Verwendet nur Titel aus dem öffentlichen Teil der Tagesordnungen. Personalangelegenheiten werden ausgelassen.
Nur Standardbibliothek, deterministische Ausgabe.
"""
from __future__ import annotations

import html
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HIER = Path(__file__).resolve().parent
ROOT = HIER.parents[1]
CACHE = HIER / ".cache"
OUT = ROOT / "ratskarte"
sys.path.insert(0, str(ROOT / "scripts" / "orte"))

import build as ob  # noqa: E402
from seiten import e, seite  # noqa: E402

GEMEINDE = "Wanzleben-Börde"
BASIS = "https://ratsinfo.kitu-genossenschaft.de/wzl_bi/"

# Reine Formalien und Personalsachen: nicht auf der Karte
FORMAL = re.compile(r"^(Eröffnung|Feststellung|Änderungsanträge zur Tagesordnung|Abstimmung über die Niederschrift|"
                    r"Genehmigung der Niederschrift|Bericht|Berichte|Einwohnerfragestunde|Bürgerfragestunde|Anfragen|"
                    r"Mitteilung|Information|Kenntnisnahme|Verschiedenes|Schließung|Sonstiges|Einwohnerfragen)", re.I)
PERSONAL = re.compile(r"\b(Herr|Herrn|Frau|Wahl|Wahlen|Berufung|Abberufung|Ernennung|Ehrung|Bestellung|Vereidigung|"
                      r"Verpflichtung|Lebenslauf|Personal|Ortswehrleiter|Stellvertreter|Stellvertreterin|"
                      r"Ortsbürgermeister|Ortsbürgermeisterin|Ausscheiden|Nachrücker|Nachfolger)\b", re.I)


def text(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def norm(s: str) -> str:
    s = s.replace("ß", "ss").lower()
    s = re.sub(r"str\.(?=\s|$|,)", "strasse", s)
    return re.sub(r"[\s\-–]+", " ", s)


# ---------------------------------------------------------------- Orte und Straßen
def orte_und_strassen():
    gemeinden = ob.gemeinden_laden()
    ob.ortsteile_laden(gemeinden)
    g = next(x for x in gemeinden if x["name"] == GEMEINDE)
    punkte = [p for p in ob.ortspunkte_laden(gemeinden) if p["gemeinde"] is g and p["place"] in ("town", "village", "city")]
    orte = []
    for p in punkte:
        orte.append({"name": p["name"], "lat": round(p["lat"], 5), "lon": round(p["lon"], 5),
                     "ortsteil": p["ortsteil"]["name"] if p["ortsteil"] else p["name"],
                     "url": f"/orte/{g['slug']}/{p['ortsteil']['slug']}/" if p["ortsteil"] else f"/orte/{g['slug']}/"})
    orte.sort(key=lambda o: o["name"])

    roh = json.loads((CACHE / "strassen.json").read_text(encoding="utf-8"))["elements"]
    sammel: dict[tuple[str, str], list] = defaultdict(list)
    for el in sorted(roh, key=lambda x: x["id"]):
        name = el.get("tags", {}).get("name", "").strip()
        c = el.get("center")
        if len(name) < 5 or not c:
            continue
        gg, o = ob.verorten(c["lon"], c["lat"], gemeinden)
        if gg is not g:
            continue
        sammel[(name, o["name"] if o else GEMEINDE)].append((c["lat"], c["lon"]))
    strassen = []
    for (name, ot), pts in sorted(sammel.items()):
        if any(norm(name) == norm(o["name"]) for o in orte):
            continue
        # Punkt nahe der Mitte der Straße: der Wegmittelpunkt, der dem Durchschnitt am nächsten liegt
        mlat = sum(p[0] for p in pts) / len(pts)
        mlon = sum(p[1] for p in pts) / len(pts)
        lat, lon = min(pts, key=lambda p: (p[0] - mlat) ** 2 + (p[1] - mlon) ** 2)
        nah = min(orte, key=lambda o: (o["lat"] - lat) ** 2 + ((o["lon"] - lon) * 0.62) ** 2)["name"] if orte else ot
        strassen.append({"name": name, "ortsteil": ot, "ort": nah, "lat": round(lat, 5), "lon": round(lon, 5), "n": norm(name)})
    return g, orte, strassen


# ---------------------------------------------------------------- Sitzungen
def sitzung_lesen(nr: str) -> list[dict]:
    f = CACHE / "sitzungen" / f"{nr}.html"
    if not f.exists():
        return []
    s = f.read_text(encoding="utf-8")
    ende = re.search(r"Nicht (?:&ouml;|ö)ffentlicher Teil", s)
    if ende:
        s = s[: ende.start()]
    tops = []
    for zeile in re.findall(r'<tr class="smc-t-r-l"><td class="tofnum"[^>]*>(.*?)</tr>', s, re.S):
        m = re.search(r'<a\s+href="to0050\.asp\?__ktonr=(\d+)"[^>]*>(.*?)</a>', zeile, re.S)
        if not m:
            continue
        num = text(re.search(r'<span class="badge">(.*?)</span>', zeile, re.S).group(1)) if "badge" in zeile else ""
        if num.startswith("N"):
            continue
        b = re.search(r"<strong>Beschluss:</strong>(.*?)</p>", zeile, re.S)
        v = re.search(r'<a\s+href="vo0050\.asp\?__kvonr=(\d+)"[^>]*>(.*?)</a>', zeile, re.S)
        tops.append({"to": m.group(1), "titel": text(m.group(2)), "nr": re.sub(r"^[ÖO]\s*", "", num),
                     "beschluss": text(b.group(1)) if b else "",
                     "vo": v.group(1) if v else "", "vorlage": text(v.group(2)) if v else ""})
    return tops


def ort_aus_gremium(gremium: str, orte: list[dict]) -> dict | None:
    m = re.match(r"Ortschaftsrat\s+(.*)", gremium)
    if not m:
        return None
    rest = re.sub(r"^(Stadt|ZD)\s+", "", m.group(1)).split("/")[0].strip()
    for o in orte:
        if norm(o["name"]) == norm(rest) or norm(o["name"]).endswith(norm(rest)):
            return o
    return None


def finde(titel: str, orte: list[dict], strassen: list[dict], sitzungsort: dict | None):
    t = " " + norm(titel) + " "
    t = re.sub(r"wanzleben ?b(ö|oe)rde", " ", t)          # Gemeindename ist kein Ortsbezug
    genannte_orte = [o for o in orte if re.search(rf"(?<![a-zäöü]){re.escape(norm(o['name']))}(?![a-zäöü])", t)]
    # längere Namen zuerst, damit "Klein Wanzleben" nicht zusätzlich als "Wanzleben" zählt
    genannte_orte.sort(key=lambda o: -len(o["name"]))
    gefiltert = []
    for o in genannte_orte:
        if not any(norm(o["name"]) in norm(x["name"]) and x is not o for x in gefiltert):
            gefiltert.append(o)
    treffer = []
    namen = sorted({s["n"] for s in strassen}, key=len, reverse=True)
    belegt = t
    for n in namen:
        if not re.search(rf"(?<![a-zäöü]){re.escape(n)}(?![a-zäöü])", belegt):
            continue
        belegt = belegt.replace(n, " ")
        kand = [s for s in strassen if s["n"] == n]
        bezug = [o["ortsteil"] for o in gefiltert] or ([sitzungsort["ortsteil"]] if sitzungsort else [])
        passend = [s for s in kand if s["ortsteil"] in bezug] if bezug else []
        if len(kand) == 1:
            treffer.append(kand[0])
        elif len(passend) == 1:
            treffer.append(passend[0])
        # sonst mehrdeutig (gleiche Straße in mehreren Orten, kein Ortsbezug): nicht raten
    return gefiltert, treffer


# ---------------------------------------------------------------- Seite
def erzeugen() -> list[str]:
    g, orte, strassen = orte_und_strassen()
    liste = json.loads((CACHE / "sitzungsliste.json").read_text(encoding="utf-8"))
    punkte: dict[str, dict] = {}       # Schlüssel: "s:Straße|Ortsteil" oder "o:Ort"
    eintraege = []
    for si in liste:
        if si["gremium"].startswith("Fraktion"):
            continue
        sitzungsort = ort_aus_gremium(si["gremium"], orte)
        for top in sitzung_lesen(si["nr"]):
            titel = top["titel"]
            if FORMAL.match(titel) or PERSONAL.search(titel):
                continue
            o_namen, s_treffer = finde(titel, orte, strassen, sitzungsort)
            ziele = [("s:" + s["name"] + "|" + s["ortsteil"], f"{s['name']} ({s['ort']})",
                      s["lat"], s["lon"], "strasse") for s in s_treffer]
            if not ziele:
                for o in (o_namen or ([sitzungsort] if sitzungsort else [])):
                    ziele.append(("o:" + o["name"], o["name"], o["lat"], o["lon"], "ort"))
            if not ziele:
                continue
            idx = len(eintraege)
            eintraege.append({"d": si["datum"], "gr": si["gremium"], "si": si["nr"], "to": top["to"], "t": titel,
                              "b": top["beschluss"], "vo": top["vo"], "vn": top["vorlage"],
                              "z": [z[0] for z in ziele]})
            for key, name, lat, lon, art in ziele:
                p = punkte.setdefault(key, {"k": key, "name": name, "lat": lat, "lon": lon, "art": art, "e": []})
                p["e"].append(idx)

    eintraege_sort = sorted(range(len(eintraege)), key=lambda i: (eintraege[i]["d"], eintraege[i]["to"]), reverse=True)
    neu = {alt: n for n, alt in enumerate(eintraege_sort)}
    eintraege = [eintraege[i] for i in eintraege_sort]
    pkt = sorted(punkte.values(), key=lambda p: (p["art"], p["name"]))
    for p in pkt:
        p["e"] = sorted(neu[i] for i in p["e"])
    n_str = sum(1 for p in pkt if p["art"] == "strasse")
    n_ort = len(pkt) - n_str
    jahre = sorted({x["d"][:4] for x in eintraege}, reverse=True)
    gremien = sorted({x["gr"] for x in eintraege})

    daten = {"basis": BASIS, "punkte": [[p["k"], p["name"], p["lat"], p["lon"], p["art"], p["e"]] for p in pkt],
             "eintraege": [[x["d"], x["gr"], x["si"], x["to"], x["t"], x["b"], x["vo"], x["vn"], x["z"]] for x in eintraege]}
    daten_json = json.dumps(daten, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    stand = max((x["datum"] for x in liste if x["nr"] + ".html" in {f.name for f in (CACHE / "sitzungen").iterdir()}), default="")
    opt_ort = "".join(f'<option value="{e(p["k"])}">{e(p["name"])}</option>' for p in sorted(pkt, key=lambda p: p["name"]))
    opt_jahr = "".join(f'<option value="{j}">{j}</option>' for j in jahre)
    opt_gr = "".join(f'<option value="{e(x)}">{e(x)}</option>' for x in gremien)

    inhalt = f"""<h1>Ratskarte Wanzleben-Börde</h1>
<p class="lead">Was beraten Stadtrat, Ausschüsse und Ortschaftsräte über Ihre Straße oder Ihren Ort? Die Karte zeigt {ob.zahl(len(eintraege))} Tagesordnungspunkte seit 2024, verknüpft mit {ob.zahl(n_str)} Straßen und {ob.zahl(n_ort)} Orten.</p>
<aside class="aufruf block"><strong>Prototyp.</strong> Zurzeit nur für die Stadt Wanzleben-Börde, weil deren Ratsinformationssystem öffentlich auslesbar ist. Ausgewertet werden nur die Titel öffentlicher Tagesordnungspunkte, keine Dokumente. Die Zuordnung zu Straßen geschieht automatisch und kann Fehler enthalten. Maßgeblich ist immer das <a href="{BASIS}si0040.asp">Ratsinformationssystem der Stadt</a>.</aside>

<div id="rk-karte" class="ok-karte" style="height:min(60vh,520px)" role="region" aria-label="Karte der Straßen und Orte mit Tagesordnungspunkten"></div>
<p class="klein">Blaue Punkte: Straßen, die im Titel genannt sind. Grüne Punkte: Orte, wenn der Ort genannt ist oder der Ortschaftsrat beraten hat.</p>

<form id="rk-filter" class="suche" role="search" aria-label="Tagesordnungspunkte filtern">
<label>Suche <input id="rk-q" type="search" placeholder="z. B. Spielplatz, Bahnhofstraße"></label>
<label>Straße oder Ort <select id="rk-ort"><option value="">alle</option>{opt_ort}</select></label>
<label>Gremium <select id="rk-gr"><option value="">alle</option>{opt_gr}</select></label>
<label>Jahr <select id="rk-jahr"><option value="">alle</option>{opt_jahr}</select></label>
</form>
<p id="rk-treffer" class="klein" aria-live="polite"></p>
<ol id="rk-liste" class="rk-liste"></ol>
<noscript><p>Die Liste wird mit JavaScript aus den Daten auf dieser Seite erzeugt.</p></noscript>
<script type="application/json" id="rk-daten">{daten_json}</script>

<section aria-labelledby="h-wie"><h2 id="h-wie">Wie die Karte entsteht</h2>
<ul class="eintraege">
<li><strong>Quelle:</strong> Sitzungskalender und Tagesordnungen aus dem <a href="{BASIS}si0040.asp">Ratsinformationssystem der Stadt Wanzleben-Börde</a>, Straßennamen und Orte aus <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> (ODbL).</li>
<li><strong>Zuordnung:</strong> Steht ein Straßenname aus OpenStreetMap im Titel, erscheint der Punkt bei der Straße. Gibt es die Straße in mehreren Orten, nehmen wir den Ort, der im Titel steht oder dessen Ortschaftsrat tagt. Ist das nicht eindeutig, raten wir nicht.</li>
<li><strong>Datenschutz:</strong> Wir übernehmen nur Titel aus dem öffentlichen Teil. Formalien wie Niederschriften und Personalangelegenheiten wie Wahlen oder Ehrungen lassen wir aus. Dokumente (PDF) werden nicht ausgewertet.</li>
<li><strong>Stand:</strong> Sitzungen bis {e(stand[8:10] + "." + stand[5:7] + "." + stand[:4]) if stand else "?"}.</li>
<li>Vorbild ist die <a href="https://codefor.de/projekte/dd-ratskarte/">Ratskarte Dresden</a> des OK Lab Dresden.</li>
</ul></section>"""
    extra = '<script src="/assets/ratskarte.js" defer></script>'
    html_seite = seite(titel="Ratskarte Wanzleben-Börde – Ratsthemen auf der Karte | OK Lab Börde",
                       beschreibung=f"Welche Straßen und Orte in Wanzleben-Börde beraten Stadtrat und Ortschaftsräte? {len(eintraege)} öffentliche Tagesordnungspunkte seit 2024 auf der Karte.",
                       pfad="/ratskarte/", inhalt=inhalt, karte=True, extra_head=extra,
                       brotkrumen=[("Start", "/"), ("Ratskarte Wanzleben-Börde", None)])
    ob.schreibe(OUT / "index.html", html_seite)
    print(f"{len(eintraege)} Tagesordnungspunkte, {n_str} Straßen, {n_ort} Orte, {len(strassen)} Straßen im Abgleich", file=sys.stderr)
    return ["/ratskarte/"]


if __name__ == "__main__":
    erzeugen()
