"""Erzeugt den Veranstaltungskalender:
- /veranstaltungen/                 Gesamtkalender mit Karte, Filtern und Liste
- /veranstaltungen/termine.json     kompakte Daten für die Abschnitte auf den Ortsseiten
- /veranstaltungen/kalender/*.ics   Kalender-Abo für alle und je Gemeinde

Liest scripts/veranstaltungen/.cache/termine.json (siehe fetch.py). Für die Zuordnung zu Orten nutzt es die
Ortsdaten aus scripts/orte/.cache/, falls vorhanden, sonst die eingecheckte Kopie scripts/veranstaltungen/orte.json
(so kommt der tägliche Lauf ohne den großen OSM-Abruf aus).
Nur Standardbibliothek, deterministische Ausgabe (abhängig vom Datum des Abrufs).
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

HIER = Path(__file__).resolve().parent
ROOT = HIER.parents[1]
CACHE = HIER / ".cache"
OUT = ROOT / "veranstaltungen"
ORTE_DATEI = HIER / "orte.json"
sys.path.insert(0, str(ROOT / "scripts" / "orte"))

from seiten import BASIS_URL, e, seite  # noqa: E402

VG = {
    "VG Obere Aller": ["Eilsleben", "Harbke", "Hötensleben", "Sommersdorf", "Ummendorf", "Völpke", "Wefensleben"],
    "VG Elbe-Heide": ["Angern", "Burgstall", "Colbitz", "Loitsche-Heinrichsberg", "Rogätz", "Westheide", "Zielitz"],
}
QUELLEN = {"landkreis": "Landkreis Börde", "portal": "Gemeinde-Website", "wanzleben": "Stadt Wanzleben-Börde",
           "ratsinfo": "Ratsinfo Wanzleben-Börde"}
TAGE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]


def norm(s: str) -> str:
    s = s.lower().replace("ß", "ss").replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    s = re.sub(r"\bkl\.\s*", "klein ", s)
    s = re.sub(r"\bgr\.\s*", "gross ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


# ---------------------------------------------------------------- Orte
def orte_laden() -> dict:
    """{gemeinden: [{name, slug, lat, lon}], orte: [{name, gemeinde, ortsteil, ortsteil_slug, lat, lon, rang}]}"""
    if (ROOT / "scripts" / "orte" / ".cache" / "ortspunkte.json").exists():
        import build as ob  # noqa: PLC0415
        gemeinden = ob.gemeinden_laden()
        ob.ortsteile_laden(gemeinden)
        punkte = ob.ortspunkte_laden(gemeinden)
        haupt = {}
        for p in sorted(punkte, key=lambda p: (ob.PLACE_RANG[p["place"]], p["name"])):
            haupt.setdefault(p["gemeinde"]["slug"], p)
        daten = {
            "gemeinden": [{"name": g["name"], "slug": g["slug"],
                           "lat": round(haupt[g["slug"]]["lat"], 5) if g["slug"] in haupt else None,
                           "lon": round(haupt[g["slug"]]["lon"], 5) if g["slug"] in haupt else None} for g in gemeinden],
            "orte": [{"name": p["name"], "gemeinde": p["gemeinde"]["slug"],
                      "ortsteil": p["ortsteil"]["name"] if p["ortsteil"] else "",
                      "ortsteil_slug": p["ortsteil"]["slug"] if p["ortsteil"] else "",
                      "lat": round(p["lat"], 5), "lon": round(p["lon"], 5), "rang": ob.PLACE_RANG[p["place"]]} for p in punkte],
        }
        ORTE_DATEI.write_text(json.dumps(daten, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
        return daten
    return json.loads(ORTE_DATEI.read_text(encoding="utf-8"))


def zuordnen(t: dict, daten: dict) -> tuple[dict | None, dict | None]:
    """Gibt (Gemeinde, Ortspunkt) zurück. Reihenfolge: Adresse, Ort, Titel, Veranstalter."""
    gem = {g["slug"]: g for g in daten["gemeinden"]}
    gem_name = {g["name"]: g for g in daten["gemeinden"]}
    gebiet = t.get("gebiet", "")
    if gebiet in VG:
        erlaubt = {gem_name[n]["slug"] for n in VG[gebiet] if n in gem_name}
    elif gebiet in gem_name:
        erlaubt = {gem_name[gebiet]["slug"]}
    else:
        erlaubt = set(gem)
    kandidaten = []
    for o in daten["orte"]:
        if o["gemeinde"] in erlaubt:
            for n in sorted({o["name"], re.sub(r"^Zuckerdorf\s+", "", o["name"])}):
                kandidaten.append((norm(n), o))
                # Adjektivformen: „Harbker SV“, „Samsweger Adventsglühen“, „Zielitzer Adventszauber“
                for form in {norm(n) + "er", norm(n) + "r" if n.endswith("e") else "", norm(n)[:-1] + "r" if n.endswith("en") else ""}:
                    if form:
                        kandidaten.append((form, o))
    kandidaten.sort(key=lambda x: (-len(x[0]), x[1]["rang"], x[1]["name"]))
    for feld in ("adresse", "ort", "titel", "veranstalter"):
        txt = " " + norm(t.get(feld, "")) + " "
        if len(txt) < 4:
            continue
        # Der zuerst genannte Ort gewinnt („Hundisburg / Einheitsgemeinde Haldensleben“), bei gleicher Stelle der längere Name
        treffer = [(txt.find(f" {n} "), -len(n), o) for n, o in kandidaten if f" {n} " in txt]
        if treffer:
            o = min(treffer, key=lambda x: (x[0], x[1]))[2]
            return gem[o["gemeinde"]], o
        for slug in sorted(erlaubt):
            g = gem[slug]
            if f" {norm(g['name'])} " in txt:
                return g, None
    if len(erlaubt) == 1:
        return gem[next(iter(erlaubt))], None
    return None, None


# ---------------------------------------------------------------- Hilfen
def datum_text(t: dict) -> str:
    d = date.fromisoformat(t["start"][:10])
    s = f"{TAGE[d.weekday()]}, {d.day}. {MONATE[d.month - 1]} {d.year}"
    if "T" in t["start"]:
        s += f", {t['start'][11:16]}"
        if t.get("ende") and "T" in t["ende"] and t["ende"][:10] == t["start"][:10]:
            s += f"–{t['ende'][11:16]}"
        s += " Uhr"
    if t.get("ende") and t["ende"][:10] > t["start"][:10]:
        d2 = date.fromisoformat(t["ende"][:10])
        s += f" bis {TAGE[d2.weekday()]}, {d2.day}. {MONATE[d2.month - 1]}"
    return s


def ort_text(t: dict) -> str:
    """Ort aus der Quelle, ergänzt um Adresse und zugeordneten Ortsnamen, falls sie dort nicht schon stehen."""
    ort = t.get("ort") or ""
    if t.get("adresse") and norm(t["adresse"]) not in norm(ort):
        ort = f"{ort}, {t['adresse']}" if ort else t["adresse"]
    if t.get("ort_name") and f" {norm(t['ort_name'])} " not in f" {norm(ort)} ":
        ort = f"{ort}, {t['ort_name']}" if ort else t["ort_name"]
    return ort


def ics_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def ics_falten(zeile: str) -> str:
    b = zeile.encode("utf-8")
    if len(b) <= 75:
        return zeile
    teile, akt = [], b""
    for ch in zeile:
        c = ch.encode("utf-8")
        if len(akt) + len(c) > (75 if not teile else 74):
            teile.append(akt.decode("utf-8"))
            akt = b""
        akt += c
    teile.append(akt.decode("utf-8"))
    return "\r\n ".join(teile)


def ics(termine: list[dict], name: str, stempel: str) -> str:
    z = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//OK Lab Börde//Veranstaltungen//DE", "CALSCALE:GREGORIAN",
         "METHOD:PUBLISH", f"X-WR-CALNAME:{ics_escape(name)}", "X-WR-TIMEZONE:Europe/Berlin",
         "REFRESH-INTERVAL;VALUE=DURATION:PT12H", "X-PUBLISHED-TTL:PT12H",
         "BEGIN:VTIMEZONE", "TZID:Europe/Berlin",
         "BEGIN:DAYLIGHT", "TZOFFSETFROM:+0100", "TZOFFSETTO:+0200", "TZNAME:CEST", "DTSTART:19700329T020000",
         "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU", "END:DAYLIGHT",
         "BEGIN:STANDARD", "TZOFFSETFROM:+0200", "TZOFFSETTO:+0100", "TZNAME:CET", "DTSTART:19701025T030000",
         "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU", "END:STANDARD", "END:VTIMEZONE"]
    for t in termine:
        z += ["BEGIN:VEVENT", f"UID:{t['id']}@ok-lab-boerde.github.io", f"DTSTAMP:{stempel}"]
        if "T" in t["start"]:
            s = t["start"].replace("-", "").replace(":", "") + "00"
            z.append(f"DTSTART;TZID=Europe/Berlin:{s}")
            if t.get("ende") and "T" in t["ende"] and t["ende"] > t["start"]:
                z.append(f"DTEND;TZID=Europe/Berlin:{t['ende'].replace('-', '').replace(':', '')}00")
        else:
            d = date.fromisoformat(t["start"][:10])
            bis = date.fromisoformat(t["ende"][:10]) if t.get("ende") and t["ende"][:10] > t["start"][:10] else d
            z += [f"DTSTART;VALUE=DATE:{d:%Y%m%d}", f"DTEND;VALUE=DATE:{bis + timedelta(days=1):%Y%m%d}"]
        z.append(f"SUMMARY:{ics_escape(t['titel'])}")
        ort = ort_text(t)
        if ort:
            z.append(f"LOCATION:{ics_escape(ort)}")
        z += [f"URL:{t['url']}", f"DESCRIPTION:{ics_escape('Quelle: ' + QUELLEN[t['quelle']] + ' – ' + t['url'])}", "END:VEVENT"]
    z.append("END:VCALENDAR")
    return "\r\n".join(ics_falten(x) for x in z) + "\r\n"


# ---------------------------------------------------------------- Seite
def erzeugen() -> list[str]:
    roh = json.loads((CACHE / "termine.json").read_text(encoding="utf-8"))
    abruf = date.fromisoformat(roh["abruf"])
    bis = abruf + timedelta(days=366)
    daten = orte_laden()
    gem_slug = {g["slug"]: g for g in daten["gemeinden"]}

    termine, gesehen = [], set()
    for t in roh["termine"]:
        tag = t["start"][:10]
        letzter = (t.get("ende") or t["start"])[:10]
        if letzter < abruf.isoformat() or tag > bis.isoformat():
            continue
        schluessel = (tag, norm(t["titel"]))
        if schluessel in gesehen:            # gleiche Veranstaltung aus zwei Quellen
            continue
        gesehen.add(schluessel)
        g, o = zuordnen(t, daten)
        t = dict(t)
        t["g"] = g["slug"] if g else ""
        t["g_name"] = g["name"] if g else t.get("gebiet", "")
        t["ot"] = o["ortsteil_slug"] if o else ""
        t["ort_name"] = o["name"] if o else (g["name"] if g else "")
        t["lat"] = o["lat"] if o else (g["lat"] if g else None)
        t["lon"] = o["lon"] if o else (g["lon"] if g else None)
        termine.append(t)
    termine.sort(key=lambda t: (t["start"], t["titel"], t["id"]))

    # Daten für Ortsseiten und Kalender-Abos
    kompakt = {"stand": roh["abruf"],
               "felder": ["start", "ende", "titel", "ort", "g", "ot", "url", "art"],
               "termine": [[t["start"], t.get("ende", ""), t["titel"], ort_text(t),
                            t["g"], t["ot"], t["url"], t.get("art", "")] for t in termine]}
    schreibe(OUT / "termine.json", json.dumps(kompakt, ensure_ascii=False, separators=(",", ":")) + "\n")
    stempel = f"{abruf:%Y%m%d}T000000Z"
    schreibe_bin(OUT / "kalender" / "alle.ics", ics(termine, "Veranstaltungen im Landkreis Börde", stempel))
    je_g = defaultdict(list)
    for t in termine:
        if t["g"]:
            je_g[t["g"]].append(t)
    for slug, g in gem_slug.items():
        schreibe_bin(OUT / "kalender" / f"{slug}.ics", ics(je_g.get(slug, []), f"Veranstaltungen {g['name']}", stempel))

    # Gesamtseite
    punkte = defaultdict(lambda: [None, None, "", 0])
    for t in termine:
        if t["lat"] is not None:
            k = f"{t['lat']},{t['lon']}"
            p = punkte[k]
            p[0], p[1], p[2] = t["lat"], t["lon"], t["ort_name"]
            p[3] += 1
    karte_json = json.dumps([v for _k, v in sorted(punkte.items())], ensure_ascii=False, separators=(",", ":"))
    li = []
    monat_vorher = ""
    for i, t in enumerate(termine):
        d = date.fromisoformat(t["start"][:10])
        monat = f"{MONATE[d.month - 1]} {d.year}"
        if monat != monat_vorher:
            li.append(f'<li class="vk-monat" data-m="{d:%Y-%m}"><h2>{e(monat)}</h2></li>')
            monat_vorher = monat
        ort = ort_text(t)
        art = ' <span class="vk-art">Öffentliche Sitzung</span>' if t.get("art") == "sitzung" else ""
        li.append(
            f'<li class="vk-termin" data-d="{t["start"][:10]}" data-e="{(t.get("ende") or t["start"])[:10]}" data-g="{e(t["g"])}" '
            f'data-ll="{t["lat"] if t["lat"] is not None else ""},{t["lon"] if t["lon"] is not None else ""}" data-s="{e(t.get("art", ""))}">'
            f'<p class="vk-zeit"><time datetime="{e(t["start"])}">{e(datum_text(t))}</time>{art}</p>'
            f'<h3><a href="{e(t["url"])}" rel="noopener">{e(t["titel"])}</a></h3>'
            + (f'<p class="vk-ort">{e(ort)}</p>' if ort else "")
            + f'<p class="klein">{e(t["g_name"]) + " · " if t["g_name"] else ""}Quelle: {e(QUELLEN[t["quelle"]])}'
            + (f' · Veranstalter: {e(t["veranstalter"])}' if t.get("veranstalter") else "") + "</p></li>")
    mit_terminen = sorted({t["g"] for t in termine if t["g"]}, key=lambda s: gem_slug[s]["name"])
    opt = "".join(f'<option value="{e(s)}">{e(gem_slug[s]["name"])} ({len(je_g[s])})</option>' for s in mit_terminen)
    abos = "".join(f'<li><a href="/veranstaltungen/kalender/{e(s)}.ics">{e(gem_slug[s]["name"])}</a></li>'
                   for s in sorted(gem_slug, key=lambda s: gem_slug[s]["name"]))
    q = roh.get("quellen", {})
    quellen_li = "".join(f"<li>{e(n)}: {'nicht erreichbar, letzter Stand' if v is None else str(v) + ' Termine'}</li>" for n, v in q.items())
    stand = f"{abruf.day}.{abruf.month}.{abruf.year}"

    inhalt = f"""<h1>Veranstaltungen in der Börde</h1>
