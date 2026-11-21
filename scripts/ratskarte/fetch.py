"""Lädt Sitzungen und Tagesordnungen aus dem Ratsinformationssystem (SessionNet) der Stadt Wanzleben-Börde
und die Straßennamen der Gemeinde aus OpenStreetMap nach scripts/ratskarte/.cache/.

Prototyp. Gelesen werden nur öffentlich zugängliche HTML-Seiten (Sitzungskalender und Tagesordnungen),
keine PDF-Dokumente. Zwischen zwei Abrufen liegen mindestens 3 Sekunden. Abgeschlossene Sitzungen
werden nur einmal geladen, danach kommen sie aus dem Cache.

Aufruf:  python scripts/ratskarte/fetch.py
Danach:  python scripts/ratskarte/build.py
Nur Standardbibliothek.
"""
from __future__ import annotations

import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

HIER = Path(__file__).resolve().parent
CACHE = HIER / ".cache"
SITZ = CACHE / "sitzungen"
BASIS = "https://ratsinfo.kitu-genossenschaft.de/wzl_bi/"
AB_JAHR = 2024                     # Wahlperiode 2024–2029
PAUSE = 3.0
UA = {"User-Agent": "ok-lab-boerde-ratskarte/0.1 (+https://ok-lab-boerde.github.io/)"}
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]
STRASSEN_Q = """[out:json][timeout:180];
area["boundary"="administrative"]["admin_level"="8"]["name"="Wanzleben-Börde"]->.g;
way["highway"]["name"](area.g);
out center tags;"""

_letzter = 0.0


def hole(url: str) -> str:
    global _letzter
    warte = PAUSE - (time.monotonic() - _letzter)
    if warte > 0:
        time.sleep(warte)
    req = urllib.request.Request(url, headers=UA)
    for versuch in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                roh = r.read()
            break
        except OSError as ex:
            if versuch == 3:
                raise
            pause = 30 * (versuch + 1)
            print(f"  {ex} – neuer Versuch in {pause} s", file=sys.stderr)
            time.sleep(pause)
    _letzter = time.monotonic()
    try:
        return roh.decode("utf-8")
    except UnicodeDecodeError:      # SessionNet meldet utf-8, liefert aber teils Windows-1252
        return roh.decode("cp1252", errors="replace")


def strassen() -> None:
    ziel = CACHE / "strassen.json"
    daten = urllib.parse.urlencode({"data": STRASSEN_Q}).encode()
    for url in OVERPASS:
        try:
            req = urllib.request.Request(url, data=daten, headers=UA)
            with urllib.request.urlopen(req, timeout=240) as r:
                j = json.loads(r.read())
            if j.get("elements"):
                ziel.write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
                print(f"Straßen: {len(j['elements'])} Wege")
                return
        except Exception as ex:  # noqa: BLE001
            print(f"Overpass {url}: {ex}", file=sys.stderr)
    sys.exit("Straßen konnten nicht geladen werden")


def main() -> None:
    SITZ.mkdir(parents=True, exist_ok=True)
    if "--ohne-strassen" not in sys.argv:
        strassen()
    heute = date.today()
    liste: dict[str, dict] = {}
    for jahr in range(AB_JAHR, heute.year + 1):
        s = hole(f"{BASIS}si0046.asp?__cjahr={jahr}&__cmonat=1&__canz=12")
        for m in re.finditer(r'<a\s+href="si0057\.asp\?__ksinr=(\d+)"\s+title="Details anzeigen: ([^"]*?) (\d\d)\.(\d\d)\.(\d{4})"', s):
            nr, name, t, mo, j = m.groups()
            liste[nr] = {"nr": nr, "gremium": html.unescape(name).strip(), "datum": f"{j}-{mo}-{t}"}
    (CACHE / "sitzungsliste.json").write_text(json.dumps(sorted(liste.values(), key=lambda x: (x["datum"], x["nr"])),
                                                         ensure_ascii=False, indent=1), encoding="utf-8")
    neu = 0
    grenze = (heute - timedelta(days=60)).isoformat()
    for x in liste.values():
        if x["gremium"].startswith("Fraktion"):
            continue
        f = SITZ / f"{x['nr']}.html"
        # Ältere Sitzungen ändern sich nicht mehr; jüngere und künftige neu laden (Beschlüsse, Nachträge).
        if f.exists() and x["datum"] < grenze:
            continue
        try:
            f.write_text(hole(f"{BASIS}si0057.asp?__ksinr={x['nr']}"), encoding="utf-8")
        except OSError as ex:
            print(f"Abbruch nach {neu} Sitzungen ({ex}); der Rest folgt beim nächsten Lauf.", file=sys.stderr)
            break
        neu += 1
        if neu % 25 == 0:
            print(f"  {neu} Sitzungen geladen …")
    print(f"{len(liste)} Sitzungen seit {AB_JAHR}, {neu} neu geladen")


if __name__ == "__main__":
    main()
