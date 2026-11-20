"""Bereitet die Daten für den Unfallatlas Börde auf.

Lädt die Jahres-CSVs des Unfallatlas (Statistische Ämter des Bundes und der Länder),
filtert auf den Landkreis Börde (ULAND 15, UREGBEZ 0, UKREIS 83), vereinheitlicht die
Spalten und schreibt kompakte JSON-Dateien nach unfallatlas/data/.
Zusätzlich holt es Kreisgrenze und Gemeindenamen aus den Verwaltungsgebieten 1:250 000
(VG250) des Bundesamts für Kartographie und Geodäsie.

Die Rohdaten werden nur im Arbeitsspeicher verarbeitet und nicht gespeichert.

Aufruf:  python scripts/unfallatlas/build.py
Nur Standardbibliothek, kein pip install nötig.
"""
from __future__ import annotations

import csv
import io
import json
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

BASIS = "https://www.opengeodata.nrw.de/produkte/transport_verkehr/unfallatlas/"
WFS = "https://sgx.geodatenzentrum.de/wfs_vg250"
LAND, REGBEZ, KREIS = "15", "0", "83"
AGS = "15083"
OUT = Path(__file__).resolve().parents[2] / "unfallatlas" / "data"
UA = {"User-Agent": "ok-lab-boerde-unfallatlas"}

# Reihenfolge der Felder je Unfall in unfaelle.json
FELDER = ["jahr", "monat", "wochentag", "stunde", "kategorie", "art", "typ", "licht",
          "beteiligt", "gemeinde", "lat", "lon"]
# Bits im Feld "beteiligt"
BITS = {"rad": 1, "pkw": 2, "fuss": 4, "krad": 8, "gkfz": 16, "sonstige": 32, "gkfz_unbekannt": 64}


def get(url: str, timeout: int = 300) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    for versuch in range(4):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as exc:  # noqa: BLE001 - Netzwerkfehler wiederholen
            if versuch == 3:
                raise
            print(f"  {url}: {exc} – neuer Versuch", file=sys.stderr)
            time.sleep(5 * (versuch + 1))
    raise RuntimeError("unreachable")


def wfs(typename: str, **extra: str) -> dict:
    query = urllib.parse.urlencode({
        "SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature", "TYPENAMES": typename,
        "OUTPUTFORMAT": "application/json", "SRSNAME": "EPSG:4326", **extra,
    })
    return json.loads(get(f"{WFS}?{query}", timeout=120))


def feld(row: dict, *namen: str) -> str | None:
    """Erster vorhandener Spaltenname gewinnt (die Namen wechseln zwischen den Jahren)."""
    for n in namen:
        if n in row and row[n] is not None:
            return row[n].strip()
    return None


def zahl(s: str | None) -> int | None:
    if s is None or s == "":
        return None
    return int(s)


def koordinate(s: str) -> float:
    return round(float(s.replace(",", ".")), 5)


def lies_jahr(zip_bytes: bytes) -> tuple[list[list], dict]:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        kandidaten = [n for n in zf.namelist() if n.lower().endswith((".csv", ".txt"))]
        if len(kandidaten) != 1:
            raise RuntimeError(f"Unerwarteter ZIP-Inhalt: {zf.namelist()}")
        text = zf.read(kandidaten[0]).decode("utf-8-sig")

    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    spalten = reader.fieldnames or []
    info = {"datei": kandidaten[0], "spalten": spalten, "land": 0}
    zeilen = []
    for r in reader:
        if (feld(r, "ULAND") or "").lstrip("0") != LAND:
            continue
        info["land"] += 1
        if feld(r, "UREGBEZ") != REGBEZ or (feld(r, "UKREIS") or "").lstrip("0") != KREIS:
            continue

        bits = 0
        for key, namen in (("rad", ("IstRad",)), ("pkw", ("IstPKW",)), ("fuss", ("IstFuss",)),
                           ("krad", ("IstKrad",)), ("sonstige", ("IstSonstige", "IstSonstig"))):
            if feld(r, *namen) == "1":
                bits |= BITS[key]
        gkfz = feld(r, "IstGkfz")
        if gkfz is None:
            bits |= BITS["gkfz_unbekannt"]  # 2017: Lkw sind in "Sonstige" enthalten
        elif gkfz == "1":
            bits |= BITS["gkfz"]

        zeilen.append([
            zahl(feld(r, "UJAHR")), zahl(feld(r, "UMONAT")), zahl(feld(r, "UWOCHENTAG")),
            zahl(feld(r, "USTUNDE")), zahl(feld(r, "UKATEGORIE")), zahl(feld(r, "UART")),
            zahl(feld(r, "UTYP1")), zahl(feld(r, "ULICHTVERH", "LICHT")), bits,
            (feld(r, "UGEMEINDE") or "").zfill(3),
            koordinate(feld(r, "YGCSWGS84")), koordinate(feld(r, "XGCSWGS84")),
        ])
    return zeilen, info


