"""Kleine Geometrie-Helfer ohne externe Bibliotheken (Koordinaten als [lon, lat])."""
from __future__ import annotations

import math


def punkt_in_ring(lon: float, lat: float, ring: list[list[float]]) -> bool:
    drin = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi + 1e-15) + xi:
            drin = not drin
        j = i
    return drin


def punkt_in_multipolygon(lon: float, lat: float, polys: list[list[list[list[float]]]]) -> bool:
    """polys: Liste von Polygonen, jedes = [aussenring, loch1, ...]."""
    for poly in polys:
        if punkt_in_ring(lon, lat, poly[0]) and not any(punkt_in_ring(lon, lat, h) for h in poly[1:]):
            return True
    return False


def geojson_zu_polys(geom: dict) -> list:
    if geom["type"] == "Polygon":
        return [geom["coordinates"]]
    if geom["type"] == "MultiPolygon":
        return geom["coordinates"]
    return []


def ringe_aus_osm(members: list[dict]) -> list:
    """Baut aus einer Overpass-'out geom'-Relation Polygone (outer/inner-Ringe zusammensetzen)."""
    def ketten(rolle: str) -> list[list[list[float]]]:
        stuecke = [[[p["lon"], p["lat"]] for p in m["geometry"]]
                   for m in members if m.get("type") == "way" and m.get("role", "outer") in rolle and m.get("geometry")]
        ringe = []
        while stuecke:
            ring = stuecke.pop(0)
            fortschritt = True
            while ring[0] != ring[-1] and fortschritt:
                fortschritt = False
                for i, s in enumerate(stuecke):
                    if s[0] == ring[-1]:
                        ring += s[1:]
                    elif s[-1] == ring[-1]:
                        ring += s[::-1][1:]
                    elif s[-1] == ring[0]:
                        ring = s[:-1] + ring
                    elif s[0] == ring[0]:
                        ring = s[::-1][:-1] + ring
                    else:
                        continue
                    stuecke.pop(i)
                    fortschritt = True
                    break
            if len(ring) >= 4 and ring[0] == ring[-1]:
                ringe.append(ring)
        return ringe

    aussen = ketten(("outer", ""))
    innen = ketten(("inner",))
    polys = [[r] for r in aussen]
    for h in innen:
        for p in polys:
            if punkt_in_ring(h[0][0], h[0][1], p[0]):
                p.append(h)
                break
    return polys


def flaeche_und_schwerpunkt(ring: list[list[float]]) -> tuple[float, float, float]:
    a = cx = cy = 0.0
    for i in range(len(ring) - 1):
        x1, y1 = ring[i]
        x2, y2 = ring[i + 1]
        f = x1 * y2 - x2 * y1
        a += f
        cx += (x1 + x2) * f
        cy += (y1 + y2) * f
    if abs(a) < 1e-12:
        xs = [p[0] for p in ring]
        ys = [p[1] for p in ring]
        return 0.0, sum(xs) / len(xs), sum(ys) / len(ys)
    return abs(a / 2), cx / (3 * a), cy / (3 * a)


def innerer_punkt(polys: list) -> tuple[float, float]:
    """Schwerpunkt des größten Polygons; liegt er außerhalb, den ersten Ringpunkt nahe der Mitte nehmen."""
    groesstes = max(polys, key=lambda p: flaeche_und_schwerpunkt(p[0])[0])
    _, x, y = flaeche_und_schwerpunkt(groesstes[0])
    if punkt_in_multipolygon(x, y, [groesstes]):
        return x, y
    ring = groesstes[0]
    return ring[len(ring) // 2][0] * 0.5 + x * 0.5, ring[len(ring) // 2][1] * 0.5 + y * 0.5


def vereinfachen(ring: list[list[float]], toleranz: float) -> list[list[float]]:
    """Douglas-Peucker, Ring bleibt geschlossen."""
    if len(ring) < 5:
        return ring

    def dp(pts: list[list[float]]) -> list[list[float]]:
        if len(pts) < 3:
            return pts
        (x1, y1), (x2, y2) = pts[0], pts[-1]
        dx, dy = x2 - x1, y2 - y1
        norm = math.hypot(dx, dy) or 1e-15
        idx, dmax = 0, 0.0
        for i in range(1, len(pts) - 1):
            d = abs(dy * pts[i][0] - dx * pts[i][1] + x2 * y1 - y2 * x1) / norm
            if d > dmax:
                idx, dmax = i, d
        if dmax > toleranz:
            return dp(pts[: idx + 1])[:-1] + dp(pts[idx:])
        return [pts[0], pts[-1]]

    mitte = len(ring) // 2
    out = dp(ring[: mitte + 1])[:-1] + dp(ring[mitte:])
    out = [[round(x, 5), round(y, 5)] for x, y in out]
    if out[0] != out[-1]:
        out.append(out[0])
    return out if len(out) >= 4 else ring


def polys_vereinfachen(polys: list, toleranz: float) -> list:
    return [[vereinfachen(r, toleranz) for r in p] for p in polys]


def bbox(polys: list) -> list[float]:
    xs = [pt[0] for p in polys for r in p for pt in r]
    ys = [pt[1] for p in polys for r in p for pt in r]
    return [min(xs), min(ys), max(xs), max(ys)]


def distanz_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
