"""Lädt die Rohdaten für Betriebe-Karte und Ortssteckbriefe in scripts/orte/.cache/.

Quellen:
- OpenStreetMap über die Overpass API (Lizenz ODbL, © OpenStreetMap-Mitwirkende)
- Gemeindegrenzen: Verwaltungsgebiete 1:250 000 (VG250), © GeoBasis-DE / BKG, dl-de/by-2-0

Aufruf:  python scripts/orte/fetch.py
Danach:  python scripts/orte/build.py
Nur Standardbibliothek. Höchstens einmal pro Woche ausführen (Overpass schonen).
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

CACHE = Path(__file__).resolve().parent / ".cache"
KREIS_RELATION = 62359          # Landkreis Börde, ermittelt über de:amtlicher_gemeindeschluessel=15083
AGS = "15083"
AREA = 3600000000 + KREIS_RELATION
UA = {"User-Agent": "ok-lab-boerde-orte/1.0 (+https://ok-lab-boerde.github.io/betriebe/ueber-die-daten/)"}
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]
WFS = "https://sgx.geodatenzentrum.de/wfs_vg250"

AMENITY_BETRIEB = ("restaurant|cafe|fast_food|bar|pub|biergarten|ice_cream|pharmacy|doctors|dentist|clinic|veterinary|"
                   "bank|fuel|car_wash|car_rental|driving_school|marketplace")

QUERIES = {
    "kreis_check": f"""[out:json][timeout:60];
relation({KREIS_RELATION});
out tags;""",
    "betriebe": f"""[out:json][timeout:300];
area({AREA})->.k;
(
  nwr["name"]["shop"](area.k);
  nwr["name"]["craft"](area.k);
  nwr["name"]["office"](area.k);
  nwr["name"]["amenity"~"^({AMENITY_BETRIEB})$"](area.k);
  nwr["name"]["healthcare"](area.k);
  nwr["name"]["tourism"~"^(hotel|guest_house|hostel|apartment|chalet|camp_site|caravan_site)$"](area.k);
  nwr["amenity"="vending_machine"]["vending"~"milk|eggs|food|potatoes|meat|honey|fruit|vegetables|farm"](area.k);
);
out center tags;""",
    "poi": f"""[out:json][timeout:300];
area({AREA})->.k;
(
  nwr["club"](area.k);
  nwr["office"="association"](area.k);
  nwr["leisure"~"^(sports_centre|stadium|sports_hall|swimming_pool|pitch|golf_course|horse_riding)$"]["name"](area.k);
  nwr["amenity"="fire_station"](area.k);
  nwr["amenity"~"^(kindergarten|school|childcare|library)$"](area.k);
  node["highway"="bus_stop"](area.k);
  nwr["railway"~"^(station|halt)$"](area.k);
  nwr["tourism"~"^(attraction|museum|viewpoint|zoo|theme_park|gallery)$"]["name"](area.k);
  nwr["historic"~"^(castle|manor|monastery|ruins|archaeological_site|monument|city_gate|church|tower)$"]["name"](area.k);
  nwr["leisure"~"^(bathing_place|beach_resort|nature_reserve|park)$"]["name"](area.k);
  nwr["natural"="beach"](area.k);
  nwr["leisure"="playground"](area.k);
  nwr["amenity"="townhall"](area.k);
);
out center tags;""",
    "ortsteile": f"""[out:json][timeout:300];
area({AREA})->.k;
relation["boundary"="administrative"]["admin_level"~"^(9|10)$"](area.k);
out geom;""",
    "ortspunkte": f"""[out:json][timeout:120];
area({AREA})->.k;
node["place"~"^(city|town|village|hamlet)$"]["name"](area.k);
out body;""",
}


def http(url: str, data: bytes | None = None, timeout: int = 300) -> bytes:
    req = urllib.request.Request(url, data=data, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def overpass(name: str, query: str) -> None:
    body = urllib.parse.urlencode({"data": query}).encode()
    last: Exception | None = None
    for endpoint in OVERPASS:
        for versuch in range(4):
            try:
                raw = http(endpoint, body)
                parsed = json.loads(raw)
                if parsed.get("remark") and "error" in parsed["remark"].lower():
                    raise RuntimeError(parsed["remark"])
                (CACHE / f"{name}.json").write_bytes(raw)
                print(f"{name}: {len(parsed.get('elements', []))} Elemente ({endpoint})", file=sys.stderr)
                return
            except Exception as exc:  # noqa: BLE001
                last = exc
                warte = 20 * (versuch + 1)
                print(f"  {name}: {exc} – neuer Versuch in {warte}s", file=sys.stderr)
                time.sleep(warte)
    raise SystemExit(f"Overpass-Abfrage {name} fehlgeschlagen: {last}")


def wfs_gemeinden() -> None:
    query = urllib.parse.urlencode({
        "SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature", "TYPENAMES": "vg250:vg250_gem",
        "OUTPUTFORMAT": "application/json", "SRSNAME": "EPSG:4326", "CQL_FILTER": f"ags LIKE '{AGS}%'",
    })
    raw = http(f"{WFS}?{query}", timeout=180)
    n = len(json.loads(raw)["features"])
    (CACHE / "gemeinden_vg250.json").write_bytes(raw)
    print(f"gemeinden_vg250: {n} Gemeinden", file=sys.stderr)


def main() -> None:
    CACHE.mkdir(exist_ok=True)
    wfs_gemeinden()
    for name, query in QUERIES.items():
        overpass(name, query)
        time.sleep(5)  # Overpass schonen
    kreis = json.loads((CACHE / "kreis_check.json").read_text(encoding="utf-8"))["elements"][0]["tags"]
    if kreis.get("de:amtlicher_gemeindeschluessel") != AGS:
        raise SystemExit(f"Relation {KREIS_RELATION} ist nicht mehr der Landkreis {AGS}: {kreis.get('name')}")


if __name__ == "__main__":
    main()