def schreibe(pfad: Path, obj, kompakt: bool = False) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, ensure_ascii=False, separators=(",", ":") if kompakt else None,
                      indent=None if kompakt else 1)
    pfad.write_text(text + "\n", encoding="utf-8")


def main() -> None:
    liste = json.loads(get(BASIS, timeout=60))
    dateien = []
    for ds in liste.get("datasets", []):
        for f in ds.get("files", []):
            if f["name"].endswith("_CSV.zip"):
                dateien.append(f)
    dateien.sort(key=lambda f: f["name"])
    if not dateien:
        sys.exit("Keine CSV-Dateien im Verzeichnis gefunden – Daten bleiben unverändert.")

    alle: list[list] = []
    je_jahr: dict[str, int] = {}
    stand = ""
    for f in dateien:
        print(f"Lade {f['name']} …", file=sys.stderr)
        zeilen, info = lies_jahr(get(BASIS + f["name"]))
        if info["land"] == 0:
            print(f"  Sachsen-Anhalt nicht enthalten – übersprungen", file=sys.stderr)
            continue
        jahre = {z[0] for z in zeilen}
        print(f"  {info['datei']}: {len(zeilen)} Unfälle im Landkreis, Jahre {sorted(jahre)}", file=sys.stderr)
        alle.extend(zeilen)
        for j in jahre:
            je_jahr[str(j)] = sum(1 for z in zeilen if z[0] == j)
        stand = max(stand, f.get("timestamp", "")[:10])

    if not alle:
        sys.exit("Keine Unfälle für den Landkreis gefunden – Daten bleiben unverändert.")

    gem = wfs("vg250:vg250_gem", CQL_FILTER=f"ags LIKE '{AGS}%'", PROPERTYNAME="ags,gen")
    namen = {ft["properties"]["ags"][-3:]: ft["properties"]["gen"] for ft in gem["features"]}
    fehlend = sorted({z[9] for z in alle} - set(namen))
    if fehlend:
        print(f"  Hinweis: kein Name für Gemeindeschlüssel {fehlend}", file=sys.stderr)

    grenze = wfs("vg250:vg250_krs", CQL_FILTER=f"ags='{AGS}'")
    for ft in grenze["features"]:
        ft["properties"] = {"name": ft["properties"].get("gen"), "ags": ft["properties"].get("ags")}
    # Nur stabile Felder behalten: der WFS liefert sonst bei jedem Abruf einen neuen
    # "timeStamp", und die jährliche Action würde grundlos committen.
    grenze = {"type": grenze["type"], "features": grenze["features"]}

    alle.sort(key=lambda z: (z[0], z[1], z[3]))
    schreibe(OUT / "unfaelle.json", {"felder": FELDER, "bits": BITS, "gemeinden": dict(sorted(namen.items())),
                                     "unfaelle": alle}, kompakt=True)
    schreibe(OUT / "kreisgrenze.geojson", grenze, kompakt=True)
    schreibe(OUT / "stand.json", {
        "datenstand": stand,
        "jahre": sorted(int(j) for j in je_jahr),
        "anzahl": len(alle),
        "je_jahr": dict(sorted(je_jahr.items())),
        "quelle": {
            "name": "Unfallatlas der Statistischen Ämter des Bundes und der Länder",
            "url": "https://unfallatlas.statistikportal.de/",
            "daten_url": BASIS,
            "lizenz": "Datenlizenz Deutschland – Namensnennung – Version 2.0",
            "lizenz_url": "https://www.govdata.de/dl-de/by-2-0",
        },
        "grenzen": {
            "name": "Verwaltungsgebiete 1:250 000 (VG250), © GeoBasis-DE / BKG",
            "url": "https://gdz.bkg.bund.de/index.php/default/verwaltungsgebiete-1-250-000-stand-01-01-vg250-01-01.html",
            "lizenz": "Datenlizenz Deutschland – Namensnennung – Version 2.0",
            "lizenz_url": "https://www.govdata.de/dl-de/by-2-0",
        },
    })
    print(f"Fertig: {len(alle)} Unfälle, {len(namen)} Gemeinden → {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