<p class="lead">{len(termine)} Termine aus den Kalendern des Landkreises und der Gemeinden: Weihnachtsmärkte, Konzerte, Feste, Vereinsveranstaltungen und öffentliche Sitzungen. Stand: {e(stand)}, täglich aktualisiert.</p>

<form class="suche" id="vk-filter" role="search" aria-label="Veranstaltungen filtern">
  <label>Suche<input type="search" id="vk-q" placeholder="z. B. Weihnachtsmarkt, Konzert" autocomplete="off"></label>
  <label>Gemeinde<select id="vk-g"><option value="">alle Gemeinden</option>{opt}</select></label>
  <label>Zeitraum<select id="vk-z"><option value="">alle</option><option value="heute">heute</option><option value="we">dieses Wochenende</option><option value="7">nächste 7 Tage</option><option value="30">nächste 30 Tage</option></select></label>
  <label class="schalter"><input type="checkbox" id="vk-s" checked> öffentliche Sitzungen zeigen</label>
</form>
<p class="treffer" id="vk-treffer" aria-live="polite"></p>
<div class="ok-karte" id="vk-karte" style="height:min(45vh,400px)" role="region" aria-label="Karte der Veranstaltungsorte"></div>
<script type="application/json" id="vk-daten">{karte_json}</script>
<ol class="vk-liste" id="vk-liste">{"".join(li)}</ol>

