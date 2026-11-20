"""Lädt Stromerzeugungs-Einheiten im Landkreis Börde aus dem Marktstammdatenregister
und schreibt aggregierte Kennzahlen nach energiewende/data.json.

Es werden nur Summen gespeichert: keine Betreibernamen, keine Adressen, keine Koordinaten.
Quelle: Marktstammdatenregister (Bundesnetzagentur), Datenlizenz Deutschland – Namensnennung – 2.0

Aufruf:  python scripts/fetch_mastr.py
Nur Standardbibliothek, kein pip install nötig.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

URL = ("https://www.marktstammdatenregister.de/MaStR/Einheit/EinheitJson/"
       "GetErweiterteOeffentlicheEinheitStromerzeugung")
LANDKREIS = "Börde"
PAGE_SIZE = 5000
OUT = Path(__file__).resolve().parent.parent / "energiewende" / "data.json"

# Energieträger aus dem Register -> Kategorie auf der Seite
KATEGORIEN = {
    "Solare Strahlungsenergie": "solar",
    "Wind": "wind",
    "Biomasse": "biomasse",
    "Wasser": "wasser",
    "Speicher": "speicher",
}
IN_BETRIEB = "In Betrieb"
IN_PLANUNG = "In Planung"
STILLGELEGT = ("Endgültig stillgelegt",)

DATE_RE = re.compile(r"/Date\((-?\d+)\)/")


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    m = DATE_RE.search(value)
    if not m:
        return None
    # timedelta statt fromtimestamp: Windows kann keine Daten vor 1970 umrechnen
    return EPOCH + timedelta(milliseconds=int(m.group(1)))


def fetch_page(page: int) -> dict:
    query = urllib.parse.urlencode({
        "sort": "", "page": page, "pageSize": PAGE_SIZE, "group": "",
        "filter": f"Landkreis~eq~'{LANDKREIS}'",
    })
    req = urllib.request.Request(f"{URL}?{query}", headers={"User-Agent": "ok-lab-boerde-energiewende-monitor"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                return json.load(resp)
        except Exception as exc:  # noqa: BLE001 - Netzwerkfehler wiederholen
            if attempt == 3:
                raise
            print(f"  Seite {page}: {exc} – neuer Versuch", file=sys.stderr)
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("unreachable")


def fetch_all() -> list[dict]:
    rows: list[dict] = []
    page = 1
    while True:
        data = fetch_page(page)
        if data.get("Errors"):
            raise RuntimeError(data["Errors"])
        batch = data.get("Data") or []
        rows.extend(batch)
        total = data.get("Total", 0)
        print(f"Seite {page}: {len(rows)}/{total}", file=sys.stderr)
        if not batch or len(rows) >= total:
            break
        page += 1
        time.sleep(1)
    return rows


def aggregate(rows: list[dict]) -> dict:
    cats = list(dict.fromkeys(KATEGORIEN.values())) + ["sonstige"]
    aktuell = {c: {"anzahl": 0, "kw": 0.0} for c in cats}
    planung = {c: {"anzahl": 0, "kw": 0.0} for c in cats}
    zubau = defaultdict(lambda: defaultdict(float))      # jahr -> kat -> kW in Betrieb genommen
    abgang = defaultdict(lambda: defaultdict(float))     # jahr -> kat -> kW stillgelegt
    gemeinden: dict[str, dict] = {}
    solar_art = defaultdict(lambda: {"anzahl": 0, "kw": 0.0})

    for r in rows:
        kat = KATEGORIEN.get(r.get("EnergietraegerName") or "", "sonstige")
        kw = float(r.get("Bruttoleistung") or 0)
        status = r.get("BetriebsStatusName") or ""
        start = parse_date(r.get("InbetriebnahmeDatum"))
        ende = parse_date(r.get("EndgueltigeStilllegungDatum"))

        if status == IN_PLANUNG:
            planung[kat]["anzahl"] += 1
            planung[kat]["kw"] += kw
            continue

        if start:
            zubau[start.year][kat] += kw
        if status in STILLGELEGT and ende:
            abgang[ende.year][kat] += kw

        if status != IN_BETRIEB:
            continue

        aktuell[kat]["anzahl"] += 1
        aktuell[kat]["kw"] += kw

        if kat == "solar":
            art = r.get("ArtDerSolaranlageBezeichnung") or "Unbekannt"
            solar_art[art]["anzahl"] += 1
            solar_art[art]["kw"] += kw

        name = r.get("Gemeinde") or "Unbekannt"
        g = gemeinden.setdefault(name, {"name": name, "schluessel": r.get("Gemeindeschluessel"),
                                        **{c: 0.0 for c in cats}, "anzahl": 0})
        g[kat] += kw
        g["anzahl"] += 1

    # Kumulierte Leistung je Jahr (Zubau minus Stilllegungen)
    jahre = sorted(set(zubau) | set(abgang))
    verlauf = []
    if jahre:
        laufend = defaultdict(float)
        for jahr in range(jahre[0], datetime.now(timezone.utc).year + 1):
            for c in cats:
                laufend[c] += zubau[jahr][c] - abgang[jahr][c]
            verlauf.append({"jahr": jahr, **{c: round(max(laufend[c], 0) / 1000, 2) for c in cats},
                            **{f"zubau_{c}": round(zubau[jahr][c] / 1000, 2) for c in cats}})

    def mw(d: dict) -> dict:
        return {k: {"anzahl": v["anzahl"], "mw": round(v["kw"] / 1000, 2)} for k, v in d.items()}

    gem_liste = sorted(gemeinden.values(), key=lambda g: -sum(g[c] for c in cats if c != "speicher"))
    for g in gem_liste:
        for c in cats:
            g[c] = round(g[c] / 1000, 2)

    return {
        "stand": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "landkreis": LANDKREIS,
        "einheiten_gesamt": len(rows),
        "aktuell": mw(aktuell),
        "planung": mw(planung),
        "solar_art": mw(solar_art),
        "verlauf": verlauf,
        "gemeinden": gem_liste,
        "quelle": {
            "name": "Marktstammdatenregister der Bundesnetzagentur",
            "url": "https://www.marktstammdatenregister.de/",
            "lizenz": "Datenlizenz Deutschland – Namensnennung – Version 2.0",
            "lizenz_url": "https://www.govdata.de/dl-de/by-2-0",
        },
    }


def main() -> None:
    rows = fetch_all()
    if not rows:
        sys.exit("Keine Daten erhalten – data.json bleibt unverändert.")
    result = aggregate(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{OUT} geschrieben: {len(rows)} Einheiten", file=sys.stderr)


if __name__ == "__main__":
    main()