<section aria-labelledby="h-abo"><h2 id="h-abo">Kalender abonnieren</h2>
<p>Die Termine lassen sich im Kalender auf Handy oder Computer abonnieren und bleiben dann von selbst aktuell. Link kopieren und im Kalender „Abonnement hinzufügen“ bzw. „Kalender per URL“ wählen.</p>
<p><strong>Alle Termine:</strong> <a class="url-lang" href="/veranstaltungen/kalender/alle.ics">{BASIS_URL}/veranstaltungen/kalender/alle.ics</a></p>
<details><summary>Kalender je Gemeinde</summary><ul class="spalten">{abos}</ul></details>
</section>

<section aria-labelledby="h-quellen"><h2 id="h-quellen">Woher die Termine kommen</h2>
<ul class="eintraege">
<li>Aus den öffentlichen Veranstaltungskalendern des <a href="https://www.landkreis-boerde.de/erleben/veranstaltungen">Landkreises</a>, der Gemeinde <a href="https://www.niedere-boerde.de/veranstaltungen">Niedere Börde</a>, der Verbandsgemeinden <a href="https://www.obere-aller.de/veranstaltungen">Obere Aller</a> und <a href="https://www.elbe-heide.de/veranstaltungen">Elbe-Heide</a> sowie der <a href="https://www.wanzleben-boerde.de/de/aktuelles/veranstaltungen.html">Stadt Wanzleben-Börde</a> (dort auch die öffentlichen Sitzungen aus dem <a href="https://ratsinfo.kitu-genossenschaft.de/wzl_bi/">Ratsinfo</a>).</li>
<li>Wir übernehmen nur Titel, Datum, Uhrzeit und Ort. Beschreibungen, Bilder und Eintrittspreise stehen beim Veranstalter, jeder Titel verlinkt dorthin. Kurzfristige Änderungen bitte dort prüfen.</li>
<li>Andere Gemeinden fehlen noch, weil ihre Kalender nicht maschinenlesbar oder für automatische Abrufe gesperrt sind. Wir fragen nach.</li>
<li>Ihre Veranstaltung fehlt? Am besten im Kalender Ihrer Gemeinde oder beim Landkreis eintragen lassen, dann erscheint sie auch hier.</li>
</ul>
<details><summary>Letzter Abruf je Quelle</summary><ul>{quellen_li}</ul></details>
</section>"""
    schreibe(OUT / "index.html", seite(
        titel="Veranstaltungen im Landkreis Börde – Kalender | OK Lab Börde",
        beschreibung=f"{len(termine)} Veranstaltungen im Landkreis Börde: Märkte, Konzerte, Feste und öffentliche Sitzungen, nach Gemeinde filterbar und als Kalender-Abo.",
        pfad="/veranstaltungen/", inhalt=inhalt, karte=True, extra_head='<script src="/assets/veranstaltungen.js" defer></script>',
        brotkrumen=[("Start", "/"), ("Veranstaltungen", None)]))
    zugeordnet = sum(1 for t in termine if t["g"])
    print(f"{len(termine)} Termine, {zugeordnet} einer Gemeinde zugeordnet, {sum(1 for t in termine if t['ot'] or t['lat'])} mit Kartenpunkt",
          file=sys.stderr)
    return ["/veranstaltungen/"]


def schreibe(pfad: Path, text: str) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    if not pfad.exists() or pfad.read_text(encoding="utf-8") != text:
        pfad.write_text(text, encoding="utf-8", newline="\n")


def schreibe_bin(pfad: Path, text: str) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    b = text.encode("utf-8")
    if not pfad.exists() or pfad.read_bytes() != b:
        pfad.write_bytes(b)


if __name__ == "__main__":
    if "--nur-orte" in sys.argv:          # wöchentlich nach dem OSM-Abruf: Ortsliste für den täglichen Lauf erneuern
        orte_laden()
    else:
        erzeugen()
